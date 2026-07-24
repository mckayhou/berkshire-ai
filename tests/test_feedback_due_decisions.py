#!/usr/bin/env python3
"""feedback_due_decisions：到期决策批量反馈。"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import decision_log as dl  # noqa: E402
import feedback_due_decisions as fb  # noqa: E402
from experience_store import Experience, ExperienceStore  # noqa: E402
from realized_feedback import StaticPriceProvider  # noqa: E402


def _rec(**kw):
    base = dict(
        ticker="AAA",
        date="2026-01-01",
        scores={"duan": 0.75, "buffett": 0.75, "munger": 0.70, "lilu": 0.72},
        price_anchor=100.0,
        thesis="t",
        kill_condition="k",
        action="hold",
        horizon_days=20,
    )
    base.update(kw)
    return dl.DecisionRecord(**base)


def test_has_experience_mat_and_legacy():
    keys = {("AAA", "2026-01-01", "2026-01-21")}
    assert fb.has_experience(keys, "AAA", "2026-01-01", "2026-01-21")
    assert not fb.has_experience(keys, "AAA", "2026-01-01", "2026-02-01")

    legacy = {("BBB", "2026-01-01", "")}
    assert fb.has_experience(legacy, "BBB", "2026-01-01", "2026-01-21")
    # legacy + another mat → legacy no longer blocks other mats?
    # other_mats non-empty → legacy does not block
    mixed = {("BBB", "2026-01-01", ""), ("BBB", "2026-01-01", "2026-01-21")}
    assert fb.has_experience(mixed, "BBB", "2026-01-01", "2026-01-21")
    assert not fb.has_experience(mixed, "BBB", "2026-01-01", "2026-02-01")


def test_run_feedback_pass_dry_and_apply(tmp_path, monkeypatch):
    dlog = tmp_path / "dec.jsonl"
    elog = tmp_path / "exp.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(dlog))
    monkeypatch.setenv("BERKSHIRE_EXPERIENCE_LOG", str(elog))

    due = _rec(ticker="DUE1", horizon_days=10)  # mat 2026-01-11
    future = _rec(ticker="FUT1", date="2026-06-01", horizon_days=60)
    dl.append_decision(due)
    dl.append_decision(future)

    prices = {("DUE1", "2026-01-11"): 110.0}
    provider = StaticPriceProvider(prices)

    summary = fb.run_feedback_pass(
        as_of="2026-02-01",
        decision_log=str(dlog),
        experience_log=str(elog),
        network=False,
        apply=False,
        provider=provider,
    )
    assert summary["n_would_write"] == 1
    assert summary["n_not_due"] == 1
    assert summary["n_written"] == 0
    assert not elog.exists() or elog.read_text() == ""

    summary2 = fb.run_feedback_pass(
        as_of="2026-02-01",
        decision_log=str(dlog),
        experience_log=str(elog),
        network=False,
        apply=True,
        provider=provider,
    )
    assert summary2["n_written"] == 1
    store = ExperienceStore(path=str(elog))
    exps = store.load()
    assert len(exps) == 1
    assert exps[0].ticker == "DUE1"
    assert exps[0].alpha == pytest.approx(0.10)
    assert "mat:2026-01-11" in exps[0].tags
    assert "source:feedback_due" in exps[0].tags

    # 再跑应 skip_existing
    summary3 = fb.run_feedback_pass(
        as_of="2026-02-01",
        decision_log=str(dlog),
        experience_log=str(elog),
        network=False,
        apply=True,
        provider=provider,
    )
    assert summary3["n_written"] == 0
    assert summary3["n_skip_existing"] == 1
    assert len(store.load()) == 1


def test_cli_offline_requires_prices():
    assert fb.main(["--offline", "--as-of", "2026-01-01"]) == 2


def test_cli_apply_with_prices(tmp_path, monkeypatch):
    dlog = tmp_path / "dec.jsonl"
    elog = tmp_path / "exp.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(dlog))
    monkeypatch.setenv("BERKSHIRE_EXPERIENCE_LOG", str(elog))
    dl.append_decision(_rec(ticker="CLI1", horizon_days=5))
    code = fb.main(
        [
            "--as-of",
            "2026-02-01",
            "--offline",
            "--prices",
            json.dumps({"CLI1|2026-01-06": 95.0}),
            "--apply",
            "--log",
            str(dlog),
            "--experience-log",
            str(elog),
        ]
    )
    assert code == 0
    exps = ExperienceStore(path=str(elog)).load()
    assert len(exps) == 1
    assert exps[0].verdict == "refuted"  # -5%
