"""LLM-judge for SkillForge: Consistency Rate + failure dimensions + diagnostic plan."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .types import (
    CATEGORY_PRIORITY,
    Consistency,
    DimensionResult,
    FailureCategory,
    FailureRecord,
    OptimizationItem,
    Severity,
)

if TYPE_CHECKING:
    from prompt_optimizer import LLMClient

try:
    from ..prompt_optimizer import LLMClient, OpenAICompatibleLLMClient
    from ..sanitize import sanitize_untrusted
except ImportError:  # pragma: no cover - flat PYTHONPATH=src
    from prompt_optimizer import LLMClient, OpenAICompatibleLLMClient
    from sanitize import sanitize_untrusted


@dataclass
class ConsistencyJudgment:
    consistency: Consistency
    rationale: str
    strict_match: bool  # True iff consistent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consistency": self.consistency.value,
            "rationale": self.rationale,
            "strict_match": self.strict_match,
        }


@dataclass
class ConsistencyBatchReport:
    judgments: List[ConsistencyJudgment]
    task_ids: List[str]

    @property
    def strict_cr(self) -> float:
        if not self.judgments:
            return 0.0
        return sum(1 for j in self.judgments if j.consistency == Consistency.CONSISTENT) / len(
            self.judgments
        )

    @property
    def lenient_cr(self) -> float:
        if not self.judgments:
            return 0.0
        ok = {Consistency.CONSISTENT, Consistency.PARTIAL}
        return sum(1 for j in self.judgments if j.consistency in ok) / len(self.judgments)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strict_cr": round(self.strict_cr, 4),
            "lenient_cr": round(self.lenient_cr, 4),
            "n": len(self.judgments),
            "judgments": [
                {"task_id": tid, **j.to_dict()}
                for tid, j in zip(self.task_ids, self.judgments)
            ],
        }


_CR_SYSTEM = """你是企业投研/技术支持质量评审员（LLM-judge）。
比较「Agent 输出」与「专家参考回复」，判断二者在问题澄清与解决方案上是否一致。
专家参考是历史工单中的可接受解之一，不是唯一正确答案；若 Agent 给出等价且正确的方案也算一致。

只输出一个 JSON 对象，不要 markdown 围栏，不要其它文字。格式：
{
  "consistency": "consistent" | "partial" | "inconsistent",
  "rationale": "一句话理由",
  "core_action_aligned": true | false
}

分类标准：
- consistent：澄清与解决方案与参考对齐，措辞差异不影响结论
- partial：与参考不矛盾但遗漏重要细节
- inconsistent：缺少关键澄清、遗漏核心方案要素、或与参考冲突
"""


_FA_SYSTEM = """你是 SkillForge Failure Analyzer。对一条失败执行记录做四维并行归因：
knowledge（领域知识）、tool（工具调用）、clarification（澄清提问）、style（语气与格式）。

只输出 JSON，不要 markdown：
{
  "dimensions": [
    {"category": "knowledge|tool|clarification|style", "severity": "low|medium|high",
     "issue_type": "简短类型标签", "hint": "诊断提示"}
  ],
  "primary_category": "knowledge|tool|clarification|style",
  "overall_severity": "low|medium|high"
}

severity=low 表示该维度无问题。primary_category 按 severity 与优先级 knowledge>tool>clarification>style 选取。
"""


_DIAG_SYSTEM = """你是 SkillForge Skill Diagnostician。根据聚合失败报告与 SKILL.md 结构，产出可执行的优化计划。
原则：Minimal Modification（只追加必要规则）、Do No Harm（不删现有内容）、Evidence-Based。

