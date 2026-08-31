#!/usr/bin/env python3
"""离线单元测试：tools/capital_flow.py（无网络）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capital_flow as cf  # noqa: E402


def test_norm_code_and_secid():
    assert cf._norm_code("600519.SH") == "600519"
    assert cf._norm_code("sh600519") == "600519"
    assert cf._secid("600519") == "1.600519"
    assert cf._secid("000001") == "0.000001"


def test_score_holders_concentration():
    rows = [
        {"HOLDER_TOTAL_NUM": 90_000, "END_DATE": "2026-06-30"},
        {"HOLDER_TOTAL_NUM": 100_000, "END_DATE": "2026-03-31"},
    ]
    rec = cf.score_holders(rows)
    assert rec["ok"] is True
    assert rec["change_pct"] == -10.0
    assert rec["score"] == 100.0
    assert any("集中" in f for f in rec["flags"])


def test_score_holders_needs_two_periods():
    assert cf.score_holders([{"HOLDER_TOTAL_NUM": 1}])["ok"] is False


def test_score_margin_leverage_up():
    rows = [
        {"RZYE": 1.2e9, "DATE": "2026-08-01"},
        {"RZYE": 1.0e9, "DATE": "2026-07-01"},
    ]
    rec = cf.score_margin(rows)
    assert rec["ok"] is True
    assert rec["change_pct"] == 20.0
    assert rec["score"] == 90.0
    assert any("杠杆" in f for f in rec["flags"])


def test_score_block_premium():
    rows = [{"PREMIUM_RATIO": 8, "TRADE_DATE": "2026-08-01"}] * 3
    rec = cf.score_block(rows)
    assert rec["ok"] is True
    assert rec["avg_premium_pct"] == 8
    assert rec["score"] == 90.0


def test_score_lhb_institution_vs_retail():
    inst = {"NET_AMT": 100, "OPERATEDEPT_NAME": "机构专用", "TRADE_DATE": "2026-08-01"}
    retail = {"NET_AMT": 10, "OPERATEDEPT_NAME": "某某营业部", "TRADE_DATE": "2026-08-01"}
    rec = cf.score_lhb([inst, retail])
    assert rec["ok"] is True
    assert rec["score"] > 50


def test_score_lhb_stale_daily_summary():
    rec = cf.score_lhb(
        [{"TRADE_DATE": "2013-01-28", "TOTAL_NET": -1e8, "TOTAL_BUY": 1e8, "TOTAL_SELL": 2e8}]
    )
    assert rec["ok"] is False
    assert "无近期龙虎榜" in rec["reason"]


def test_score_north_single_period():
    rec = cf.score_north([{"HOLD_SHARES": 1e6, "TRADE_DATE": "2026-06-30"}])
    assert rec["ok"] is False
    assert "仅一期" in rec["reason"]
    assert rec["latest"] == 1e6


def test_score_inst_and_north():
    inst = cf.score_inst(
        [
            {"HOLD_RATIO": 12.0, "END_DATE": "2026-06-30"},
            {"HOLD_RATIO": 10.0, "END_DATE": "2026-03-31"},
        ]
    )
    assert inst["ok"] and inst["score"] == 70.0
    north = cf.score_north(
        [
            {"HOLD_SHARES": 95, "HOLD_DATE": "2026-08-01"},
            {"HOLD_SHARES": 100, "HOLD_DATE": "2026-07-01"},
        ]
    )
    assert north["ok"]
    assert any("减持" in f for f in north["flags"])


def test_combine_partial_modules():
    modules = {
        "holders": {"ok": True, "score": 80, "flags": ["筹码快速集中（户数降超10%）"]},
        "margin": {"ok": False, "reason": "无数据", "flags": []},
    }
    out = cf.combine(modules)
    assert out["ok"] is True
    assert out["n_modules"] == 1
    assert out["score"] == 80
    assert out["signal"] == "偏多"
    assert out["flags"]


def test_combine_all_missing():
    out = cf.combine({"holders": {"ok": False, "flags": []}})
    assert out["ok"] is False
    assert out["signal"] == "缺失"


def test_analyze_uses_injected_fetchers():
    def holders(_code):
        return [
            {"HOLDER_TOTAL_NUM": 80, "END_DATE": "2026-06-30"},
            {"HOLDER_TOTAL_NUM": 100, "END_DATE": "2026-03-31"},
        ]

    def boom(_code):
        raise ConnectionError("offline")

    result = cf.analyze(
        "600519.SH",
        fetchers={
            "holders": holders,
            "margin": boom,
            "block": lambda c: [],
            "lhb": lambda c: [],
            "inst": lambda c: [],
            "north": lambda c: [],
        },
    )
    assert result["code"] == "600519"
    assert result["ok"] is True
    assert result["modules"]["holders"]["ok"] is True
    assert result["modules"]["margin"]["ok"] is False
    assert "ConnectionError" in result["modules"]["margin"]["reason"]


def test_cli_help_exits_zero(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["capital_flow.py", "--help"])
    with pytest.raises(SystemExit) as ei:
        cf.main()
    assert ei.value.code == 0


def test_cli_score_json_offline(monkeypatch, capsys):
    def holders(_code):
        return [
            {"HOLDER_TOTAL_NUM": 80, "END_DATE": "2026-06-30"},
            {"HOLDER_TOTAL_NUM": 100, "END_DATE": "2026-03-31"},
        ]

    monkeypatch.setattr(
        cf,
        "_FETCHERS",
        {
            "holders": (holders, cf.score_holders, "股东户数"),
            "margin": (lambda c: [], cf.score_margin, "融资融券"),
            "block": (lambda c: [], cf.score_block, "大宗交易"),
            "lhb": (lambda c: [], cf.score_lhb, "龙虎榜"),
            "inst": (lambda c: [], cf.score_inst, "机构持仓"),
            "north": (lambda c: [], cf.score_north, "北向资金"),
        },
    )
    monkeypatch.setattr(sys, "argv", ["capital_flow.py", "score", "600519", "--json"])
    with pytest.raises(SystemExit) as ei:
        cf.main()
    assert ei.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["n_modules"] == 1
    assert payload["signal"] == "偏多"
