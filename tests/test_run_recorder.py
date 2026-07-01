#!/usr/bin/env python3
"""RunRecorder 测试。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from run_recorder import RunRecord, RunRecorder  # noqa: E402


def test_append_and_load(tmp_path, monkeypatch):
    path = tmp_path / "runs.jsonl"
    monkeypatch.setenv("BERKSHIRE_RUN_LOG", str(path))
    rec = RunRecorder()
    rec.append(RunRecord(run_id="run-1", event="feedback", ticker="AAPL", metrics={"alpha": 0.1}))
    rows = rec.load()
    assert len(rows) == 1
    assert rows[0].ticker == "AAPL"
    assert rows[0].metrics["alpha"] == pytest.approx(0.1)


def test_list_runs_filter(tmp_path, monkeypatch):
    path = tmp_path / "runs.jsonl"
    monkeypatch.setenv("BERKSHIRE_RUN_LOG", str(path))
    rec = RunRecorder()
    rec.append(RunRecord(run_id="r1", event="reflect", ticker="MSFT"))
    rec.append(RunRecord(run_id="r2", event="feedback", ticker="AAPL"))
    assert len(rec.list_runs(event="reflect")) == 1
    assert rec.list_runs(ticker="AAPL")[0].run_id == "r2"


def test_load_run(tmp_path, monkeypatch):
    path = tmp_path / "runs.jsonl"
    monkeypatch.setenv("BERKSHIRE_RUN_LOG", str(path))
    rec = RunRecorder()
    rec.append(RunRecord(run_id="run-xyz", event="optimize", ticker="TSLA"))
    assert rec.load_run("run-xyz").event == "optimize"
    assert rec.load_run("missing") is None
