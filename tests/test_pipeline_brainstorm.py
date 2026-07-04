#!/usr/bin/env python3
"""V10.29 pipeline brainstorm integration test."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from decision_log import DecisionRecord  # noqa: E402
from pipeline import run_full_cycle  # noqa: E402
from prompt_optimizer import StaticLLMClient  # noqa: E402


def test_pipeline_use_brainstorm():
    """use_brainstorm=True 路径经 EvidenceBrainstormProposer 产出假设。"""
    factor_scan = {
        "ok": True,
        "candidates": [{"ticker": "600519", "score": 0.5, "direction": "long", "note": "q"}],
    }
    d = DecisionRecord(
        ticker="600519",
        date="2026-01-02",
        scores={"duan": 0.8, "buffett": 0.7, "munger": 0.7, "lilu": 0.7},
        price_anchor=100.0,
    )
    out = run_full_cycle(
        d,
        realized_price=110.0,
        persist=False,
        run_rd=True,
        rd_cycles=1,
        dev_rounds=1,
        llm=StaticLLMClient(responses={"*": "P✓✓✓"}),
        factor_scan=factor_scan,
        use_brainstorm=True,
    )
    rd = out["rd"]
    assert rd is not None
    assert rd.total_hypotheses >= 1
