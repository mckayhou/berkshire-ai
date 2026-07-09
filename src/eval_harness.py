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
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from graph_analysis import AnalysisRunner

try:
    from .graph import BerkshireGraph, Gradient
    from .observability import get_logger, run_context
    from .optimizer import TextualGradientDescent
    from .prompt_optimizer import LLMClient
    from .prompt_validation import StaticPromptScorer
except ImportError:  # pragma: no cover - flat PYTHONPATH=src
    from graph import BerkshireGraph, Gradient
    from observability import get_logger, run_context
    from optimizer import TextualGradientDescent
    from prompt_optimizer import LLMClient
    from prompt_validation import StaticPromptScorer


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
    analysis_scores: Optional[Dict[str, float]] = None  # V10.26 rerun_analysis 时的大师分


@dataclass
class EvolutionReport:
    rounds: List[RoundMetrics] = field(default_factory=list)
    converged: bool = False
    initial_quality: float = 0.0
    run_id: Optional[str] = None
    rerun_analysis: bool = False

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
    run_id: Optional[str] = None,
    retriever: Optional[Any] = None,
    retriever_ticker: Optional[str] = None,
    retriever_k: int = 3,
    rerun_analysis: bool = False,
    analysis_runner: Optional["AnalysisRunner"] = None,
    ticker: str = "",
) -> EvolutionReport:
    """跑多轮验证门控进化，返回逐轮指标 + 是否收敛。

    Args:
        graph: 含 prompt 变量（有初始 value 底稿）的计算图。
        llm: LLMClient（真实或 mock），用于改写。
        quality_fn: prompt → [0,1] 质量分；兼作验证门控 scorer（rerun_analysis=False）。
        rounds: 最大轮数。
        threshold: 达标阈值；全部变量 ≥ threshold 即收敛。
        min_improvement: 验证门控接受所需最小增益。
        prompt_nodes: 仅优化这些节点（None=全部 prompt 变量）。
        run_id: 可选；用于把本次进化的所有日志关联到同一 run（默认自动生成）。
        rerun_analysis: V10.26 — 每轮改写后重跑分析，用 backward(scores) 产梯度。
        analysis_runner: 分析执行器；rerun_analysis 且未传时用 PromptHeuristicAnalysisRunner。
        ticker: rerun_analysis 时传给 analysis_runner 的标的。
    """
    runner = analysis_runner
    if rerun_analysis and runner is None:
        try:
            from .graph_analysis import PromptHeuristicAnalysisRunner
        except ImportError:
            from graph_analysis import PromptHeuristicAnalysisRunner
        runner = PromptHeuristicAnalysisRunner()

    def _run_analysis() -> Optional[Dict[str, float]]:
        if rerun_analysis and runner is not None:
            return dict(runner.run(graph, ticker or "DEMO"))
        return None

    def _mean_quality_from_scores(scores: Dict[str, float]) -> float:
        try:
            from .graph_analysis import mean_master_scores
        except ImportError:
            from graph_analysis import mean_master_scores
        if prompt_nodes:
            prefixes = [
                n[: -len("_prompt")]
                for n in prompt_nodes
                if n.endswith("_prompt")
            ]
            if prefixes:
                vals = [_clip01(float(scores.get(p, 0.0))) for p in prefixes]
                return sum(vals) / len(vals)
        return mean_master_scores(scores)

    def _mean_quality(scores: Optional[Dict[str, float]] = None) -> float:
        if rerun_analysis and runner is not None:
            s = scores if scores is not None else _run_analysis()
            if not s:
                return 0.0
            return _mean_quality_from_scores(s)
        return mean_prompt_quality(graph, quality_fn, prompt_nodes)

    def _build_grads(scores: Optional[Dict[str, float]] = None) -> Dict[str, Gradient]:
        if rerun_analysis and runner is not None:
            try:
                from .graph_analysis import prompt_gradients_from_scores
            except ImportError:
                from graph_analysis import prompt_gradients_from_scores
            s = scores if scores is not None else _run_analysis()
            if not s:
                return {}
            return prompt_gradients_from_scores(graph, s, prompt_nodes=prompt_nodes)
        return build_quality_gradients(graph, quality_fn, threshold, prompt_nodes)

    def _all_passed(
        grads: Dict[str, Gradient],
        scores: Optional[Dict[str, float]] = None,
    ) -> bool:
        if rerun_analysis and scores is not None:
            if prompt_nodes:
                prefixes = [
                    n[: -len("_prompt")]
                    for n in prompt_nodes
                    if n.endswith("_prompt")
                ]
                if prefixes:
                    vals = [_clip01(float(scores.get(p, 0.0))) for p in prefixes]
                    return bool(vals) and all(v >= threshold for v in vals)
            return bool(scores) and all(
                _clip01(float(v)) >= threshold for v in scores.values()
            )
        return bool(grads) and all(g.ok for g in grads.values())

    # 验证门控仍按 prompt 文本打分（改写后 analysis 分在下一轮体现）
    scorer = StaticPromptScorer(fn=quality_fn)
    optimizer = TextualGradientDescent(
        graph,
        llm=llm,
        scorer=scorer,
        min_improvement=min_improvement,
        retriever=retriever,
        retriever_ticker=retriever_ticker,
        retriever_k=retriever_k,
    )
    logger = get_logger("eval_harness")
    report = EvolutionReport(
        initial_quality=_mean_quality(),
        rerun_analysis=bool(rerun_analysis),
    )

    with run_context(run_id) as rid:
        logger.info(
            "evolution_start",
            extra={"event": "evolution_start", "rounds": rounds,
                   "threshold": threshold, "initial_quality": report.initial_quality,
                   "rerun_analysis": rerun_analysis},
        )
        for r in range(1, rounds + 1):
            scores_snapshot = _run_analysis()

            grads = _build_grads(scores_snapshot)
            all_passed = _all_passed(grads, scores_snapshot)
            if all_passed:
                q = _mean_quality(scores_snapshot)
                report.rounds.append(
                    RoundMetrics(r, q, 0, 0, True, analysis_scores=scores_snapshot)
                )
                report.converged = True
                break

            updates = optimizer.step(grads)
            accepted = sum(1 for u in updates if u.get("rewritten"))
            rejected = sum(1 for u in updates if u.get("rewrite_rejected"))

            scores_snapshot = _run_analysis()

            q = _mean_quality(scores_snapshot)
            report.rounds.append(
                RoundMetrics(
                    r, q, accepted, rejected, False, analysis_scores=scores_snapshot
                )
            )
            logger.info(
                "evolution_round",
                extra={"event": "evolution_round", "round": r, "mean_quality": q,
                       "accepted": accepted, "rejected": rejected},
            )
            if accepted == 0:
                # 本轮无任何可接受改写 → 已到验证门控能达到的上限，收敛
                report.converged = True
                break

        logger.info(
            "evolution_end",
            extra={"event": "evolution_end", "final_quality": report.final_quality,
                   "improvement": report.improvement, "converged": report.converged,
                   "monotonic": report.monotonic_non_decreasing},
        )
        report.run_id = rid

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
