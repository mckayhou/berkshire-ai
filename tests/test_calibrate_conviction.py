#!/usr/bin/env python3
"""calibrate_conviction 单元测试。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from calibrate_conviction import calibrate_conviction, offsets_dict  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from experience_store import Experience  # noqa: E402


def _exp(stances, rb=0.6, alpha=0.1):
    return Experience(
        ticker="AAPL",
        date="2026-01-01",
        stances=stances,
        alpha=alpha,
        realized_base=rb,
        verdict="confirmed",
    )


def test_overconfident_master_positive_bias():
    exps = [
        _exp({"duan": 0.9, "buffett": 0.85, "munger": 0.8, "lilu": 0.75}, rb=0.5),
        _exp({"duan": 0.88, "buffett": 0.82, "munger": 0.78, "lilu": 0.72}, rb=0.55),
    ]
    rows = calibrate_conviction(exps)
    duan = next(r for r in rows if r.prefix == "duan")
    assert duan.n == 2
    assert duan.mean_bias > 0
    assert duan.suggested_offset < 0


def test_offsets_dict_skips_empty():
    rows = calibrate_conviction([])
    assert offsets_dict(rows) == {}
