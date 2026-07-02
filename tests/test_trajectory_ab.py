#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trajectory_ab import load_tasks, run_ab_report  # noqa: E402

FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "trajectories", "sample_tasks.json"
)


def test_ab_report_coverage_and_evolution():
    tasks = load_tasks(FIXTURE)
    report = run_ab_report(tasks)
    assert report.tasks == 6
    assert report.below_target >= 1
    assert report.diagnosis_coverage_pct >= 90.0
    assert report.v10_evolution_improved >= 1
    assert report.mean_evolution_delta > 0
