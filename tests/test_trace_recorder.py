#!/usr/bin/env python3
"""trace_recorder 测试。"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trace_recorder import TraceRecorder, record_trace  # noqa: E402


def test_append_and_count(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_TRACE_DIR", str(tmp_path))
    path = record_trace("AAPL", "feedback", score=0.8, notes="test")
    assert path is not None
    rec = TraceRecorder()
    assert rec.count() == 1
    files = rec.list_files()
    assert len(files) == 1
    with open(files[0], encoding="utf-8") as fh:
        data = json.load(fh)
    assert data[0]["ticker"] == "AAPL"
    assert data[0]["phase"] == "feedback"
