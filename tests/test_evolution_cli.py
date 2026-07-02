#!/usr/bin/env python3
"""evolution_cli 子命令测试。"""
import json
import os
import subprocess
import sys

BERKSHIRE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVO = os.path.join(BERKSHIRE_DIR, "src", "evolution_loop_v10.py")


def _run_cli(*args, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, EVO, *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=merged,
        cwd=BERKSHIRE_DIR,
    )


def test_cli_default_run_example():
    r = _run_cli()
    assert r.returncode == 0
    assert "Graph created" in r.stdout


def test_cli_status(tmp_path, monkeypatch):
    env = {
        "BERKSHIRE_DECISION_LOG": str(tmp_path / "d.jsonl"),
        "BERKSHIRE_EXPERIENCE_LOG": str(tmp_path / "e.jsonl"),
        "BERKSHIRE_RUN_LOG": str(tmp_path / "r.jsonl"),
    }
    r = _run_cli("status", env=env)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "decisions" in data
    assert data["decisions"]["count"] == 0


def test_cli_reflect(tmp_path):
    env = {
        "BERKSHIRE_EXPERIENCE_LOG": str(tmp_path / "e.jsonl"),
        "BERKSHIRE_RUN_LOG": str(tmp_path / "r.jsonl"),
    }
    r = _run_cli("reflect", "AAPL", env=env)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["ticker"] == "AAPL"


def test_cli_optimize(tmp_path):
    env = {
        "BERKSHIRE_EXPERIENCE_LOG": str(tmp_path / "e.jsonl"),
        "BERKSHIRE_RUN_LOG": str(tmp_path / "r.jsonl"),
    }
    r = _run_cli("optimize", "AAPL", "--rounds", "1", env=env)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "evolution" in data
    assert data["evolution"]["rounds"] >= 1


def test_cli_skill_evolve_list():
    r = _run_cli("skill-evolve", "list")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "investment-research" in data["skills"]


def test_cli_skill_evolve_judge_rule():
    fixture = os.path.join(
        BERKSHIRE_DIR, "tests", "fixtures", "skill_forge", "bad_cases.jsonl"
    )
    r = _run_cli("skill-evolve", "judge", fixture, "--judge-mode", "rule")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["strict_cr"] >= 0
