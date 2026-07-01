#!/usr/bin/env python3
"""pipeline.run_full_cycle 测试。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from decision_log import DecisionRecord  # noqa: E402
from pipeline import run_full_cycle  # noqa: E402


def test_full_cycle_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_DECISION_LOG", str(tmp_path / "d.jsonl"))
    monkeypatch.setenv("BERKSHIRE_EXPERIENCE_LOG", str(tmp_path / "e.jsonl"))
    monkeypatch.setenv("BERKSHIRE_RUN_LOG", str(tmp_path / "r.jsonl"))
    monkeypatch.setenv("BERKSHIRE_TRACE_DIR", str(tmp_path / "traces"))

    d = DecisionRecord(
        "AAPL", "2026-01-02",
        {"duan": 0.8, "buffett": 0.7, "munger": 0.6, "lilu": 0.5},
        price_anchor=100.0,
    )
    out = run_full_cycle(d, realized_price=110.0, run_rd=True, rd_cycles=1)
    assert out.get("feedback") is not None
    assert out["feedback"]["stats"].alpha == pytest.approx(0.10)
    assert out.get("rd") is not None
