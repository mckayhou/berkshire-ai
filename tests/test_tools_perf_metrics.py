#!/usr/bin/env python3
"""离线单元测试：tools/perf_metrics.py（纯 stdlib 绩效指标）。"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import perf_metrics as pm  # noqa: E402


# ---------------------------------------------------------------------------
# returns_from_prices
# ---------------------------------------------------------------------------
def test_returns_from_prices_basic():
    assert pm.returns_from_prices([100.0, 110.0, 99.0]) == [0.1, -0.1]


def test_returns_from_prices_short_and_zero_guard():
    assert pm.returns_from_prices([]) == []
    assert pm.returns_from_prices([100.0]) == []
    # 起点为 0 的相邻对被跳过，不崩
    assert pm.returns_from_prices([0.0, 5.0]) == []


# ---------------------------------------------------------------------------
# cumulative_return: 求和 vs 累乘
# ---------------------------------------------------------------------------
def test_cumulative_return_sum_default():
    assert pm.cumulative_return([0.1, -0.1, 0.05]) == pytest_approx(0.05)


def test_cumulative_return_compound():
    got = pm.cumulative_return([0.1, 0.1], method="compound")
    assert got == pytest_approx(1.1 * 1.1 - 1.0)


def test_cumulative_return_empty():
    assert pm.cumulative_return([]) == 0.0


# ---------------------------------------------------------------------------
# annualized / volatility / sharpe
# ---------------------------------------------------------------------------
def test_annualized_return_is_mean_times_periods():
    r = [0.01, 0.02, 0.03]
    assert pm.annualized_return(r, periods=252) == pytest_approx(0.02 * 252)


def test_volatility_zero_when_constant():
    assert pm.volatility([0.01, 0.01, 0.01]) == 0.0


def test_volatility_scales_with_sqrt_periods():
    r = [0.0, 0.02, 0.04, 0.06]  # 样本 std 已知
    sd = pm.volatility(r, periods=1)
    assert pm.volatility(r, periods=4) == pytest_approx(sd * math.sqrt(4))


def test_sharpe_zero_volatility_returns_zero():
    assert pm.sharpe([0.01, 0.01, 0.01]) == 0.0


def test_sharpe_sign_positive_for_positive_mean():
    assert pm.sharpe([0.01, 0.02, -0.005, 0.015]) > 0


def test_sharpe_short_series_returns_zero():
    assert pm.sharpe([0.01]) == 0.0


# ---------------------------------------------------------------------------
# information_ratio
# ---------------------------------------------------------------------------
def test_information_ratio_zero_when_equal_to_benchmark():
    r = [0.01, 0.02, 0.03]
    assert pm.information_ratio(r, r) == 0.0


def test_information_ratio_positive_when_beats_benchmark():
    r = [0.02, 0.03, 0.01, 0.04]
    b = [0.01, 0.01, 0.01, 0.01]
    assert pm.information_ratio(r, b) > 0


# ---------------------------------------------------------------------------
# max_drawdown
# ---------------------------------------------------------------------------
def test_max_drawdown_no_drawdown_is_zero():
    assert pm.max_drawdown([0.01, 0.02, 0.03]) == 0.0


def test_max_drawdown_additive_returns():
    # 累计净值（求和）: 0.1, 0.0, -0.1 ；峰值 0.1，谷 -0.1 → 回撤 -0.2
    assert pm.max_drawdown([0.1, -0.1, -0.1]) == pytest_approx(-0.2)


def test_max_drawdown_on_nav():
    assert pm.max_drawdown([100.0, 120.0, 90.0, 110.0], is_nav=True) == pytest_approx(-30.0)


def test_max_drawdown_empty():
    assert pm.max_drawdown([]) == 0.0


# ---------------------------------------------------------------------------
# win_rate
# ---------------------------------------------------------------------------
def test_win_rate():
    assert pm.win_rate([0.1, -0.1, 0.2, 0.0]) == pytest_approx(0.5)
    assert pm.win_rate([]) == 0.0


# ---------------------------------------------------------------------------
# risk_analysis 汇总
# ---------------------------------------------------------------------------
def test_risk_analysis_empty_is_all_zero():
    rep = pm.risk_analysis([])
    assert rep.n == 0
    assert rep.cumulative_return == 0.0
    assert rep.sharpe == 0.0
    assert rep.has_benchmark is False


def test_risk_analysis_with_benchmark_excess():
    r = [0.02, 0.03, 0.01]
    b = [0.01, 0.01, 0.01]
    rep = pm.risk_analysis(r, b, periods=252)
    assert rep.has_benchmark is True
    assert rep.benchmark_cumulative == pytest_approx(0.03)
    assert rep.excess_cumulative == pytest_approx((0.01 + 0.02 + 0.0))
    assert rep.information_ratio > 0
    assert rep.annualized_excess == pytest_approx(((0.01 + 0.02 + 0.0) / 3) * 252)


def test_risk_analysis_cost_reduces_net():
    r = [0.01, 0.01, 0.01]
    rep = pm.risk_analysis(r, cost=0.002, periods=252)
    assert rep.net_cumulative_return == pytest_approx(rep.cumulative_return - 0.002 * 3)
    assert rep.net_annualized_return < rep.annualized_return


def test_risk_analysis_cost_zero_net_equals_gross():
    r = [0.01, -0.02, 0.03]
    rep = pm.risk_analysis(r, cost=0.0)
    assert rep.net_cumulative_return == pytest_approx(rep.cumulative_return)


# ---------------------------------------------------------------------------
# 桥接：PriceProvider + 决策快照（用 StaticPriceProvider 注入，离线）
# ---------------------------------------------------------------------------
class _DictProvider:
    """最小可注入 provider（鸭子类型），未命中抛 KeyError。"""

    def __init__(self, prices):
        self._p = prices

    def get_price(self, ticker, date):
        return self._p[(ticker.upper(), date)]


def test_price_path_from_provider_skips_missing():
    prov = _DictProvider({("AAA", "2024-01-02"): 11.0, ("AAA", "2024-01-04"): 12.0})
    path = pm.price_path_from_provider("AAA", ["2024-01-02", "2024-01-03", "2024-01-04"], prov)
    assert path == [11.0, 12.0]  # 缺失日 2024-01-03 被跳过


def test_analyze_price_path_with_benchmark():
    rep = pm.analyze_price_path([100.0, 110.0, 121.0], [100.0, 105.0, 110.25])
    assert rep.has_benchmark is True
    assert rep.n == 2
    assert rep.cumulative_return == pytest_approx(0.2)


class _Decision:
    """鸭子类型的决策快照（仅含 perf_metrics 用到的字段）。"""

    def __init__(self, ticker, price_anchor, benchmark=None, benchmark_anchor=None):
        self.ticker = ticker
        self.price_anchor = price_anchor
        self.benchmark = benchmark
        self.benchmark_anchor = benchmark_anchor


def test_analyze_decision_builds_curve_from_anchor():
    prov = _DictProvider(
        {
            ("AAA", "2024-02-01"): 110.0,
            ("AAA", "2024-03-01"): 121.0,
            ("SPX", "2024-02-01"): 105.0,
            ("SPX", "2024-03-01"): 110.25,
        }
    )
    dec = _Decision("AAA", 100.0, benchmark="SPX", benchmark_anchor=100.0)
    rep = pm.analyze_decision(dec, ["2024-02-01", "2024-03-01"], prov)
    assert rep.has_benchmark is True
    assert rep.cumulative_return == pytest_approx(0.2)
    # 标的累计 0.2、基准累计 0.1 → 累计超额 0.1
    assert rep.benchmark_cumulative == pytest_approx(0.1)
    assert rep.excess_cumulative == pytest_approx(0.1)


def test_analyze_decision_no_benchmark():
    prov = _DictProvider({("AAA", "2024-02-01"): 110.0})
    dec = _Decision("AAA", 100.0)
    rep = pm.analyze_decision(dec, ["2024-02-01"], prov)
    assert rep.has_benchmark is False
    assert rep.cumulative_return == pytest_approx(0.1)


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
def test_render_markdown_contains_core_rows():
    rep = pm.risk_analysis([0.01, 0.02], [0.0, 0.01], cost=0.001)
    md = pm.render_markdown(rep)
    assert "年化收益" in md
    assert "夏普" in md
    assert "信息比率(IR)" in md  # 有基准
    assert "含成本" in md         # cost>0


def test_to_json_roundtrip_keys():
    rep = pm.risk_analysis([0.01, 0.02])
    j = pm.to_json(rep)
    assert j["n"] == 2
    assert "max_drawdown" in j
    assert "sharpe" in j


# ---------------------------------------------------------------------------
# 轻量 approx（不依赖 pytest.approx 的命名差异，保持本文件自足）
# ---------------------------------------------------------------------------
def pytest_approx(value, abs=1e-9):
    import pytest

    return pytest.approx(value, abs=abs)