只输出 JSON：
{
  "root_causes": ["..."],
  "optimization_plan": [
    {
      "section_heading": "SKILL.md 中存在的章节标题子串",
      "action": "append",
      "content": "以 - 开头的单行或多行 markdown 补强条目",
      "category": "knowledge|tool|clarification|style",
      "issue_type": "类型",
      "expected_impact": "预期效果"
    }
  ]
}
"""


def resolve_llm_client(
    explicit: Optional["LLMClient"] = None,
    *,
    require: bool = False,
) -> Optional["LLMClient"]:
    if explicit is not None:
        return explicit
    try:
        return OpenAICompatibleLLMClient()
    except Exception:
        if require:
            raise
        return None


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
    return {}


def _parse_consistency(raw: str) -> Consistency:
    try:
        return Consistency(raw.lower().strip())
    except ValueError:
        return Consistency.INCONSISTENT


def _parse_severity(raw: str) -> Severity:
    try:
        return Severity(raw.lower().strip())
    except ValueError:
        return Severity.MEDIUM


def _parse_category(raw: str) -> FailureCategory:
    try:
        return FailureCategory(raw.lower().strip())
    except ValueError:
        return FailureCategory.KNOWLEDGE


def judge_consistency(
    agent_output: str,
    reference_output: str,
    llm: "LLMClient",
    *,
    task_id: str = "",
    skill_name: str = "",
    depth: str = "standard",
) -> ConsistencyJudgment:
    """LLM-judge Consistency Rate (Strict / Lenient)."""
    agent = sanitize_untrusted(agent_output) or "（空）"
    ref = sanitize_untrusted(reference_output) or "（空）"
    user = (
        f"task_id: {task_id}\n"
        f"skill: {skill_name}\n"
        f"depth: {depth}\n\n"
        f"<<<AGENT_OUTPUT\n{agent}\nAGENT_OUTPUT>>>\n\n"
        f"<<<REFERENCE\n{ref}\nREFERENCE>>>"
    )
    raw = llm.complete(_CR_SYSTEM, user)
    data = _extract_json(raw)
    consistency = _parse_consistency(str(data.get("consistency", "inconsistent")))
    rationale = str(data.get("rationale", raw[:200]))
    return ConsistencyJudgment(
        consistency=consistency,
        rationale=rationale,
        strict_match=consistency == Consistency.CONSISTENT,
    )


def judge_consistency_batch(
    tasks: List[Dict[str, Any]],
    llm: "LLMClient",
) -> ConsistencyBatchReport:
    judgments: List[ConsistencyJudgment] = []
    task_ids: List[str] = []
    for t in tasks:
        tid = str(t.get("task_id", ""))
        j = judge_consistency(
            str(t.get("agent_output", "")),
            str(t.get("reference_output", "")),
            llm,
            task_id=tid,
            skill_name=str(t.get("skill_name", "")),
            depth=str((t.get("metadata") or {}).get("depth", "standard")),
        )
        judgments.append(j)
        task_ids.append(tid)
    return ConsistencyBatchReport(judgments=judgments, task_ids=task_ids)


def judge_failure_record(
    case_dict: Dict[str, Any],
    llm: "LLMClient",
) -> FailureRecord:
    """LLM four-dimension failure analysis for one bad case."""
    agent = sanitize_untrusted(str(case_dict.get("agent_output", "")))
    ref = sanitize_untrusted(str(case_dict.get("reference_output", "")))
    tools = case_dict.get("tool_trace") or []
    meta = case_dict.get("metadata") or {}
    user = json.dumps(
        {
            "task_id": case_dict.get("task_id"),
            "skill_name": case_dict.get("skill_name"),
            "consistency": case_dict.get("consistency"),
            "tool_trace": tools,
            "metadata": meta,
            "agent_output": agent,
            "reference_output": ref,
        },
        ensure_ascii=False,
    )
    raw = llm.complete(_FA_SYSTEM, user)
    data = _extract_json(raw)
    dims: List[DimensionResult] = []
    for d in data.get("dimensions") or []:
        dims.append(
            DimensionResult(
                category=_parse_category(str(d.get("category", "knowledge"))),
                severity=_parse_severity(str(d.get("severity", "medium"))),
                issue_type=str(d.get("issue_type", "unknown")),
                hint=str(d.get("hint", "")),
            )
        )
    if len(dims) < 4:
        raise ValueError("LLM failure analysis returned incomplete dimensions")

    primary = _parse_category(str(data.get("primary_category", dims[0].category.value)))
    overall = _parse_severity(str(data.get("overall_severity", "medium")))
    flagged = [d for d in dims if d.severity != Severity.LOW]
    categories = sorted(
        {d.category for d in flagged},
        key=lambda c: CATEGORY_PRIORITY.index(c),
    )
    return FailureRecord(
        task_id=str(case_dict.get("task_id", "")),
        skill_name=str(case_dict.get("skill_name", "")),
        dimensions=dims,
        primary_category=primary,
        overall_severity=overall,
        failure_categories=categories,
    )


def judge_diagnostic_plan(
    skill_name: str,
    version: int,
    aggregated_dicts: List[Dict[str, Any]],
    skill_markdown: str,
    llm: "LLMClient",
) -> tuple[List[str], List[OptimizationItem]]:
    """LLM Skill Diagnostician → root_causes + optimization_plan."""
    # Truncate skill for context window
    skill_excerpt = skill_markdown[:12000]
    user = json.dumps(
        {
            "skill_name": skill_name,
            "version": version,
            "aggregated_failures": aggregated_dicts,
            "skill_markdown_excerpt": skill_excerpt,
        },
        ensure_ascii=False,
    )
    raw = llm.complete(_DIAG_SYSTEM, user)
    data = _extract_json(raw)
    root_causes = [str(x) for x in (data.get("root_causes") or [])]
    plan: List[OptimizationItem] = []
    for item in data.get("optimization_plan") or []:
        plan.append(
            OptimizationItem(
                section_heading=str(item.get("section_heading", "输出要求")),
                action=str(item.get("action", "append")),
                content=str(item.get("content", "")),
                evidence_task_ids=list(item.get("evidence_task_ids") or []),
                category=_parse_category(str(item.get("category", "knowledge"))),
                issue_type=str(item.get("issue_type", "unknown")),
                expected_impact=str(item.get("expected_impact", "")),
            )
        )
    if not plan:
        raise ValueError("LLM diagnostic returned empty optimization_plan")
    return root_causes, plan
