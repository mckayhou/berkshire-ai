#!/usr/bin/env python3
"""factor_screener_bridge + thesis_queue 因子扫描集成测试。"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from ashare_alphagpt.formula_store import save_formula  # noqa: E402
from ashare_alphagpt.screener import run_screen, score_bars  # noqa: E402
import thesis_queue as tq  # noqa: E402


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "symbol", "open", "high", "low", "close", "volume"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _synthetic_csv_rows(symbol: str, n: int = 100) -> list[dict]:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    rows = []
    for i in range(n):
        c = float(close[i])
        rows.append({
            "time": f"2024{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
            "symbol": symbol,
            "open": f"{c - 0.2:.2f}",
            "high": f"{c + 0.5:.2f}",
            "low": f"{c - 0.5:.2f}",
            "close": f"{c:.2f}",
            "volume": f"{rng.integers(1e5, 2e5)}",
        })
    return rows


def test_score_bars_with_formula():
    pytest.importorskip("torch")
    rows = _synthetic_csv_rows("sh.600519", 100)
    bars = [
        {
            "date": r["time"],
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "vol": float(r["volume"]),
        }
        for r in rows
    ]
    hit = score_bars(bars, [0])
    assert hit is not None
    assert "score" in hit


def test_run_screen_from_csv(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    monkeypatch.setenv("BERKSHIRE_DATA_DIR", str(tmp_path))
    formula_path = save_formula([0], formula_str="RET", best_score=1.5)
    _write_csv(
        tmp_path / "daily_ohlcv.csv",
        _synthetic_csv_rows("sh.600519", 100) + _synthetic_csv_rows("sz.000001", 100),
    )
    result = run_screen(formula_path=formula_path, source="csv", min_score=-1.0)
    assert result["ok"] is True
    assert len(result["candidates"]) == 2
    assert result["candidates"][0]["signal"] == "alphagpt_factor"
    assert "thesis_queue_line" in result["candidates"][0]


def test_merge_factor_scan_suggestions():
    scan = {
        "ok": True,
        "candidates": [
            {"ticker": "600519", "score": 0.42, "direction": "long", "note": "test"},
            {"ticker": "NVDA", "score": 0.9, "direction": "long", "note": "skip queued"},
        ],
    }
    out = tq.merge_factor_scan_suggestions(scan, {"NVDA"}, set())
    tickers = [x["ticker"] for x in out]
    assert "600519" in tickers
    assert "NVDA" not in tickers
    assert out[0]["source"] == "factor_screener"


def test_build_action_plan_with_factor_scan():
    state = {
        "theses": [],
        "queue": [],
        "path": "/tmp/state.md",
    }
    factor_scan = {
        "ok": True,
        "candidates": [
            {"ticker": "600519", "score": 0.55, "direction": "long", "note": "factor hit"},
        ],
    }
    plan = tq.build_action_plan(state, factor_scan=factor_scan)
    assert len(plan["factor_suggestions"]) == 1
    assert any(r["ticker"] == "600519" for r in plan["research_now"])
