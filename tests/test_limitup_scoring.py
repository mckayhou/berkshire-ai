#!/usr/bin/env python3
"""五维打板评分 + limitup_screener_bridge 集成测试（无 torch）。"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import thesis_queue as tq  # noqa: E402
from ashare_alphagpt.limitup_scoring import (  # noqa: E402
    SignalType,
    UnifiedScoringSystem,
    classify_signal_from_bars,
    score_bars_limitup,
    signal_from_bars,
)
from ashare_alphagpt.screener import run_limitup_screen_from_csv  # noqa: E402


def _bars_limit_up(n: int = 30, limit_pct: float = 10.0) -> list[dict]:
    bars = []
    close = 10.0
    for i in range(n - 1):
        bars.append({
            "date": f"2024{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "vol": 1_000_000,
        })
        close += 0.01
    prev = close
    last_close = prev * (1 + limit_pct / 100)
    bars.append({
        "date": "20241230",
        "open": prev * 1.03,
        "high": last_close,
        "low": prev * 1.02,
        "close": last_close,
        "vol": 5_000_000,
    })
    return bars


def test_classify_limit_up_main_board():
    bars = _bars_limit_up(limit_pct=10.0)
    assert classify_signal_from_bars(bars, code="600519") == SignalType.LIMIT_UP


def test_unified_scoring_weights_must_sum_100():
    with pytest.raises(ValueError):
        UnifiedScoringSystem({"signal_strength": 50})


def test_score_bars_limit_up_high_score():
    bars = _bars_limit_up()
    hit = score_bars_limitup("600519", bars)
    assert hit is not None
    assert hit["signal_type"] == SignalType.LIMIT_UP.value
    assert hit["score"] >= 70


def test_signal_from_bars_auction_high_open():
    bars = [
        {"date": "20241228", "open": 10, "high": 10.2, "low": 9.9, "close": 10, "vol": 1e6},
        {"date": "20241229", "open": 10.4, "high": 10.5, "low": 10.2, "close": 10.35, "vol": 1.2e6},
    ]
    sig = signal_from_bars("000001", bars)
    assert sig is not None
    assert sig.signal_type == SignalType.AUCTION_HIGH_OPEN


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "symbol", "open", "high", "low", "close", "volume"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_run_limitup_screen_from_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BERKSHIRE_LIMITUP_SCORE_MIN", "50")
    rows = []
    for sym, code in [("sh.600519", "600519"), ("sz.000001", "000001")]:
        for i, b in enumerate(_bars_limit_up(25)):
            rows.append({
                "time": b["date"],
                "symbol": sym,
                "open": b["open"],
                "high": b["high"],
                "low": b["low"],
                "close": b["close"],
                "volume": b["vol"],
            })
    _write_csv(tmp_path / "daily_ohlcv.csv", rows)
    result = run_limitup_screen_from_csv(min_score=50)
    assert result["ok"] is True
    assert len(result["candidates"]) >= 1
    assert result["candidates"][0]["signal"] == "limitup_scoring"


def test_merge_limitup_scan_suggestions():
    scan = {
        "ok": True,
        "candidates": [
            {"ticker": "600519", "score": 82, "signal_type": "封涨停", "note": "test"},
            {"ticker": "NVDA", "score": 90, "signal_type": "封涨停", "note": "skip"},
        ],
    }
    out = tq.merge_limitup_scan_suggestions(scan, {"NVDA"}, set())
    tickers = [x["ticker"] for x in out]
    assert "600519" in tickers
    assert "NVDA" not in tickers
    assert out[0]["source"] == "limitup_screener"
