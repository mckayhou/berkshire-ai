#!/usr/bin/env python3
"""stock_comparison 测试。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from stock_comparison import build_matrix  # noqa: E402


def test_build_matrix_two_tickers():
    md = build_matrix(["AAPL", "MSFT"])
    assert "AAPL" in md
    assert "MSFT" in md
    assert "对决矩阵" in md
    assert "| 维度 |" in md
