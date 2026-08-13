#!/usr/bin/env python3
"""dojo_holdings_bridge offline unit tests."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location(
    "dojo_holdings_bridge", TOOLS / "dojo_holdings_bridge.py"
)
assert _spec and _spec.loader
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


def test_norm_ticker_markets():
    assert bridge._norm_ticker("aapl", "us") == "AAPL"
    assert bridge._norm_ticker("700", "hk") == "0700.HK"
    assert bridge._norm_ticker("0700.HK", "hk") == "0700.HK"
    assert bridge._norm_ticker("600519", "cn") == "600519"


def test_legs_equal_weight_with_cash():
    legs = [
        {"ticker": "AAPL", "market": "us", "shares": 10},
        {"ticker": "700", "market": "hk", "shares": 100},
    ]
    w = bridge.legs_to_weights(legs, equal_weight=True, cash_pct=20)
    assert w["CASH"] == pytest.approx(20.0)
    assert w["AAPL"] == pytest.approx(40.0)
    assert w["0700.HK"] == pytest.approx(40.0)
    assert abs(sum(w.values()) - 100.0) < 0.05


def test_legs_from_market_value():
    legs = [
        {"ticker": "AAPL", "market_value": 300},
        {"ticker": "MSFT", "market_value": 100},
    ]
    w = bridge.legs_to_weights(legs, cash_pct=0)
    assert w["AAPL"] == pytest.approx(75.0)
    assert w["MSFT"] == pytest.approx(25.0)


def test_legs_shares_times_price():
    legs = [{"ticker": "AAPL", "shares": 2}, {"ticker": "MSFT", "shares": 1}]
    w = bridge.legs_to_weights(legs, prices={"AAPL": 100, "MSFT": 200})
    # 200 vs 200 → 50/50
    assert w["AAPL"] == pytest.approx(50.0)
    assert w["MSFT"] == pytest.approx(50.0)


def test_convert_cli_dry_run(tmp_path):
    doc = {
        "id": "demo",
        "name": "Demo",
        "holdings": [
            {"ticker": "GOOG", "market": "us", "shares": 10},
            {"ticker": "0700", "market": "hk", "shares": 5},
        ],
    }
    p = tmp_path / "p.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    code = bridge.main(
        [
            "convert",
            "--portfolio",
            str(p),
            "--equal-weight",
            "--cash",
            "10",
            "--dry-run",
        ]
    )
    assert code == 0


def test_write_and_list(tmp_path):
    root = tmp_path / "portfolio"
    root.mkdir()
    doc = {
        "id": "abc",
        "name": "N",
        "holdings": [{"ticker": "AAPL", "market": "us", "shares": 1}],
    }
    (root / "abc.json").write_text(json.dumps(doc), encoding="utf-8")
    rows = bridge.list_dojo_portfolios(root)
    assert len(rows) == 1
    assert rows[0]["id"] == "abc"

    out = tmp_path / "holdings.json"
    w = bridge.legs_to_weights(bridge._iter_legs(doc), equal_weight=True, cash_pct=0)
    bridge.write_holdings(out, w, source="dojo:abc")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["AAPL"] == pytest.approx(100.0)
    assert loaded["_source"] == "dojo:abc"


def test_decision_record_portfolio_fields():
    import decision_log as dl

    r = dl.DecisionRecord(
        ticker="AAPL",
        date="2026-01-01",
        scores={p: 0.75 for p in ("duan", "buffett", "munger", "lilu")},
        price_anchor=100.0,
        thesis="t",
        kill_condition="k",
        action="hold",
        horizon_days=20,
        portfolio_weight=12.5,
        risk_flags=["theme_ai", "single_high"],
    )
    assert r.portfolio_weight == 12.5
    assert r.risk_flags == ["theme_ai", "single_high"]
    d = r.to_dict()
    r2 = dl.DecisionRecord.from_dict(d)
    assert r2.portfolio_weight == 12.5
    assert r2.risk_flags == ["theme_ai", "single_high"]

    with pytest.raises(ValueError):
        dl.DecisionRecord(
            ticker="X",
            date="2026-01-01",
            scores={"duan": 0.5, "buffett": 0.5, "munger": 0.5, "lilu": 0.5},
            price_anchor=1.0,
            portfolio_weight=120,
        )
