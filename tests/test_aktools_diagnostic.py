#!/usr/bin/env python3
"""aktools_diagnostic 离线测试（mock fetch）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import aktools_diagnostic as ad  # noqa: E402


def _mock_fetch(path: str, params: dict):
    if "market_prices" in path:
        return [{"date": "2026-06-01", "close": 150.5, "rsi": 62}]
    if "stock_news" in path:
        return [{"title": "Earnings beat"}, {"title": "New product launch"}]
    if "stock_info" in path:
        return {"name": "Apple Inc", "industry": "Technology"}
    return {}


def test_composite_ok_when_any_section_succeeds(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_ENABLE_AKTOOLS", "1")
    report = ad.composite_diagnostic("AAPL", fetch=_mock_fetch)
    assert report["ok"] is True
    assert report["market"] == "us"
    assert report["sections"]["prices"]["ok"] is True


def test_infer_market_a_share():
    assert ad.infer_market("600519") == "sh"
    assert ad.infer_market("000001") == "sz"
    assert ad.infer_market("0700.HK") == "hk"


def test_render_markdown_contains_sections(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_ENABLE_AKTOOLS", "1")
    report = ad.composite_diagnostic("AAPL", fetch=_mock_fetch)
    md = ad.render_markdown(report)
    assert "技术面" in md
    assert "消息面" in md
    assert "150.5" in md


def test_disabled_returns_error(monkeypatch):
    monkeypatch.delenv("BERKSHIRE_ENABLE_AKTOOLS", raising=False)
    report = ad.composite_diagnostic("AAPL", fetch=_mock_fetch)
    assert report["ok"] is False
