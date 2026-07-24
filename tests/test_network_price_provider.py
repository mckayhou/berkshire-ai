#!/usr/bin/env python3
"""离线单元测试：NetworkPriceProvider（src/realized_feedback.py）。

全程用可注入的 mock fetcher，绝不连网络。覆盖：
- _norm_date：YYYYMMDD / YYYY-MM-DD / 带时间 / 非法
- 精确命中、缓存只取一次、非交易日回退到前一交易日
- 关闭回退、整段无数据/取数失败 → KeyError
- close 为字符串/None/空串的健壮解析
- 与 realized_scores_via_provider 串联
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from decision_log import DecisionRecord  # noqa: E402
from realized_feedback import (  # noqa: E402
    NetworkPriceProvider,
    _norm_date,
    realized_scores_via_provider,
)


def _ok(bars):
    return {"ok": True, "data": bars, "error": None}


# --------------------------- _norm_date ---------------------------
def test_norm_date_formats():
    assert _norm_date("20240105") == "2024-01-05"
    assert _norm_date("2024-01-05") == "2024-01-05"
    assert _norm_date("2024-01-05 00:00:00") == "2024-01-05"
    assert _norm_date("bad") is None
    assert _norm_date("") is None


# --------------------------- 取数 + 缓存 ---------------------------
def test_exact_hit_and_cache_fetches_once():
    calls = []

    def fetcher(code, limit):
        calls.append((code, limit))
        return _ok([
            {"date": "2024-01-03", "close": "10.0"},
            {"date": "2024-01-04", "close": "11.0"},
        ])

    p = NetworkPriceProvider(fetcher=fetcher)
    assert p.get_price("AAPL", "2024-01-04") == 11.0
    assert p.get_price("AAPL", "2024-01-03") == 10.0
    assert len(calls) == 1  # 同一 ticker 只取一次（内存缓存）


def test_fallback_to_prior_trading_day():
    def fetcher(code, limit):
        return _ok([
            {"date": "2024-01-05", "close": 20.0},  # 周五
            {"date": "2024-01-08", "close": 22.0},  # 周一
        ])

    p = NetworkPriceProvider(fetcher=fetcher)
    # 周六请求 → 回退到周五收盘
    assert p.get_price("X", "2024-01-06") == 20.0
    # 周一之后某节假日 → 回退到周一
    assert p.get_price("X", "2024-01-09") == 22.0


def test_fallback_disabled_raises():
    def fetcher(code, limit):
        return _ok([{"date": "2024-01-05", "close": 20.0}])

    p = NetworkPriceProvider(fetcher=fetcher, fallback_to_prior=False)
    with pytest.raises(KeyError):
        p.get_price("X", "2024-01-06")


def test_no_prior_before_requested_date_raises():
    def fetcher(code, limit):
        return _ok([{"date": "2024-01-05", "close": 20.0}])

    p = NetworkPriceProvider(fetcher=fetcher)
    with pytest.raises(KeyError):
        p.get_price("X", "2024-01-01")  # 早于最早 bar，无可回退


def test_empty_or_failed_fetch_raises():
    p_fail = NetworkPriceProvider(fetcher=lambda c, l: {"ok": False, "data": None})
    with pytest.raises(KeyError):
        p_fail.get_price("X", "2024-01-05")

    p_empty = NetworkPriceProvider(fetcher=lambda c, l: _ok([]))
    with pytest.raises(KeyError):
        p_empty.get_price("X", "2024-01-05")


def test_yahoo_fallback_when_primary_empty(monkeypatch):
    """主链空时可用 yahoo_fallback=True + 注入 _yahoo_chart_series。"""
    import realized_feedback as rf

    monkeypatch.setattr(
        rf,
        "_yahoo_chart_series",
        lambda ticker, range_="6mo": {"2024-03-01": 42.0},
    )
    p = NetworkPriceProvider(
        fetcher=lambda c, l: {"ok": False, "data": None},
        yahoo_fallback=True,
    )
    assert p.get_price("TSM", "2024-03-01") == 42.0
    # 注入 fetcher 默认关 Yahoo
    p_off = NetworkPriceProvider(fetcher=lambda c, l: {"ok": False, "data": None})
    with pytest.raises(KeyError):
        p_off.get_price("TSM", "2024-03-01")


def test_robust_close_parsing_skips_bad_bars():
    def fetcher(code, limit):
        return _ok([
            {"date": "2024-01-03", "close": None},
            {"date": "2024-01-04", "close": ""},
            {"date": "2024-01-05", "close": "abc"},
            {"date": "2024-01-08", "close": "15.5"},
        ])

    p = NetworkPriceProvider(fetcher=fetcher)
    assert p.get_price("X", "2024-01-08") == 15.5
    # 坏 bar 全跳过；请求 01-04 回退也只能落到 01-08 之前无有效 → 无 prior 抛错
    with pytest.raises(KeyError):
        p.get_price("X", "2024-01-04")


def test_fetcher_exception_is_swallowed():
    def boom(code, limit):
        raise RuntimeError("network down")

    p = NetworkPriceProvider(fetcher=boom)
    with pytest.raises(KeyError):  # 异常 → 空序列 → KeyError，不向上抛 RuntimeError
        p.get_price("X", "2024-01-05")


# --------------------------- 与收益评分串联 ---------------------------
def test_integration_with_realized_scores_via_provider():
    def fetcher(code, limit):
        data = {
            "AAPL": [{"date": "2024-02-01", "close": 110.0}],
            "SPY": [{"date": "2024-02-01", "close": 101.0}],
        }
        return _ok(data.get(code.upper(), []))

    provider = NetworkPriceProvider(fetcher=fetcher)
    decision = DecisionRecord(
        ticker="AAPL",
        date="2024-01-01",
        scores={"buffett": 0.8},
        price_anchor=100.0,
        benchmark="SPY",
        benchmark_anchor=100.0,
    )
    scores, stats = realized_scores_via_provider(decision, "2024-02-01", provider)
    # 标的 +10%，基准 +1% → alpha ≈ +9%
    assert stats.raw_return == pytest.approx(0.10, abs=1e-9)
    assert stats.alpha == pytest.approx(0.09, abs=1e-9)
    assert "buffett" in scores


def test_disk_cache_hits_without_second_fetch(tmp_path):
    calls = []

    def fetcher(code, limit):
        calls.append(code)
        return _ok([{"date": "2024-01-03", "close": "10.0"}])

    cache_dir = tmp_path / "cache"
    p = NetworkPriceProvider(fetcher=fetcher, disk_cache_dir=str(cache_dir))
    assert p.get_price("AAPL", "2024-01-03") == 10.0
    assert len(calls) == 1

    p2 = NetworkPriceProvider(fetcher=fetcher, disk_cache_dir=str(cache_dir))
    assert p2.get_price("AAPL", "2024-01-03") == 10.0
    assert len(calls) == 1  # 磁盘缓存命中，不再 fetch
