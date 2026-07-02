#!/usr/bin/env python3
"""trajectory_ab_eval CLI smoke test."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def test_trajectory_ab_eval_cli_default():
    proc = subprocess.run(
        [sys.executable, str(_REPO / "tools" / "trajectory_ab_eval.py"), "--no-evolution"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_trajectory_ab_eval_cli_json():
    tasks = _REPO / "tests" / "fixtures" / "trajectories" / "sample_tasks.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(_REPO / "tools" / "trajectory_ab_eval.py"),
            "--tasks",
            str(tasks),
            "--json",
            "--no-evolution",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert '"diagnosis_coverage_pct"' in proc.stdout
