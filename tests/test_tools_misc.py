#!/usr/bin/env python3
"""离线单元测试：ashare_data / stock_screener / morningstar_fair_value 的纯函数

只覆盖不触网的解析、格式化与信号计算逻辑。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import ashare_data as ad          # noqa: E402
import stock_screener as ss       # noqa: E402
import morningstar_fair_value as mf  # noqa: E402


# ---------------------------------------------------------------------------
# ashare_data._qq_code —— 代码 → 腾讯行情前缀
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("code,expected", [
    ("600519", "sh600519"),
    ("000001", "sz000001"),
    ("300750", "sz300750"),
    ("830799", "bj830799"),
    ("600519.SH", "sh600519"),
    ("000001.SZ", "sz000001"),
])
def test_qq_code(code, expected):
    assert ad._qq_code(code) == expected


# ---------------------------------------------------------------------------
# ashare_data 格式化函数（健壮性：脏输入不崩溃）
# ---------------------------------------------------------------------------
def test_fmt_yi():
    assert ad._fmt_yi(2.5e8) == "2.50亿"
    assert ad._fmt_yi(3.0e4) == "3.00万"
    assert ad._fmt_yi(123) == "123.00"
    assert ad._fmt_yi("-") == "-"
    assert ad._fmt_yi(None) == "-"
    assert ad._fmt_yi("abc") == "abc"   # 非数字原样返回


def test_fmt_pct_and_num():
    assert ad._fmt_pct(1.234) == "1.23%"
    assert ad._fmt_pct("-") == "-"
    assert ad._fmt_pct("x") == "x"
    assert ad._fmt_num(3.14159, 2) == "3.14"
    assert ad._fmt_num(None) == "-"
    assert ad._fmt_num("n/a") == "n/a"


def test_parse_qq_quote_invalid():
    assert ad._parse_qq_quote("") == {}
    assert ad._parse_qq_quote('v_sh1="a~b~c";') == {}  # 字段不足 50


def test_parse_qq_quote_valid():
    fields = ["1"] * 50
    fields[1] = "贵州茅台"
    fields[2] = "600519"
    fields[3] = "1500.00"
    raw = 'v_sh600519="' + "~".join(fields) + '";'
    q = ad._parse_qq_quote(raw)
    assert q["name"] == "贵州茅台"
    assert q["code"] == "600519"
    assert q["price"] == "1500.00"


# ---------------------------------------------------------------------------
# stock_screener.check_momentum
# ---------------------------------------------------------------------------
def _flat_prices(n, close=10.0, vol=100):
    return [
        {"date": f"2026-01-{i:02d}", "close": close, "high": close,
         "low": close, "volume": vol}
        for i in range(1, n + 1)
    ]


def test_check_momentum_insufficient_data():
    assert ss.check_momentum(_flat_prices(60)) is None  # < 61


def test_check_momentum_no_trigger_on_flat():
    m = ss.check_momentum(_flat_prices(61))
    assert m is not None
    assert m["triggered"] is False


def test_check_momentum_triggers_on_breakout_with_volume():
    prices = _flat_prices(61)
    # 最后一天放量突破
    prices[-1] = {"date": "2026-03-03", "close": 20.0, "high": 20.0,
                  "low": 19.0, "volume": 1000}
    for i in range(-5, -1):
        prices[i]["volume"] = 1000
    m = ss.check_momentum(prices)
    assert m["triggered"] is True
    assert m["is_60d_high"] is True
    assert m["vol_ratio"] > 1.5


# ---------------------------------------------------------------------------
# stock_screener.grade_signal
# ---------------------------------------------------------------------------
def _val(score, ind=False, reason=""):
    return {"score": score, "independent_pass": ind, "independent_reason": reason}


def test_grade_signal_skip_when_no_momentum():
    assert ss.grade_signal(None, None)[0] == "SKIP"
    assert ss.grade_signal({"triggered": False}, None)[0] == "SKIP"


def test_grade_signal_watch_when_no_value():
    assert ss.grade_signal({"triggered": True}, None)[0] == "WATCH"


@pytest.mark.parametrize("score,ind,expected", [
    (5, False, "BUY_8%"),
    (4, True, "BUY_8%"),
    (4, False, "BUY_5%"),
    (3, False, "BUY_3%"),
    (0, True, "BUY_3%"),   # 仅独立条件通过
    (0, False, "PASS"),
])
def test_grade_signal_tiers(score, ind, expected):
    m = {"triggered": True}
    assert ss.grade_signal(m, _val(score, ind, "独立"))[0] == expected


# ---------------------------------------------------------------------------
# morningstar_fair_value 纯函数
# ---------------------------------------------------------------------------
def test_stars():
    assert mf._stars(None) == "N/A"
    assert mf._stars("") == "N/A"
    assert mf._stars(4) == "★★★★"
    assert mf._stars("3.0") == "★★★"
    assert mf._stars(0) == ""
    assert mf._stars("abc") == "abc"   # 无法解析原样返回


def test_extract_ticker():
    assert mf.extract_ticker("0P000003MH.NAS.AAPL") == "AAPL"
    assert mf.extract_ticker("") == ""
    assert mf.extract_ticker("SHORT") == "SHORT"  # 不足 3 段原样返回


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
