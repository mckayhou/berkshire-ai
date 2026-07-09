#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from signal_proposer import (  # noqa: E402
    CompositeHypothesisProposer,
    FactorScanHypothesisProposer,
    proposer_from_signal_scans,
)


def test_factor_scan_proposer():
    scan = {
        "ok": True,
        "candidates": [
            {"ticker": "600519", "score": 0.42, "direction": "long", "note": "momentum"},
        ],
    }
    p = FactorScanHypothesisProposer(scan)
    hyps = p.propose(ticker="600519", recent=[], k=3)
    assert len(hyps) == 1
    assert hyps[0].ticker == "600519"
    assert "因子" in hyps[0].statement


def test_composite_and_factory():
    factor = {"ok": True, "candidates": [{"ticker": "000001", "score": 1.0, "direction": "long"}]}
    limitup = {
        "ok": True,
        "candidates": [{"ticker": "000002", "limitup_score": 88, "dimensions": {"封板": 90}}],
    }
    comp = proposer_from_signal_scans(factor_scan=factor, limitup_scan=limitup)
    assert isinstance(comp, CompositeHypothesisProposer)
    hyps = comp.propose(ticker="FOCUS", recent=[], k=5)
    tickers = {h.ticker for h in hyps}
    assert "000001" in tickers and "000002" in tickers
