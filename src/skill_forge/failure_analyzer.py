"""Four-dimensional failure analyzer (Knowledge / Tool / Clarification / Style)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Optional, Set

from .judge_mode import JudgeMode, effective_judge_mode
from .types import (
    CATEGORY_PRIORITY,
    BadCase,
    Consistency,
    DimensionResult,
    FailureCategory,
    FailureRecord,
    Severity,
)

if TYPE_CHECKING:
    from prompt_optimizer import LLMClient

_REQUIRED_TOOLS_STANDARD = {
    "financial_rigor",
    "verify-market-cap",
    "cross-validate",
    "verify-valuation",
    "report_audit",
}

_KNOWLEDGE_MARKERS = (
    "financial-data",
    "双源",
    "交叉验证",
    "macrotrends",
    "stockanalysis",
    "信息丰富度",
)

_STYLE_MARKERS = (
    "行动卡",
    "action card",
    "综合决策",
    "AI研究置信度",
)


def _severity_rank(s: Severity) -> int:
    return {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}[s]


def _max_severity(items: List[DimensionResult]) -> Severity:
    if not items:
        return Severity.LOW
    return max(items, key=lambda d: _severity_rank(d.severity)).severity


def _pick_primary(dims: List[DimensionResult]) -> FailureCategory:
    flagged = [d for d in dims if d.severity != Severity.LOW]
    if not flagged:
        return FailureCategory.STYLE
    flagged.sort(
        key=lambda d: (
            -_severity_rank(d.severity),
            CATEGORY_PRIORITY.index(d.category),
        )
    )
    return flagged[0].category


def _normalize_tools(tool_trace: List[str]) -> Set[str]:
    out: Set[str] = set()
    for t in tool_trace:
        base = t.split("/")[-1].replace(".py", "").strip().lower()
        out.add(base)
        if "financial_rigor" in t:
            out.add("financial_rigor")
        if "report_audit" in t:
            out.add("report_audit")
    return out


def _analyze_knowledge(case: BadCase) -> DimensionResult:
    text = case.agent_output.lower()
    ref = case.reference_output.lower()
    issues: List[str] = []

    if case.consistency == Consistency.INCONSISTENT:
        issues.append("agent output conflicts with expert reference resolution")

    missing_markers = [m for m in _KNOWLEDGE_MARKERS if m.lower() not in text]
    if len(missing_markers) >= 3:
        issues.append(f"missing domain markers: {', '.join(missing_markers[:3])}")

    ref_nums = set(re.findall(r"\d{2,}(?:\.\d+)?", ref))
    out_nums = set(re.findall(r"\d{2,}(?:\.\d+)?", text))
    if ref_nums and len(ref_nums & out_nums) / max(len(ref_nums), 1) < 0.3:
        issues.append("key numeric facts from reference not reflected in output")

    audit = case.metadata.get("audit_failures") or []
    if audit:
        issues.append(f"report_audit flagged {len(audit)} data point(s)")

    if not issues:
        return DimensionResult(
            FailureCategory.KNOWLEDGE, Severity.LOW, "ok", "knowledge adequate"
        )
    severity = Severity.HIGH if case.consistency == Consistency.INCONSISTENT else Severity.MEDIUM
    return DimensionResult(
        FailureCategory.KNOWLEDGE,
        severity,
        "missing" if "missing" in issues[0] else "incorrect",
        "; ".join(issues),
    )


def _analyze_tool(case: BadCase) -> DimensionResult:
    depth = (case.metadata.get("depth") or "standard").lower()
    tools = _normalize_tools(case.tool_trace)
    required = set(_REQUIRED_TOOLS_STANDARD)
    if depth == "lite":
        required -= {"report_audit"}

    missing = sorted(required - tools)
    if missing:
        sev = Severity.HIGH if len(missing) >= 2 else Severity.MEDIUM
        return DimensionResult(
            FailureCategory.TOOL,
            sev,
            "missing_invocation",
            f"required tools not called: {', '.join(missing)}",
        )

    wrong = case.metadata.get("tool_errors") or []
    if wrong:
        return DimensionResult(
            FailureCategory.TOOL,
            Severity.MEDIUM,
            "wrong_params",
            "; ".join(str(w) for w in wrong[:3]),
        )
    return DimensionResult(
        FailureCategory.TOOL, Severity.LOW, "ok", "tool usage adequate"
    )


def _analyze_clarification(case: BadCase) -> DimensionResult:
    text = case.agent_output
    questions = len(re.findall(r"[?？]", text))
    depth = (case.metadata.get("depth") or "standard").lower()

    if depth == "lite" and questions > 5:
        return DimensionResult(
            FailureCategory.CLARIFICATION,
            Severity.MEDIUM,
            "over_asking",
            f"lite mode but {questions} clarification questions asked",
        )
    if depth in ("standard", "deep") and questions == 0 and case.consistency != Consistency.CONSISTENT:
        return DimensionResult(
            FailureCategory.CLARIFICATION,
            Severity.MEDIUM,
            "under_asking",
            "no clarifying questions before incomplete analysis",
        )
    if questions > 12:
        return DimensionResult(
            FailureCategory.CLARIFICATION,
            Severity.MEDIUM,
            "over_asking",
            f"excessive questions ({questions})",
        )
    return DimensionResult(
        FailureCategory.CLARIFICATION, Severity.LOW, "ok", "clarification adequate"
    )


def _analyze_style(case: BadCase) -> DimensionResult:
    text = case.agent_output.lower()
    missing = [m for m in _STYLE_MARKERS if m.lower() not in text]
    if len(missing) >= 2:
        return DimensionResult(
            FailureCategory.STYLE,
            Severity.MEDIUM,
            "format_gap",
            f"missing report structure: {', '.join(missing)}",
        )
    if len(case.agent_output) > 12000:
        return DimensionResult(
            FailureCategory.STYLE,
            Severity.MEDIUM,
            "verbose",
            "response overly verbose for customer-facing research deliverable",
        )
    if case.consistency == Consistency.PARTIAL and "结论" not in text and "decision" not in text:
        return DimensionResult(
            FailureCategory.STYLE,
            Severity.MEDIUM,
            "weak_conclusion",
            "partial consistency but no explicit conclusion section",
        )
    return DimensionResult(
        FailureCategory.STYLE, Severity.LOW, "ok", "style adequate"
    )


def analyze_bad_case_rules(case: BadCase) -> FailureRecord:
    """Rule-based four-dimension analysis (offline fallback)."""
    dims = [
        _analyze_knowledge(case),
        _analyze_tool(case),
        _analyze_clarification(case),
        _analyze_style(case),
    ]
    flagged = [d for d in dims if d.severity != Severity.LOW]

    primary = _pick_primary(dims)
    overall = _max_severity(flagged) if flagged else Severity.LOW
    categories = sorted({d.category for d in flagged}, key=lambda c: CATEGORY_PRIORITY.index(c))

    return FailureRecord(
        task_id=case.task_id,
        skill_name=case.skill_name,
        dimensions=dims,
        primary_category=primary,
        overall_severity=overall,
        failure_categories=categories,
    )


def analyze_bad_case(
    case: BadCase,
    *,
    llm: Optional["LLMClient"] = None,
    mode: JudgeMode = JudgeMode.AUTO,
) -> FailureRecord:
    """Four-dimension analysis; LLM when mode allows, else rules."""
    from .llm_judge import judge_failure_record, resolve_llm_client

    client = llm
    if mode != JudgeMode.RULE and client is None:
        client = resolve_llm_client()
    eff = effective_judge_mode(mode, client)

    if eff == JudgeMode.LLM and client is not None:
        try:
            return judge_failure_record(
                {
                    "task_id": case.task_id,
                    "skill_name": case.skill_name,
                    "agent_output": case.agent_output,
                    "reference_output": case.reference_output,
                    "consistency": case.consistency.value,
                    "tool_trace": case.tool_trace,
                    "metadata": case.metadata,
                },
                client,
            )
        except Exception:
            pass
    return analyze_bad_case_rules(case)


def analyze_batch(
    cases: List[BadCase],
    *,
    llm: Optional["LLMClient"] = None,
    mode: JudgeMode = JudgeMode.AUTO,
) -> List[FailureRecord]:
    return [
        analyze_bad_case(c, llm=llm, mode=mode)
        for c in cases
        if c.is_failure
    ]
