#!/usr/bin/env python3
"""离线评测台测试：证明多轮验证门控进化「单调不降 + 收敛」。

全程确定性桩，零网络。核心断言：
- 好的 LLM（产出越来越优的 prompt）→ 质量逐轮上升、收敛、单调不降；
- 坏的 LLM（产出更差的 prompt）→ 验证门控全回滚、质量不退化、立即收敛；
- 多节点、min_improvement、render 输出。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from eval_harness import (  # noqa: E402
    build_quality_gradients,
    mean_prompt_quality,
    render_report,
    run_multi_round,
)
from graph import BerkshireGraph, Variable  # noqa: E402
from prompt_optimizer import LLMClient  # noqa: E402


# 质量函数：每个 ✓ 记 0.25 分，封顶 1.0；"P" 初始 0 分
def quality(prompt: str) -> float:
    return min(1.0, prompt.count("✓") * 0.25)


class GrowingLLM(LLMClient):
    """每次调用产出比上次多一个 ✓ 的 prompt —— 模拟「确有改进」的改写器。"""

    def __init__(self):
        self.n = 0

    def complete(self, system: str, user: str) -> str:
        self.n += 1
        return "P" + "✓" * self.n


class DegradingLLM(LLMClient):
    """总是产出 0 分 prompt —— 模拟「改坏了」的改写器，应被验证门控拦回。"""

    def complete(self, system: str, user: str) -> str:
        return "WORSE"


def _graph(prompts: dict) -> BerkshireGraph:
    g = BerkshireGraph()
    g.variables.clear()  # 去掉默认预置的四大师 prompt 变量，隔离测试
    for name, value in prompts.items():
        g.variables[name] = Variable(name=name, value=value, type="prompt", role="buffett")
    return g


# --------------------------- helpers ---------------------------
def test_mean_quality_and_gradients():
    g = _graph({"a": "P✓✓", "b": "P"})  # 0.5, 0.0
    assert mean_prompt_quality(g, quality) == 0.25
    grads = build_quality_gradients(g, quality, threshold=0.7)
    assert grads["a"].ok is False and grads["b"].ok is False
    assert grads["a"].score == 0.5


# --------------------------- 收益：单调上升 + 收敛 ---------------------------
def test_good_llm_improves_monotonic_and_converges():
    g = _graph({"buffett_prompt": "P"})  # 初始质量 0
    report = run_multi_round(g, GrowingLLM(), quality, rounds=6, threshold=0.70)

    assert report.initial_quality == 0.0
    # 轨迹：0 → .25 → .5 → .75（达标后收敛）
    qualities = [rm.mean_quality for rm in report.rounds]
    assert qualities[:3] == [0.25, 0.5, 0.75]
    assert report.final_quality >= 0.70
    assert report.converged is True
    assert report.monotonic_non_decreasing is True
    assert report.improvement >= 0.70


# --------------------------- 安全：坏改写不退化 ---------------------------
def test_bad_llm_never_regresses_and_converges_immediately():
    g = _graph({"buffett_prompt": "P✓✓"})  # 初始质量 0.5
    report = run_multi_round(g, DegradingLLM(), quality, rounds=5, threshold=0.99)

    assert report.initial_quality == 0.5
    # 候选 "WORSE"(0) < 旧版(0.5) → 全部回滚，质量保持 0.5
    assert report.final_quality == 0.5
    assert report.monotonic_non_decreasing is True
    assert report.converged is True  # 本轮 0 接受 → 立即收敛
    assert report.rounds[0].accepted == 0
    assert report.rounds[0].rejected == 1
    assert g.variables["buffett_prompt"].value == "P✓✓"  # 未被改坏


# --------------------------- 多节点 ---------------------------
def test_multi_node_evolution():
    g = _graph({"a": "P", "b": "P✓"})  # 0, .25
    report = run_multi_round(g, GrowingLLM(), quality, rounds=8, threshold=0.70)
    # 两个节点最终都应达标
    assert mean_prompt_quality(g, quality) >= 0.70
    assert report.monotonic_non_decreasing is True
    assert report.converged is True


# --------------------------- 已达标：第 0 改写 ---------------------------
def test_already_passing_converges_without_rewrite():
    g = _graph({"a": "P✓✓✓✓"})  # 1.0
    report = run_multi_round(g, GrowingLLM(), quality, rounds=3, threshold=0.7)
    assert report.converged is True
    assert report.rounds[0].all_passed is True
    assert report.rounds[0].accepted == 0


# --------------------------- min_improvement 阻止边际改写 ---------------------------
def test_min_improvement_blocks_marginal_gain():
    g = _graph({"a": "P"})  # 0
    # GrowingLLM 每轮 +0.25；要求最小增益 0.5 → 0.25 不够 → 全回滚 → 不前进
    report = run_multi_round(
        g, GrowingLLM(), quality, rounds=4, threshold=0.99, min_improvement=0.5
    )
    assert report.final_quality == 0.0
    assert report.converged is True
    assert report.rounds[0].accepted == 0


def test_render_report_smoke():
    g = _graph({"a": "P"})
    report = run_multi_round(g, GrowingLLM(), quality, rounds=4, threshold=0.7)
    text = render_report(report)
    assert "多轮进化评测" in text
    assert "单调不降" in text
