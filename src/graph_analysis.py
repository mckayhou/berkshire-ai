#!/usr/bin/env python3
"""
图分析重跑层（V10.26）：改写 Prompt 后重新「跑分析」并产出大师 scores。

生产可注入真实 LLM 分析器；测试/离线默认用 Prompt 启发式（与 eval_harness 桩一致）。
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Protocol, runtime_checkable

try:
    from graph import MASTER_PREFIXES, BerkshireGraph
except ImportError:  # pragma: no cover
    from .graph import MASTER_PREFIXES, BerkshireGraph

ScoreFn = Callable[[str], float]


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def default_prompt_score(prompt: str) -> float:
    """离线默认：每个 ✓ +0.25，封顶 1.0（与 test_eval_harness 一致）。"""
    return min(1.0, (prompt or "").count("✓") * 0.25)


def mean_master_scores(scores: Dict[str, float]) -> float:
    if not scores:
        return 0.0
    vals = [_clip01(float(scores.get(p, 0.0))) for p in MASTER_PREFIXES]
    return sum(vals) / len(vals)


def apply_scores_to_graph(graph: BerkshireGraph, scores: Dict[str, float]) -> Dict[str, float]:
    """把大师 scores 写回 graph.scores 与各 analysis 节点。"""
    graph.scores = dict(scores)
    for prefix, score in scores.items():
        node = graph.analysis_node(prefix)
        if node in graph.variables:
            graph.variables[node].score = _clip01(float(score))
    return graph.scores


@runtime_checkable
class AnalysisRunner(Protocol):
    """改写后重跑分析：返回 {duan, buffett, munger, lilu} scores。"""

    def run(self, graph: BerkshireGraph, ticker: str) -> Dict[str, float]: ...


class PromptHeuristicAnalysisRunner:
    """从各大师 prompt 变量推导 scores（零 LLM、可单测）。"""

    def __init__(self, score_fn: Optional[ScoreFn] = None):
        self.score_fn = score_fn or default_prompt_score

    def run(self, graph: BerkshireGraph, ticker: str) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        for prefix in MASTER_PREFIXES:
            pnode = graph.prompt_node(prefix)
            prompt = ""
            if pnode in graph.variables:
                prompt = graph.variables[pnode].value or ""
            scores[prefix] = _clip01(self.score_fn(prompt))
        return apply_scores_to_graph(graph, scores)


class StaticScoresAnalysisRunner:
    """测试用：每次返回固定 scores（不读 prompt）。"""

    def __init__(self, scores: Dict[str, float]):
        self._scores = dict(scores)

    def run(self, graph: BerkshireGraph, ticker: str) -> Dict[str, float]:
        return apply_scores_to_graph(graph, self._scores)


def prompt_gradients_from_scores(
    graph: BerkshireGraph,
    scores: Dict[str, float],
    *,
    prompt_nodes: Optional[list] = None,
) -> Dict:
    """backward(scores) 后只保留 prompt 节点梯度。"""
    all_grads = graph.backward(scores)
    names = prompt_nodes
    if names is None:
        names = [graph.prompt_node(p) for p in MASTER_PREFIXES]
    return {k: v for k, v in all_grads.items() if k in names}
