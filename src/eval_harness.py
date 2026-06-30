#!/usr/bin/env python3
"""
多轮进化循环 + 离线评测台（证明「自进化」确有收益且不退化）。

为什么需要它
--------------------------------------------------
V10.13 让 prompt 能被 LLM 改写，V10.15 给改写加了验证门控。但「能改 + 不劣于」
还需要一个**可复现的证据**：多轮迭代下，prompt 质量是不是单调不降、并收敛？
本模块提供一个**纯离线、可注入**的评测台，把这件事变成可断言的回归测试：

每一轮：
  1) 用 quality_fn 给每个 prompt 变量的当前 value 打分；
  2) 质量 < threshold 的变量生成「未达标」梯度，触发 TextGrad 改写；
  3) 改写经**验证门控**（validated_apply_gradient）：只有候选不劣于旧版才接受；
  4) 记录本轮均值质量与接受数；
  5) 全部达标 / 本轮无任何接受 → 收敛，提前结束。

关键不变式（被测试断言）
--------------------------------------------------
- **单调不降**：因每步都验证门控，均值质量永不回退（坏改写一律回滚）；
- **收敛**：达到阈值或不再有可接受改写即停止。

quality_fn / LLM 均可注入：生产用「在 held-out 标的上跑大师分析并打分」的实现，
测试用确定性桩，整链路零网络。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

try:
    from graph import BerkshireGraph, Gradient
    from optimizer import TextualGradientDescent
    from prompt_optimizer import LLMClient
    from prompt_validation import StaticPromptScorer
except ImportError:  # pragma: no cover - 包内导入回退
    from .graph import BerkshireGraph, Gradient
    from .optimizer import TextualGradientDescent
    from .prompt_optimizer import LLMClient
    from .prompt_validation import StaticPromptScorer


QualityFn = Callable[[str], float]


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _prompt_nodes(graph: BerkshireGraph, only: Optional[List[str]] = None) -> List[str]:
    names = [n for n, v in graph.variables.items() if v.type == "prompt"]
    if only is not None:
        names = [n for n in names if n in only]
    return names


def mean_prompt_quality(
    graph: BerkshireGraph,
    quality_fn: QualityFn,
    prompt_nodes: Optional[List[str]] = None,
) -> float:
    """所有（指定）prompt 变量当前 value 的平均质量。无变量返回 0.0。"""
    names = _prompt_nodes(graph, prompt_nodes)
    if not names:
        return 0.0
    total = sum(_clip01(quality_fn(graph.variables[n].value or "")) for n in names)
    return total / len(names)


def build_quality_gradients(
    graph: BerkshireGraph,
    quality_fn: QualityFn,
    threshold: float,
    prompt_nodes: Optional[List[str]] = None,
) -> Dict[str, Gradient]:
    """按当前质量给每个 prompt 变量构造结构化梯度（quality<threshold → ok=False）。"""
    grads: Dict[str, Gradient] = {}
    for name in _prompt_nodes(graph, prompt_nodes):
        q = _clip01(quality_fn(graph.variables[name].value or ""))
        ok = q >= threshold
        grads[name] = Gradient(
            node=name,
            ok=ok,
            text=f"质量评分 {q:.3f}（阈值 {threshold:.2f}）",
            score=q,
            issues=[] if ok else [f"质量 {q:.3f} 低于阈值 {threshold:.2f}，需改写"],
        )
    return grads


@dataclass
class RoundMetrics:
    round: int
    mean_quality: float          # 本轮结束后的均值质量
    accepted: int                # 本轮被接受的改写数
    rejected: int                # 本轮被验证门控回滚的改写数
    all_passed: bool             # 本轮起始是否所有变量已达标


@dataclass
class EvolutionReport:
    rounds: List[RoundMetrics] = field(default_factory=list)
    converged: bool = False
    initial_quality: float = 0.0

    @property
    def final_quality(self) -> float:
        return self.rounds[-1].mean_quality if self.rounds else self.initial_quality

    @property
    def improvement(self) -> float:
        return self.final_quality - self.initial_quality

    @property
    def monotonic_non_decreasing(self) -> bool:
        """均值质量是否全程单调不降（验证门控的核心保证）。"""
        seq = [self.initial_quality] + [r.mean_quality for r in self.rounds]
        return all(b >= a - 1e-12 for a, b in zip(seq, seq[1:]))


def run_multi_round(
    graph: BerkshireGraph,
    llm: LLMClient,
    quality_fn: QualityFn,
    *,
    rounds: int = 3,
    threshold: float = 0.70,
    min_improvement: float = 0.0,
    prompt_nodes: Optional[List[str]] = None,
) -> EvolutionReport:
    """跑多轮验证门控进化，返回逐轮指标 + 是否收敛。

    Args:
        graph: 含 prompt 变量（有初始 value 底稿）的计算图。
        llm: LLMClient（真实或 mock），用于改写。
        quality_fn: prompt → [0,1] 质量分；同时用作验证门控的评分器。
        rounds: 最大轮数。
        threshold: 达标阈值；全部变量 ≥ threshold 即收敛。
        min_improvement: 验证门控接受所需最小增益。
        prompt_nodes: 仅优化这些节点（None=全部 prompt 变量）。
    """
    scorer = StaticPromptScorer(fn=quality_fn)
    optimizer = TextualGradientDescent(
        graph, llm=llm, scorer=scorer, min_improvement=min_improvement
    )
    report = EvolutionReport(
        initial_quality=mean_prompt_quality(graph, quality_fn, prompt_nodes)
    )

    for r in range(1, rounds + 1):
        grads = build_quality_gradients(graph, quality_fn, threshold, prompt_nodes)
        all_passed = bool(grads) and all(g.ok for g in grads.values())
        if all_passed:
            report.rounds.append(
                RoundMetrics(r, mean_prompt_quality(graph, quality_fn, prompt_nodes),
                             0, 0, True)
            )
            report.converged = True
            break

        updates = optimizer.step(grads)
        accepted = sum(1 for u in updates if u.get("rewritten"))
        rejected = sum(1 for u in updates if u.get("rewrite_rejected"))
        report.rounds.append(
            RoundMetrics(
                r, mean_prompt_quality(graph, quality_fn, prompt_nodes),
                accepted, rejected, False,
            )
        )
        if accepted == 0:
            # 本轮无任何可接受改写 → 已到验证门控能达到的上限，收敛
            report.converged = True
            break

    return report


def render_report(report: EvolutionReport) -> str:
    """渲染逐轮进化轨迹（人读）。"""
    lines = [
        "多轮进化评测",
        "=" * 52,
        f"初始均值质量: {report.initial_quality:.3f}",
    ]
    for rm in report.rounds:
        tag = "（全部达标）" if rm.all_passed else f"接受 {rm.accepted} / 回滚 {rm.rejected}"
        lines.append(f"  第 {rm.round} 轮: 质量 {rm.mean_quality:.3f}  {tag}")
    lines.append("-" * 52)
    lines.append(f"最终质量: {report.final_quality:.3f}  (Δ {report.improvement:+.3f})")
    lines.append(f"收敛: {'是' if report.converged else '否'}  "
                 f"单调不降: {'是' if report.monotonic_non_decreasing else '否'}")
    return "\n".join(lines)
