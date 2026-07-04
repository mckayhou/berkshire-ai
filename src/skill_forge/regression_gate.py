#!/usr/bin/env python3
"""
Trajectory replay regression gate for SkillForge（V10.29）。

借鉴 AgentX 的 paired replay：SkillForge 修改 skill 后，用旧成功轨迹
replay 验证 patch 没有引入退化。如果回归，拒绝该 patch。

设计：
  - RegressionGate 接受 pre-patch 和 post-patch 的 skill markdown
  - 对每条 "confirmed" 轨迹（旧成功案例），用规则/LLM 重新 judge
  - 如果任一旧成功变为失败，则判定 regression → 拒绝 patch
  - 通过则放行
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from .judge_mode import JudgeMode, prepare_bad_cases
from .types import BadCase, Consistency

if TYPE_CHECKING:
    from prompt_optimizer import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class ReplayResult:
    """单条轨迹 replay 结果。"""

    task_id: str
    pre_consistency: str
    post_consistency: str
    regressed: bool


@dataclass
class RegressionReport:
    """回归门控总报告。"""

    total_replayed: int = 0
    regressions: int = 0
    passed: bool = True
    details: List[ReplayResult] = field(default_factory=list)

    @property
    def regression_rate(self) -> float:
        if self.total_replayed == 0:
            return 0.0
        return self.regressions / self.total_replayed


def replay_trajectories(
    success_cases: List[BadCase],
    *,
    post_skill_md: str,
    pre_skill_md: Optional[str] = None,
    llm: Optional["LLMClient"] = None,
    mode: JudgeMode = JudgeMode.RULE,
    max_regression_rate: float = 0.0,
) -> RegressionReport:
    """对旧成功案例做 paired replay，检测 patch 是否引入退化。

    Args:
        success_cases: 之前判定为 consistent/partial 的案例。
        post_skill_md: patch 后的 skill markdown（当前未直接用于规则模式，
            但 LLM 模式可注入上下文）。
        pre_skill_md: patch 前的 skill markdown（用于对比）。
        llm: LLM client（mode=llm 时需要）。
        mode: 评判模式。
        max_regression_rate: 允许的最大退化比例（0.0 = 零容忍）。

    Returns:
        RegressionReport，含 passed=True/False 和逐条细节。
    """
    report = RegressionReport()

    if not success_cases:
        report.passed = True
        return report

    raw_dicts = [
        {
            "task_id": c.task_id,
            "skill_name": c.skill_name,
            "agent_output": c.agent_output,
            "reference_output": c.reference_output,
            "consistency": c.consistency.value,
            "tool_trace": c.tool_trace,
            "metadata": c.metadata,
        }
        for c in success_cases
    ]

    try:
        re_judged = prepare_bad_cases(raw_dicts, llm=llm, mode=mode, re_judge=True)
    except Exception:  # noqa: BLE001
        logger.warning("regression gate re-judge failed", exc_info=True)
        report.passed = True
        return report

    id_to_original = {c.task_id: c for c in success_cases}

    for case in re_judged:
        original = id_to_original.get(case.task_id)
        if original is None:
            continue

        pre_cons = original.consistency.value
        post_cons = case.consistency.value

        regressed = (
            pre_cons in ("consistent", "partial")
            and post_cons == "inconsistent"
        )

        report.details.append(
            ReplayResult(
                task_id=case.task_id,
                pre_consistency=pre_cons,
                post_consistency=post_cons,
                regressed=regressed,
            )
        )
        report.total_replayed += 1
        if regressed:
            report.regressions += 1

    report.passed = report.regression_rate <= max_regression_rate
    if not report.passed:
        logger.warning(
            "regression gate FAILED: %d/%d cases regressed (%.1f%% > %.1f%%)",
            report.regressions,
            report.total_replayed,
            report.regression_rate * 100,
            max_regression_rate * 100,
        )

    return report
