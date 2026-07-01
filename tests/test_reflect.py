#!/usr/bin/env python3
"""对比反思 reflect 模块测试。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


from decision_log import DecisionRecord  # noqa: E402
from experience_store import (  # noqa: E402
    ExperienceStore,
    experience_from_stats,  # noqa: E402
)
from realized_feedback import ReturnStats  # noqa: E402
from reflect import reflect_ticker  # noqa: E402


def _stats(alpha: float) -> ReturnStats:
    return ReturnStats(
        ticker="AAPL",
        raw_return=alpha,
        benchmark_return=0.0,
        alpha=alpha,
        realized_base=0.5 + alpha * 0.5,
        has_benchmark=False,
    )


def test_reflect_insufficient_data(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_EXPERIENCE_LOG", str(tmp_path / "exp.jsonl"))
    report = reflect_ticker("AAPL")
    assert report.n_experiences == 0
    assert "经验不足" in report.volatility_root_cause


def test_reflect_divergence(tmp_path, monkeypatch):
    exp_log = tmp_path / "exp.jsonl"
    monkeypatch.setenv("BERKSHIRE_EXPERIENCE_LOG", str(exp_log))
    store = ExperienceStore(str(exp_log))
    d = DecisionRecord(
        ticker="AAPL", date="2026-01-01",
        scores={"duan": 0.9, "buffett": 0.8, "munger": 0.7, "lilu": 0.6},
        price_anchor=100.0,
    )
    store.append(experience_from_stats(d, _stats(0.15), lesson="win"))
    d2 = DecisionRecord(
        ticker="AAPL", date="2026-02-01",
        scores={"duan": 0.5, "buffett": 0.5, "munger": 0.5, "lilu": 0.5},
        price_anchor=100.0,
    )
    store.append(experience_from_stats(d2, _stats(-0.12), lesson="loss"))
    report = reflect_ticker("AAPL")
    assert report.n_experiences == 2
    assert report.high_alpha or report.low_alpha
    assert report.suggestions
