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
    # hold 带宽 mean_stance ≤ 0.80；默认分项均值 0.75，落在合法区
    base = dict(
        ticker="AAPL",
        date="2026-01-01",
        scores={"duan": 0.80, "buffett": 0.78, "munger": 0.70, "lilu": 0.72},
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
    assert dl.mean_stance(full) == pytest.approx(0.75)
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


def test_action_stance_bands():
    """hold 过自信 / buy 不够多 / watch 越界 → 契约不完整。"""
    overconfident_hold = _rec(
        scores={p: 0.87 for p in ("duan", "buffett", "munger", "lilu")},
        action="hold",
    )
    assert not dl.is_research_complete(overconfident_hold)
    assert any(g.startswith("action_stance:hold_mean_gt") for g in dl.research_gaps(overconfident_hold))

    weak_buy = _rec(
        scores={p: 0.60 for p in ("duan", "buffett", "munger", "lilu")},
        action="buy",
    )
    assert any(g.startswith("action_stance:buy_mean_lt") for g in dl.research_gaps(weak_buy))

    ok_add = _rec(
        scores={p: 0.82 for p in ("duan", "buffett", "munger", "lilu")},
        action="add",
    )
    assert dl.action_stance_gaps(ok_add) == []
    assert dl.is_research_complete(ok_add)

    hot_watch = _rec(
        scores={p: 0.90 for p in ("duan", "buffett", "munger", "lilu")},
        action="watch",
    )
    assert any(g.startswith("action_stance:watch_mean_gt") for g in dl.research_gaps(hot_watch))

    assert "0.8" in dl.format_action_stance_rule("hold")
    assert "≥ 0.7" in dl.format_action_stance_rule("buy").replace("0.70", "0.7")


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
    # 高 conviction 必须配 buy/add，否则 action↔stance 门禁会拉低 complete_rate
    bull = _rec(
        ticker="AAPL",
        scores={p: 0.85 for p in ("duan", "buffett", "munger", "lilu")},
        action="add",
    )
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
            "0.75",
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
    assert log_decision.main(["bands"]) == 0

    # hold + 过高 stance → 落盘但 exit 2；--strict 拒绝
    code_warn = log_decision.main(
        [
            "append",
            "--ticker",
            "HOT",
            "--date",
            "2026-07-06",
            "--price",
            "10",
            "--stance",
            "0.90",
            "--thesis",
            "x",
            "--kill",
            "y",
            "--action",
            "hold",
            "--horizon",
            "20",
        ]
    )
    assert code_warn == 2
    code_strict = log_decision.main(
        [
            "append",
            "--strict",
            "--ticker",
            "HOT2",
            "--date",
            "2026-07-06",
            "--price",
            "10",
            "--stance",
            "0.90",
            "--thesis",
            "x",
            "--kill",
            "y",
            "--action",
            "hold",
            "--horizon",
            "20",
        ]
    )
    assert code_strict == 3


def test_posterior_weekly_cli(tmp_path, monkeypatch):
    log = tmp_path / "dec.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(log))
    dl.append_decision(_rec())
    prices = json.dumps({"AAPL|2026-01-21": 110.0})
    code = posterior_weekly.main(
        ["report", "--as-of", "2026-02-01", "--prices", prices, "--json"]
    )
    assert code == 0
