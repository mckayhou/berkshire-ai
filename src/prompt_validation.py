#!/usr/bin/env python3
"""
验证门控的 Prompt 改写（production TextGrad 的关键保障）。

问题
--------------------------------------------------
V10.13 的 `apply_gradient` 会让 LLM 产出一版「改进的」Prompt——但「LLM 自称改进」
不等于「真的更好」。无验证地直接回填 `Variable.value`，多轮下来很容易**prompt 漂移**：
越改越长、越改越偏，甚至退化。

解法（验证引导更新，validation-guided update）
--------------------------------------------------
改写产出候选后，用一个**评分器**在 held-out 评测集上给「旧 Prompt」和「候选 Prompt」
各打一分，只有候选**不劣于旧版 + 最小增益阈值**才接受，否则回滚到旧版。

    old = scorer.score(current)
    cand = scorer.score(candidate)
    accept = cand >= old + min_improvement

工程约束（与 realized_feedback / prompt_optimizer 一致）
--------------------------------------------------
- 评分器经可注入/可 mock 的 `PromptScorer` 获取，核心可离线单测；
- 评分器异常 → 视为「无法验证」→ 保守回滚（不接受），绝不崩链路；
- 默认 `min_improvement=0.0`：要求「严格不劣于」即可接受（含并列）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

try:
    from graph import Gradient, Variable
    from prompt_optimizer import LLMClient, apply_gradient
except ImportError:  # pragma: no cover - 包内导入回退
    from .graph import Gradient, Variable
    from .prompt_optimizer import LLMClient, apply_gradient


# ---------------------------------------------------------------------------
# 评分器：可注入/可 mock（核心引擎不硬连真实分析/网络）
# ---------------------------------------------------------------------------
class PromptScorer:
    """Prompt 评分器抽象。实现 score(prompt) -> float（越大越好）。

    生产实现：用该 Prompt 在一组 held-out 标的上跑大师分析并对输出质量打分。
    测试实现：见 StaticPromptScorer。
    """

    def score(self, prompt: str) -> float:  # pragma: no cover - 抽象
        raise NotImplementedError


class StaticPromptScorer(PromptScorer):
    """离线/测试用评分器：用字典或回调给分，不连网络。

    用法二选一：
      - scores: {prompt_text: score}，未命中返回 default。
      - fn: 可调用 fn(prompt) -> float。
    两者都给时优先 fn。
    """

    def __init__(
        self,
        scores: Optional[dict] = None,
        fn: Optional[Callable[[str], float]] = None,
        default: float = 0.0,
    ):
        self._scores = scores or {}
        self._fn = fn
        self._default = default
        self.calls: list = []

    def score(self, prompt: str) -> float:
        self.calls.append(prompt)
        if self._fn is not None:
            return float(self._fn(prompt))
        return float(self._scores.get(prompt, self._default))


@dataclass
class ValidationResult:
    """一次验证门控改写的结构化结果（控制流读字段，不解析文本）。"""

    accepted: bool
    reason: str                       # accepted / rejected_not_better / no_candidate / scorer_error / gradient_ok
    old_prompt: Optional[str] = None
    new_prompt: Optional[str] = None
    old_score: Optional[float] = None
    new_score: Optional[float] = None

    @property
    def improvement(self) -> Optional[float]:
        if self.old_score is None or self.new_score is None:
            return None
        return self.new_score - self.old_score


def validated_apply_gradient(
    variable: Variable,
    gradient: Gradient,
    llm: LLMClient,
    scorer: PromptScorer,
    *,
    base_prompt: Optional[str] = None,
    min_improvement: float = 0.0,
    examples: Optional[Sequence] = None,
) -> ValidationResult:
    """验证门控的改写：改写 → 评分新旧 → 只有不劣于(含阈值)才接受。

    Args:
        variable / gradient / llm / base_prompt: 同 apply_gradient。
        scorer: PromptScorer（真实或 mock）。
        min_improvement: 接受所需的最小增益（默认 0.0，即「严格不劣于」即接受）。

    Returns:
        ValidationResult。accepted=True 时 new_prompt 为应采用的新 Prompt；
        accepted=False 时应保持旧 Prompt（回滚）。

    不直接修改 variable.value——是否回填由调用方（optimizer）决定。
    评分器异常 → 保守拒绝（reason="scorer_error"），不抛出。
    """
    if gradient is None or gradient.ok:
        return ValidationResult(accepted=False, reason="gradient_ok")

    current = base_prompt if base_prompt is not None else variable.value
    candidate = apply_gradient(
        variable, gradient, llm, base_prompt=current, examples=examples
    )
    if not candidate or candidate == current:
        return ValidationResult(
            accepted=False, reason="no_candidate", old_prompt=current, new_prompt=candidate
        )

    try:
        old_score = scorer.score(current) if current else float("-inf")
        new_score = scorer.score(candidate)
    except Exception:
        # 无法验证 → 保守回滚（不接受），不崩链路
        return ValidationResult(
            accepted=False, reason="scorer_error",
            old_prompt=current, new_prompt=candidate,
        )

    accepted = new_score >= old_score + min_improvement
    return ValidationResult(
        accepted=accepted,
        reason="accepted" if accepted else "rejected_not_better",
        old_prompt=current,
        new_prompt=candidate,
        old_score=old_score,
        new_score=new_score,
    )
