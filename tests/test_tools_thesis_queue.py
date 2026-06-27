#!/usr/bin/env python3
"""离线单元测试：tools/thesis_queue.py"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import thesis_queue as tq  # noqa: E402

SAMPLE_STATE = """
## 1. Active Portfolio Theses (活着的投资逻辑)
| Ticker | Thesis | Confidence | Last Check | Next Trigger | Status |
|--------|--------|------------|------------|--------------|--------|
| PDD | test | C | 2026-06-26 | x | ❌ TRIGGERED (bad) |
| AVGO | test | B | 2026-06-26 | x | ⚠️ Watch (risk) |

## 2. Pending Research Queue (待研究队列)
- [ ] **NVDA**: already queued
- [x] **DONE**: completed item

## 3. Other
"""


def test_parse_active_theses_triggered_and_watch():
    rows = tq.parse_active_theses(SAMPLE_STATE)
    assert len(rows) == 2
    pdd = next(r for r in rows if r["ticker"] == "PDD")
    assert pdd["triggered"]
    avgo = next(r for r in rows if r["ticker"] == "AVGO")
    assert avgo["watch"] and not avgo["triggered"]


def test_parse_pending_queue():
    items = tq.parse_pending_queue(SAMPLE_STATE)
    assert len(items) == 2
    open_items = [i for i in items if not i["done"]]
    assert len(open_items) == 1
    assert open_items[0]["ticker"] == "NVDA"


def test_merge_scan_skips_existing_queue():
    scan = {
        "buy_signals": [
            {"ticker": "NVDA", "grade": "BUY_5%", "reason": "ok", "max_position_pct": 5},
            {"ticker": "MU", "grade": "BUY_8%", "reason": "strong", "max_position_pct": 8},
        ],
        "watch_signals": [],
    }
    suggestions = tq.merge_scan_suggestions(scan, {"NVDA"}, {"AVGO"})
    tickers = [s["ticker"] for s in suggestions]
    assert "NVDA" not in tickers
    assert "MU" in tickers


def test_build_action_plan_priority():
    state = {
        "theses": tq.parse_active_theses(SAMPLE_STATE),
        "queue": tq.parse_pending_queue(SAMPLE_STATE),
        "path": "/tmp/state.md",
    }
    scan = {
        "buy_signals": [{"ticker": "MU", "grade": "BUY_8%", "reason": "x", "max_position_pct": 8}],
        "watch_signals": [],
    }
    plan = tq.build_action_plan(state, scan)
    assert len(plan["triggered_theses"]) == 1
    assert plan["research_now"][0]["ticker"] == "PDD"
    assert plan["research_now"][0]["priority"] == 100


def test_format_suggest_md_contains_mu():
    plan = {
        "scan_suggestions": [
            {
                "ticker": "MU",
                "priority": 8,
                "suggested_note": "portfolio_scan BUY_8%",
            }
        ],
        "research_now": [],
    }
    md = tq.format_suggest_md(plan)
    assert "MU" in md
    assert "portfolio_scan" in md


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
