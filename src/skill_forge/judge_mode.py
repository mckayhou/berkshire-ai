"""Judge mode resolution and case preparation."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from .bad_case_loader import bad_case_from_dict
from .llm_judge import judge_consistency, resolve_llm_client
from .types import BadCase, Consistency

if TYPE_CHECKING:
    from prompt_optimizer import LLMClient


class JudgeMode(str, Enum):
    RULE = "rule"
    LLM = "llm"
    AUTO = "auto"


def effective_judge_mode(mode: JudgeMode, llm: Optional["LLMClient"]) -> JudgeMode:
    if mode == JudgeMode.AUTO:
        return JudgeMode.LLM if llm is not None else JudgeMode.RULE
    if mode == JudgeMode.LLM and llm is None:
        raise RuntimeError(
            "judge-mode=llm 需要 BERKSHIRE_LLM_API_KEY（或注入 LLMClient）"
        )
    return mode


def prepare_bad_cases(
    raw_cases: List[dict],
    *,
    llm: Optional["LLMClient"] = None,
    mode: JudgeMode = JudgeMode.AUTO,
    re_judge: bool = False,
) -> List[BadCase]:
    """Build BadCase list; optionally LLM-judge consistency when missing or re_judge."""
    resolved_llm = llm if mode != JudgeMode.RULE else None
    if mode == JudgeMode.AUTO and resolved_llm is None:
        resolved_llm = resolve_llm_client()
    eff = effective_judge_mode(mode, resolved_llm)

    out: List[BadCase] = []
    for raw in raw_cases:
        case = bad_case_from_dict(raw)
        needs = re_judge or raw.get("consistency") is None
        if needs and eff == JudgeMode.LLM and resolved_llm is not None:
            j = judge_consistency(
                case.agent_output,
                case.reference_output,
                resolved_llm,
                task_id=case.task_id,
                skill_name=case.skill_name,
                depth=str(case.metadata.get("depth", "standard")),
            )
            case = BadCase(
                task_id=case.task_id,
                skill_name=case.skill_name,
                agent_output=case.agent_output,
                reference_output=case.reference_output,
                consistency=j.consistency,
                tool_trace=case.tool_trace,
                metadata={
                    **case.metadata,
                    "judge_rationale": j.rationale,
                    "judge_mode": "llm",
                },
            )
        elif raw.get("consistency") is None and eff == JudgeMode.RULE:
            case = BadCase(
                task_id=case.task_id,
                skill_name=case.skill_name,
                agent_output=case.agent_output,
                reference_output=case.reference_output,
                consistency=Consistency.INCONSISTENT,
                tool_trace=case.tool_trace,
                metadata={**case.metadata, "judge_mode": "rule_default"},
            )
        out.append(case)
    return out
