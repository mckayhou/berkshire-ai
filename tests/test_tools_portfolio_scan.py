#!/usr/bin/env python3
"""离线单元测试：tools/portfolio_scan.py 纯逻辑（不触网）。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import portfolio_scan as ps  # noqa: E402


def test_position_hints_buy_grades():
    assert ps.POSITION_HINTS["BUY_8%"]["max_position_pct"] == 8
    assert ps.POSITION_HINTS["BUY_5%"]["stance"] == "看好"
    assert ps.POSITION_HINTS["WATCH"]["max_position_pct"] == 0


def test_flatten_tickers_dedupes():
    wl = {"g1": ["NVDA", "AMD"], "g2": ["NVDA", "MU"]}
    pairs = ps.flatten_tickers(wl)
    tickers = [p[0] for p in pairs]
    assert tickers == ["NVDA", "AMD", "MU"]
    assert pairs[0] == ("NVDA", "g1")


def test_build_signal_record():
    raw = {
        "grade": "BUY_5%",
        "reason": "标准仓（4/6）",
        "advice": "建议5%仓位",
        "momentum": {"close": 100.0, "date": "2026-01-01", "pct_30d": 12.0, "vol_ratio": 2.1},
        "value": {"score": 4, "max": 6, "fund_label": "Q4", "independent_pass": False},
    }
    rec = ps.build_signal_record("NVDA", "us_ai_chip", raw)
    assert rec["ticker"] == "NVDA"
    assert rec["max_position_pct"] == 5
    assert rec["stance"] == "看好"
    assert rec["value_score"] == 4
    assert "note" in rec


def test_summarize_counts():
    results = [
        {"grade": "BUY_8%", "max_position_pct": 8},
        {"grade": "BUY_3%", "max_position_pct": 3},
        {"grade": "WATCH", "max_position_pct": 0},
        {"grade": "SKIP", "max_position_pct": 0},
    ]
    s = ps.summarize(results)
    assert s["scanned"] == 4
    assert s["buy_count"] == 2
    assert s["watch_count"] == 1
    assert s["buy_signals"][0]["max_position_pct"] == 8


def test_summarize_with_risk():
    results = [{"grade": "BUY_5%", "max_position_pct": 5}]
    risk = {"ok": False, "flags": [{"severity": "warn", "code": "cash_low", "message": "low cash"}], "metrics": {}}
    s = ps.summarize(results, risk)
    assert s["risk_ok"] is False
    assert len(s["risk_flags"]) == 1


def test_load_watchlist_group_filter(tmp_path, monkeypatch):
    wl = {"a": ["NVDA"], "b": ["MU"]}
    p = tmp_path / "watchlist.json"
    p.write_text(__import__("json").dumps(wl))
    monkeypatch.setattr(ps, "WATCHLIST_FILE", str(p))
    out = ps.load_watchlist(["a"])
    assert out == {"a": ["NVDA"]}


def test_load_watchlist_bad_group_raises(tmp_path, monkeypatch):
    p = tmp_path / "watchlist.json"
    p.write_text('{"a": ["NVDA"]}')
    monkeypatch.setattr(ps, "WATCHLIST_FILE", str(p))
    with pytest.raises(ValueError, match="未知"):
        ps.load_watchlist(["missing"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
