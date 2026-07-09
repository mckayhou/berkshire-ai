#!/usr/bin/env python3
"""投研效果：DecisionRecord 契约字段 + 后验周报。"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import log_decision  # noqa: E402
import posterior_weekly  # noqa: E402

import decision_log as dl  # noqa: E402
from posterior_report import (  # noqa: E402
    build_posterior_report,
    direction_hit,
    evaluate_decision,
    format_report_markdown,
)
from realized_feedback import StaticPriceProvider  # noqa: E402


def _rec(**kw):
    base = dict(
        ticker="AAPL",
        date="2026-01-01",
        scores={"duan": 0.9, "buffett": 0.8, "munger": 0.7, "lilu": 0.75},
        price_anchor=100.0,
        thesis="护城河宽",
        kill_condition="服务收入失速",
        action="hold",
        horizon_days=20,
        depth="standard",
        skill="investment-research",
    )
    base.update(kw)
    return dl.DecisionRecord(**base)


def test_research_complete_and_gaps():
    full = _rec()
    assert dl.is_research_complete(full)
    assert dl.research_gaps(full) == []
    assert dl.mean_stance(full) == pytest.approx(0.7875)
    assert dl.maturity_date(full) == "2026-01-21"

    bare = dl.DecisionRecord(
        ticker="MSFT",
        date="2026-01-01",
        scores={"duan": 0.5, "buffett": 0.5, "munger": 0.5, "lilu": 0.5},
        price_anchor=400.0,
        horizon_days=None,
    )
    assert not dl.is_research_complete(bare)
    assert set(dl.research_gaps(bare)) >= {"thesis", "kill_condition", "action", "horizon_days"}


def test_legacy_record_roundtrip_defaults(tmp_path, monkeypatch):
    """旧 JSONL 无新字段时仍可加载。"""
    log = tmp_path / "d.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(log))
    old = {
        "ticker": "aapl",
        "date": "2026-01-01",
        "scores": {"duan": 0.9, "buffett": 0.8, "munger": 0.4, "lilu": 0.6},
        "price_anchor": 100.0,
    }
    log.write_text(json.dumps(old) + "\n", encoding="utf-8")
    rows = dl.load_decisions()
    assert len(rows) == 1
    assert rows[0].ticker == "AAPL"
    assert rows[0].horizon_days == dl.DEFAULT_HORIZON_DAYS
    assert rows[0].thesis == ""


def test_direction_hit_rules():
    assert direction_hit(0.8, 0.05) is True
    assert direction_hit(0.8, -0.05) is False
    assert direction_hit(0.2, -0.05) is True
    assert direction_hit(0.5, 0.1) is None  # 中性


def test_posterior_report_offline_hit_rate():
    bull = _rec(ticker="AAPL", scores={p: 0.85 for p in ("duan", "buffett", "munger", "lilu")})
    bear = _rec(
        ticker="WEAK",
        scores={p: 0.25 for p in ("duan", "buffett", "munger", "lilu")},
        action="reduce",
    )
    # maturity 2026-01-21
    prices = {
        "AAPL|2026-01-21": 110.0,  # +10% hit
        "WEAK|2026-01-21": 90.0,  # -10% hit for bearish
    }
    report = build_posterior_report(
        [bull, bear],
        as_of="2026-02-01",
        price_map=prices,
    )
    assert report.n_priced == 2
    assert report.direction_hit_rate == 1.0
    assert report.complete_rate == 1.0
    md = format_report_markdown(report)
    assert "投研后验周报" in md
    assert "AAPL" in md


def test_posterior_not_due_and_missing_price():
    r = _rec(date="2026-06-01", horizon_days=30)
    row = evaluate_decision(r, as_of="2026-06-10")
    assert row.status == "not_due"

    row2 = evaluate_decision(r, as_of="2026-07-10")
    assert row2.status == "due_missing_price"


def test_static_provider_path():
    r = _rec()
    provider = StaticPriceProvider({("AAPL", "2026-01-21"): 105.0})
    row = evaluate_decision(r, as_of="2026-02-01", price_provider=provider)
    assert row.status == "due_priced"
    assert row.raw_return == pytest.approx(0.05)


def test_log_decision_cli_append_and_gaps(tmp_path, monkeypatch):
    log = tmp_path / "dec.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(log))
    code = log_decision.main(
        [
            "append",
            "--ticker",
            "NVDA",
            "--date",
            "2026-07-06",
            "--price",
            "198",
            "--stance",
            "0.88",
            "--thesis",
            "CUDA 护城河",
            "--kill",
            "份额下滑",
            "--action",
            "hold",
            "--horizon",
            "20",
        ]
    )
    assert code == 0
    assert log_decision.main(["gaps"]) == 0
    assert log_decision.main(["list", "--json"]) == 0


def test_posterior_weekly_cli(tmp_path, monkeypatch):
    log = tmp_path / "dec.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(log))
    dl.append_decision(_rec())
    prices = json.dumps({"AAPL|2026-01-21": 110.0})
    code = posterior_weekly.main(
        ["report", "--as-of", "2026-02-01", "--prices", prices, "--json"]
    )
    assert code == 0
