#!/usr/bin/env python3
"""离线单元测试：tools/financial_rigor.py

覆盖纯计算函数与安全求值器（无网络、无外部依赖）。
重点保护：精确十进制计算的正确性 + AST 求值器的安全边界。
"""
import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import financial_rigor as fr  # noqa: E402


# ---------------------------------------------------------------------------
# exact / fmt_number
# ---------------------------------------------------------------------------
def test_exact_avoids_float_trap():
    # 0.1 的二进制浮点陷阱：exact 应得到精确的 Decimal('0.1')
    assert fr.exact(0.1) == Decimal("0.1")
    assert fr.exact("1.23") == Decimal("1.23")
    assert fr.exact(Decimal("5")) == Decimal("5")


def test_fmt_number_units():
    assert fr.fmt_number(Decimal("1234.5")) == "1,234.50"
    assert fr.fmt_number(Decimal("2.5e9")) == "2.50B"
    assert fr.fmt_number(Decimal("3.2e12")) == "3.20T"
    assert fr.fmt_number(Decimal("100"), "亿") == "100.00亿"
    # 亿单位下超过万亿
    assert "万亿" in fr.fmt_number(Decimal("20000"), "亿")


# ---------------------------------------------------------------------------
# verify_market_cap
# ---------------------------------------------------------------------------
def test_verify_market_cap_exact_pass():
    assert fr.verify_market_cap(10, 1e9, 1e10) is True  # 偏差 0%


def test_verify_market_cap_large_deviation_fails():
    assert fr.verify_market_cap(10, 1e9, 2e10) is False  # 偏差 50%


def test_verify_market_cap_small_deviation_passes():
    # 偏差 3% → 警告但仍 True
    assert fr.verify_market_cap(10, 1e9, Decimal("1.03e10")) is True


def test_verify_market_cap_zero_reported_no_crash():
    # reported=0 不应除零崩溃
    assert fr.verify_market_cap(10, 1e9, 0) is True


# ---------------------------------------------------------------------------
# verify_valuation
# ---------------------------------------------------------------------------
def test_verify_valuation_ratios():
    res = fr.verify_valuation(price=100, eps=10, bvps=50, dividend=2)
    assert res["PE"] == pytest.approx(10.0)
    assert res["PB"] == pytest.approx(2.0)
    assert res["ROE"] == pytest.approx(20.0)  # eps/bvps*100
    assert res["Dividend_Yield"] == pytest.approx(2.0)


def test_verify_valuation_zero_eps_no_crash():
    res = fr.verify_valuation(price=100, eps=0)
    assert "PE" not in res  # EPS=0 时跳过 PE


# ---------------------------------------------------------------------------
# cross_validate
# ---------------------------------------------------------------------------
def test_cross_validate_consistent():
    res = fr.cross_validate("revenue", {"a": 100, "b": 101, "c": 99}, tolerance_pct=2.0)
    assert res["all_consistent"] is True
    assert res["consensus"] == 100


def test_cross_validate_inconsistent():
    res = fr.cross_validate("revenue", {"a": 100, "b": 200}, tolerance_pct=2.0)
    assert res["all_consistent"] is False


def test_cross_validate_empty_no_crash():
    # 加固点：空输入此前会因空列表取中位数而 IndexError
    res = fr.cross_validate("revenue", {})
    assert res["consensus"] is None
    assert res["all_consistent"] is False


# ---------------------------------------------------------------------------
# benford_check
# ---------------------------------------------------------------------------
def test_benford_small_sample_returns_none():
    assert fr.benford_check([1, 2, 3]) is None  # n < 50


def test_benford_conforming_dataset():
    # 按 Benford 期望比例构造首位数字分布
    values = []
    N = 3000
    for d in range(1, 10):
        count = round(fr._BENFORD[d] * N)
        values.extend([float(d)] * count)  # 首位数字即为 d
    res = fr.benford_check(values)
    assert res is not None
    assert res["is_conforming"] is True


def test_benford_nonconforming_dataset():
    # 全部首位为 1 → 严重偏离
    res = fr.benford_check([1.0] * 200)
    assert res is not None
    assert res["is_conforming"] is False


# ---------------------------------------------------------------------------
# safe_arith_eval —— 正确性
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("expr,expected", [
    ("2 + 3 * 4", 14),
    ("(1 + 2) / 4", 0.75),
    ("2 ** 10", 1024),
    ("7 % 3", 1),
    ("-5 + 2", -3),
    ("510 * 9.11e9", 510 * 9.11e9),
])
def test_safe_arith_eval_correct(expr, expected):
    assert fr.safe_arith_eval(expr) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# safe_arith_eval —— 安全边界（核心保护）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("expr", [
    "__import__('os').system('echo hi')",  # 调用 + 名称
    "os.system('x')",                       # 属性访问
    "abs(-1)",                              # 函数调用
    "a + 1",                                # 自由变量
    "lambda: 1",                            # lambda
    "[1, 2, 3]",                            # 列表字面量
    "True + 1",                             # 布尔（被显式拒绝）
])
def test_safe_arith_eval_rejects_dangerous(expr):
    with pytest.raises((ValueError, SyntaxError)):
        fr.safe_arith_eval(expr)


def test_safe_arith_eval_rejects_huge_power():
    # 加固点：超大幂指数应被拒绝，防止资源耗尽
    with pytest.raises(ValueError):
        fr.safe_arith_eval("9 ** 99999")


def test_exact_calc_returns_none_on_bad_expr():
    assert fr.exact_calc("__import__('os')") is None


def test_exact_calc_returns_value_on_good_expr():
    assert fr.exact_calc("2 + 2") == pytest.approx(4.0)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
