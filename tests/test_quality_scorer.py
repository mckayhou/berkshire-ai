#!/usr/bin/env python3
"""quality_scorer 测试。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from decision_log import DecisionRecord  # noqa: E402
from experience_store import ExperienceStore, experience_from_stats  # noqa: E402
from quality_scorer import build_experience_quality_fn  # noqa: E402
from realized_feedback import ReturnStats  # noqa: E402


def _stats(alpha: float) -> ReturnStats:
    return ReturnStats("AAPL", alpha, 0.0, alpha, 0.5 + alpha * 0.5, False)


def test_quality_fn_neutral_without_data():
    fn = build_experience_quality_fn("ZZZZ")
    assert fn("duan_prompt text") == pytest.approx(0.72)


def test_quality_fn_lower_for_miscalibrated(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    monkeypatch.setenv("BERKSHIRE_EXPERIENCE_LOG", str(path))
    store = ExperienceStore(str(path))
    d = DecisionRecord("AAPL", "2026-01-01", {"duan": 0.95, "buffett": 0.5, "munger": 0.5, "lilu": 0.5}, 100.0)
    store.append(experience_from_stats(d, _stats(-0.15), lesson="bad"))
    fn = build_experience_quality_fn("AAPL", store=store)
    duan_q = fn("duan_prompt")
    buff_q = fn("buffett_prompt")
    assert duan_q < buff_q  # duan 高信心被证伪 → 更低质量分
