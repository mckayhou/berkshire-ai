#!/usr/bin/env python3
"""repair_decision_stances：action↔stance 历史修复。"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import decision_log as dl  # noqa: E402
import repair_decision_stances as repair  # noqa: E402


def _hold_hot(**kw):
    base = dict(
        ticker="HOT",
        date="2026-07-06",
        scores={"duan": 0.90, "buffett": 0.88, "munger": 0.86, "lilu": 0.87},
        price_anchor=100.0,
        thesis="t",
        kill_condition="k",
        action="hold",
        horizon_days=20,
    )
    base.update(kw)
    return dl.DecisionRecord(**base)


def test_scale_scores_to_mean_hits_target():
    scores = {"duan": 0.9, "buffett": 0.9, "munger": 0.9, "lilu": 0.9}
    out = repair.scale_scores_to_mean(scores, 0.80)
    assert abs(sum(out.values()) / 4 - 0.80) < 1e-3
    assert all(0.0 <= v <= 1.0 for v in out.values())


def test_plan_repair_clip_hold():
    rec = _hold_hot()
    assert dl.action_stance_gaps(rec)
    plan = repair.plan_repair(rec, strategy="clip")
    assert plan is not None
    assert plan["after_action"] == "hold"
    assert plan["after_mean_stance"] <= 0.80 + 1e-6
    assert plan["after_complete"] is True
    assert plan["after_gaps"] == []


def test_plan_repair_remap_action():
    rec = _hold_hot()
    plan = repair.plan_repair(rec, strategy="remap-action")
    assert plan is not None
    assert plan["after_action"] == "add"  # stance≥0.80
    assert plan["after_complete"] is True


def test_plan_repair_noop_when_ok():
    rec = dl.DecisionRecord(
        ticker="OK",
        date="2026-01-01",
        scores={p: 0.75 for p in ("duan", "buffett", "munger", "lilu")},
        price_anchor=10.0,
        thesis="t",
        kill_condition="k",
        action="hold",
        horizon_days=20,
    )
    assert repair.plan_repair(rec) is None


def test_repair_all_and_cli_apply(tmp_path, monkeypatch):
    log = tmp_path / "d.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(log))
    hot = _hold_hot()
    ok = dl.DecisionRecord(
        ticker="OK",
        date="2026-01-02",
        scores={p: 0.72 for p in ("duan", "buffett", "munger", "lilu")},
        price_anchor=10.0,
        thesis="t",
        kill_condition="k",
        action="hold",
        horizon_days=20,
    )
    log.write_text(
        json.dumps(hot.to_dict(), ensure_ascii=False)
        + "\n"
        + json.dumps(ok.to_dict(), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    # dry-run
    assert repair.main([]) == 0
    rows = dl.load_decisions()
    assert dl.action_stance_gaps(rows[0])  # 未写盘

    # apply
    assert repair.main(["--apply"]) == 0
    rows2 = dl.load_decisions()
    assert len(rows2) == 2
    assert not dl.action_stance_gaps(rows2[0])
    assert dl.is_research_complete(rows2[0])
    assert "stance-repair" in (rows2[0].note or "")
    # backup exists
    baks = list(tmp_path.glob("d.jsonl.bak-stance-repair.*"))
    assert baks


def test_suggest_action_bands():
    assert repair.suggest_action_for_stance(0.90) == "add"
    assert repair.suggest_action_for_stance(0.75) == "hold"
    assert repair.suggest_action_for_stance(0.60) == "watch"
    assert repair.suggest_action_for_stance(0.30) == "reduce"
