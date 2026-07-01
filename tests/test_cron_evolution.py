#!/usr/bin/env python3
"""cron_evolution 测试。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cron_evolution import run_cron, run_thesis_tracker  # noqa: E402


def test_thesis_tracker_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_TRACE_DIR", str(tmp_path / "traces"))
    result = run_thesis_tracker()
    assert result.task == "thesis-tracker"
    # 无 holdings 时 portfolio_scan 可能跳过，不应崩溃
    assert isinstance(result.ok, bool)


def test_cron_unknown():
    try:
        run_cron("invalid-task")
        assert False, "should raise"
    except ValueError:
        pass
