#!/usr/bin/env python3
"""V10.29 Multi-source EvidenceBrainstormProposer tests."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from evidence_channels import (  # noqa: E402
    AnomalyScanEvidenceChannel,
    Evidence,
    EvidenceBrainstormProposer,
    ExperienceEvidenceChannel,
    GraphifyEvidenceChannel,
    ReportEvidenceChannel,
    build_brainstorm_proposer,
)
from experience_store import (  # noqa: E402
    Experience,
    ExperienceRetriever,
    KeywordExperienceRetriever,
    ExperienceStore,
)
from hypothesis import Hypothesis, STATUS_OPEN  # noqa: E402


class FakeRetriever:
    def retrieve(self, ticker: str, k: int = 5):
        return [
            Experience(
                ticker=ticker,
                date="2026-01-01",
                stances={"buffett": 0.8},
                alpha=0.05,
                realized_base=0.6,
                verdict="confirmed",
                lesson="Good momentum",
            ),
            Experience(
                ticker=ticker,
                date="2026-01-15",
                stances={"buffett": 0.3},
                alpha=-0.1,
                realized_base=0.4,
                verdict="refuted",
                lesson="Overvalued at entry",
            ),
        ]


def test_experience_channel():
    ch = ExperienceEvidenceChannel(FakeRetriever())
    evidence = ch.collect("600519", k=5)
    assert len(evidence) == 2
    assert evidence[0].channel == "experience"
    assert evidence[0].confidence == 0.8
    assert evidence[1].confidence == 0.3


def test_anomaly_scan_channel():
    scan = {
        "ok": True,
        "candidates": [
            {"ticker": "600519", "score": 0.6, "direction": "long"},
            {"ticker": "000001", "score": -0.2, "direction": "short"},
        ],
    }
    ch = AnomalyScanEvidenceChannel(scan_loader=lambda: scan)
    evidence = ch.collect("600519", k=5)
    assert len(evidence) == 2
    assert evidence[0].ticker == "600519"
    assert evidence[0].confidence == 0.6


def test_anomaly_scan_channel_empty():
    ch = AnomalyScanEvidenceChannel(scan_loader=None)
    assert ch.collect("X") == []

    ch2 = AnomalyScanEvidenceChannel(scan_loader=lambda: {"ok": False})
    assert ch2.collect("X") == []


def test_graphify_channel_missing_file():
    ch = GraphifyEvidenceChannel(graph_json_path="/nonexistent/graph.json")
    assert ch.collect("600519") == []


def test_report_channel():
    def fake_loader(ticker):
        return [f"{ticker} Q3 revenue beat expectations", f"{ticker} expanding margins"]

    ch = ReportEvidenceChannel(report_loader=fake_loader)
    evidence = ch.collect("AAPL", k=3)
    assert len(evidence) == 2
    assert "revenue" in evidence[0].summary
    assert evidence[0].channel == "report"


def test_report_channel_none():
    ch = ReportEvidenceChannel(report_loader=None)
    assert ch.collect("X") == []


def test_brainstorm_proposer_aggregation():
    scan = {
        "ok": True,
        "candidates": [
            {"ticker": "600519", "score": 0.7, "direction": "long"},
        ],
    }
    proposer = EvidenceBrainstormProposer(
        channels=[
            ExperienceEvidenceChannel(FakeRetriever()),
            AnomalyScanEvidenceChannel(scan_loader=lambda: scan),
        ],
        min_confidence=0.3,
    )
    hyps = proposer.propose(ticker="600519", recent=[], k=5)
    assert len(hyps) >= 2
    assert all(isinstance(h, Hypothesis) for h in hyps)
    channels_used = {h.statement.split("]")[0].strip("[") for h in hyps}
    assert "experience" in channels_used or "anomaly_scan" in channels_used


def test_brainstorm_proposer_dedup():
    scan = {
        "ok": True,
        "candidates": [
            {"ticker": "600519", "score": 0.7, "direction": "long"},
            {"ticker": "600519", "score": 0.7, "direction": "long"},
        ],
    }
    proposer = EvidenceBrainstormProposer(
        channels=[AnomalyScanEvidenceChannel(scan_loader=lambda: scan)],
    )
    hyps = proposer.propose(ticker="600519", recent=[], k=5)
    summaries = [h.statement for h in hyps]
    assert len(summaries) == len(set(summaries))


def test_brainstorm_with_base_proposer():
    from research_loop import StaticHypothesisProposer

    base = StaticHypothesisProposer(
        items=[
            Hypothesis(
                ticker="600519",
                statement="Base hypothesis",
                reasoning="From base",
                justification="test",
                falsifiable_condition="test",
                proposed_by="system",
                status=STATUS_OPEN,
            )
        ]
    )
    proposer = EvidenceBrainstormProposer(channels=[], base_proposer=base)
    hyps = proposer.propose(ticker="600519", recent=[], k=3)
    assert len(hyps) == 1
    assert hyps[0].statement == "Base hypothesis"


def test_build_brainstorm_proposer_factory():
    proposer = build_brainstorm_proposer(
        retriever=FakeRetriever(),
        factor_scan_loader=lambda: {"ok": True, "candidates": [{"ticker": "X", "score": 0.5}]},
        min_confidence=0.3,
    )
    hyps = proposer.propose(ticker="X", recent=[], k=5)
    assert len(hyps) >= 1


def test_channel_failure_graceful():
    class BrokenChannel:
        name = "broken"

        def collect(self, ticker, k=5):
            raise RuntimeError("boom")

    proposer = EvidenceBrainstormProposer(
        channels=[BrokenChannel()],
        min_confidence=0.0,
    )
    hyps = proposer.propose(ticker="X", recent=[], k=3)
    assert hyps == []
