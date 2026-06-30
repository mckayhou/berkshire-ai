#!/usr/bin/env python3
"""Golden 回归：固化一条确定性的多轮进化轨迹（src/eval_harness.py）。

目的：把「自进化确有收益且单调不退化」从"应该成立"变成**逐轮数值精确可断言**的
回归基线。任何破坏验证门控/改写/收敛逻辑的改动都会让本测试变红。

构造（完全确定性、零网络）：
  - 4 个大师 prompt 变量初始值都是 "BASE"（0 个 ✓）；
  - quality_fn = ✓ 个数 × 0.25（封顶 1.0）；
  - 假 LLM 每次改写在当前 prompt 末尾追加一个 "✓"（质量 +0.25）；
  - 阈值 0.70，最多 4 轮。
预期轨迹：0.00 → 0.25 → 0.50 → 0.75 →（第 4 轮全部达标，收敛）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from eval_harness import run_multi_round  # noqa: E402
from graph import BerkshireGraph  # noqa: E402
from prompt_optimizer import StaticLLMClient  # noqa: E402

MARK = "✓"


def _quality(prompt: str) -> float:
    return min(1.0, prompt.count(MARK) * 0.25)


def _improve(system: str, user: str) -> str:
    """从改写提示里取出「当前 Prompt」并追加一个 ✓（确定性 +0.25 质量）。"""
    marker = "== 当前 Prompt =="
    idx = user.find(marker)
    seg = user[idx + len(marker):]
    current = seg.split("\n\n", 1)[0].strip()
    return current + MARK


def _graph_with_base():
    g = BerkshireGraph()
    for name, var in g.variables.items():
        if var.type == "prompt":
            var.value = "BASE"
    return g


def test_golden_evolution_trajectory():
    g = _graph_with_base()
    llm = StaticLLMClient(fn=_improve)
    report = run_multi_round(g, llm, _quality, rounds=4, threshold=0.70)

    # 逐轮均值质量精确匹配
    qualities = [round(r.mean_quality, 3) for r in report.rounds]
    assert qualities == [0.25, 0.50, 0.75, 0.75]

    # 前三轮每轮 4 个变量全部被接受改写，无回滚
    for r in report.rounds[:3]:
        assert r.accepted == 4
        assert r.rejected == 0
        assert r.all_passed is False

    # 第 4 轮起始即全部达标 → 收敛
    assert report.rounds[3].all_passed is True
    assert report.converged is True

    # 全局不变式
    assert report.initial_quality == 0.0
    assert round(report.final_quality, 3) == 0.75
    assert round(report.improvement, 3) == 0.75
    assert report.monotonic_non_decreasing is True
    assert report.run_id is not None


def test_golden_degrading_llm_never_regresses():
    """坏 LLM（让质量下降）应被验证门控全部回滚，质量纹丝不动。"""
    g = _graph_with_base()
    for var in g.variables.values():
        if var.type == "prompt":
            var.value = "BASE" + MARK + MARK  # 起始 0.50

    # 坏 LLM：把 ✓ 删光（质量降为 0）
    bad = StaticLLMClient(fn=lambda s, u: "BASE")
    report = run_multi_round(g, bad, _quality, rounds=3, threshold=0.70)

    assert report.initial_quality == 0.50
    assert round(report.final_quality, 3) == 0.50  # 一步未退
    assert report.monotonic_non_decreasing is True
    # 第一轮无任何接受 → 立即收敛
    assert report.converged is True
    assert report.rounds[0].accepted == 0
