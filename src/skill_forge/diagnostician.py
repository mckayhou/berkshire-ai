"""Skill Diagnostician — map aggregated failures to SKILL.md sections."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from .judge_mode import JudgeMode, effective_judge_mode
from .types import (
    AggregatedFailure,
    DiagnosticReport,
    FailureCategory,
    OptimizationItem,
)

if TYPE_CHECKING:
    from prompt_optimizer import LLMClient

_SECTION_MAP: Dict[FailureCategory, Dict[str, str]] = {
    FailureCategory.KNOWLEDGE: {
        "missing": "第一步：数据收集",
        "incorrect": "前置步骤：AI研究偏见自觉",
        "ok": "第一步：数据收集",
    },
    FailureCategory.TOOL: {
        "missing_invocation": "数据交叉验证",
        "wrong_params": "数据交叉验证",
        "ok": "数据交叉验证",
    },
    FailureCategory.CLARIFICATION: {
        "over_asking": "研究深度（depth）",
        "under_asking": "研究深度（depth）",
        "ok": "研究深度（depth）",
    },
    FailureCategory.STYLE: {
        "format_gap": "输出要求",
        "verbose": "输出要求",
        "weak_conclusion": "输出要求",
        "ok": "输出要求",
    },
}

_PATCH_TEMPLATES: Dict[FailureCategory, Dict[str, str]] = {
    FailureCategory.KNOWLEDGE: {
        "missing": (
            "- **SkillForge 补强**：本场景多次遗漏领域知识引用。"
            " 执行前必须阅读 `skills/financial-data.md`，并在报告开头标注信息丰富度（A/B/C）。"
        ),
        "incorrect": (
            "- **SkillForge 补强**：出现与专家参考不一致的事实陈述。"
            " 所有推算数据须标注置信度，禁止用「合理推测」填补空白。"
        ),
    },
    FailureCategory.TOOL: {
        "missing_invocation": (
            "- **SkillForge 补强（工具）**：未调用必备工具链。"
            " standard/deep 模式必须在数据收集后执行 `financial_rigor.py`"
            "（verify-market-cap / cross-validate / verify-valuation），"
            "standard/deep 准出前必须 `report_audit.py`。"
        ),
        "wrong_params": (
            "- **SkillForge 补强（工具参数）**：工具调用参数不完整。"
            " cross-validate 须覆盖收入与净利润；three-scenario 仅在 deep 模式强制。"
        ),
    },
    FailureCategory.CLARIFICATION: {
        "over_asking": (
            "- **SkillForge 补强（澄清）**：lite 模式禁止超过 3 个澄清问题；"
            " 信息足够时直接进入分析，勿反复确认已知字段。"
        ),
        "under_asking": (
            "- **SkillForge 补强（澄清）**：分析不完整时须先确认 depth 模式"
            "（lite/standard/deep）及用户最关心的决策问题，再展开七模块研究。"
        ),
    },
    FailureCategory.STYLE: {
        "format_gap": (
            "- **SkillForge 补强（格式）**：报告必须含综合决策表与行动卡；"
            " 结论段须区分「AI研究置信度」与「实际投资确定性」。"
        ),
        "verbose": (
            "- **SkillForge 补强（风格）**：避免冗长复述公开资料；"
            " 每模块保留 3–5 条要点，图表仅保留支撑结论的数据。"
        ),
        "weak_conclusion": (
            "- **SkillForge 补强（结论）**：即使部分一致，也须给出明确投资建议"
            "（买入/观望/回避）及 3 条以内核心理由。"
        ),
    },
}


def diagnose_rules(
    skill_name: str,
    version: int,
    aggregated: List[AggregatedFailure],
) -> DiagnosticReport:
    """Rule-based diagnostic report (offline fallback)."""
    root_causes: List[str] = []
    plan: List[OptimizationItem] = []

    for agg in aggregated:
        section = _SECTION_MAP.get(agg.category, {}).get(
            agg.issue_type,
            _SECTION_MAP.get(agg.category, {}).get("ok", "输出要求"),
        )
        template = (
            _PATCH_TEMPLATES.get(agg.category, {}).get(agg.issue_type)
            or _PATCH_TEMPLATES.get(agg.category, {}).get("missing")
            or f"- SkillForge: address {agg.category.value}/{agg.issue_type}"
        )
        root = (
            f"{agg.category.value}:{agg.issue_type} ×{agg.count} "
            f"→ section「{section}」"
        )
        root_causes.append(root)
        plan.append(
            OptimizationItem(
                section_heading=section,
                action="append",
                content=template,
                evidence_task_ids=agg.representative_task_ids,
                category=agg.category,
                issue_type=agg.issue_type,
                expected_impact=f"reduce {agg.category.value} failures (n={agg.count})",
            )
        )

    return DiagnosticReport(
        skill_name=skill_name,
        version=version,
        aggregated=aggregated,
        root_causes=root_causes,
        optimization_plan=plan,
    )


def diagnose(
    skill_name: str,
    version: int,
    aggregated: List[AggregatedFailure],
    *,
    skill_markdown: Optional[str] = None,
    llm: Optional["LLMClient"] = None,
    mode: JudgeMode = JudgeMode.AUTO,
) -> DiagnosticReport:
    """Produce root causes and optimization plan; LLM when mode allows."""
    from .llm_judge import judge_diagnostic_plan, resolve_llm_client

    client = llm
    if mode != JudgeMode.RULE and client is None:
        client = resolve_llm_client()
    eff = effective_judge_mode(mode, client)

    if eff == JudgeMode.LLM and client is not None and skill_markdown:
        try:
            agg_dicts = [a.to_dict() for a in aggregated]
            for i, a in enumerate(aggregated):
                agg_dicts[i]["representative_task_ids"] = a.representative_task_ids
            roots, plan = judge_diagnostic_plan(
                skill_name, version, agg_dicts, skill_markdown, client
            )
            for item in plan:
                if item.evidence_task_ids:
                    continue
                for agg in aggregated:
                    if (
                        item.category == agg.category
                        and item.issue_type == agg.issue_type
                    ):
                        item.evidence_task_ids = list(agg.representative_task_ids)
                        break
            return DiagnosticReport(
                skill_name=skill_name,
                version=version,
                aggregated=aggregated,
                root_causes=roots,
                optimization_plan=plan,
            )
        except Exception:
            pass

    return diagnose_rules(skill_name, version, aggregated)
