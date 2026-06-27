#!/usr/bin/env python3
"""离线单元测试：tools/portfolio_risk.py"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import portfolio_risk as pr  # noqa: E402


def test_parse_holdings_normalizes():
    h = pr.parse_holdings({"nvda": 25, "CASH": 10})
    assert h["NVDA"] == 25
    assert h["CASH"] == 10


def test_concentration_fail_over_40():
    h = pr.parse_holdings({"NVDA": 45, "MU": 20, "CASH": 35})
    r = pr.check_holdings(h)
    assert not r["ok"]
    codes = [f["code"] for f in r["flags"]]
    assert "concentration_single" in codes


def test_cash_low_warn():
    h = pr.parse_holdings({"NVDA": 50, "MU": 45, "CASH": 5})
    r = pr.check_holdings(h)
    codes = [f["code"] for f in r["flags"]]
    assert "cash_low" in codes


def test_proposed_over_limit():
    h = pr.parse_holdings({"NVDA": 38, "CASH": 62})
    r = pr.check_holdings(h, proposed=("NVDA", 5))
    assert not r["ok"]
    assert any(f["code"] == "proposed_over_limit" for f in r["flags"])


def test_theme_exposure_warn(tmp_path, monkeypatch):
    wl = {"us_ai_chip": ["NVDA", "AMD"], "hk": ["0700.HK"]}
    p = tmp_path / "watchlist.json"
    p.write_text(__import__("json").dumps(wl))
    monkeypatch.setattr(pr, "WATCHLIST_FILE", str(p))
    h = pr.parse_holdings({"NVDA": 30, "AMD": 25, "CASH": 45})
    r = pr.check_holdings(h)
    assert any(f["code"] == "theme_concentration" for f in r["flags"])


def test_high_correlation_warn():
    h = pr.parse_holdings({"0700.HK": 40, "1024.HK": 35, "CASH": 25})
    corr = {"TENCENT/MEITUAN": 0.85}
    r = pr.check_holdings(h, corr_pairs=corr)
    assert any(f["code"] == "high_correlation" for f in r["flags"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
