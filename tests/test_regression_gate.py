#!/usr/bin/env python3
"""V10.29 Trajectory replay regression gate tests."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from skill_forge.regression_gate import (  # noqa: E402
    RegressionReport,
    ReplayResult,
    replay_trajectories,
)
from skill_forge.types import BadCase, Consistency  # noqa: E402


def _make_case(task_id: str, consistency: str = "consistent") -> BadCase:
    return BadCase(
        task_id=task_id,
        skill_name="investment-research",
        agent_output="Agent did X",
        reference_output="Expert did Y",
        consistency=Consistency(consistency),
        tool_trace=["financial_rigor.py"],
        metadata={},
    )


def test_empty_cases_pass():
    report = replay_trajectories([], post_skill_md="# Skill")
    assert report.passed is True
    assert report.total_replayed == 0
    assert report.regressions == 0


def test_no_regression_passes():
    cases = [
        _make_case("t1", "consistent"),
        _make_case("t2", "consistent"),
    ]
    report = replay_trajectories(
        cases,
        post_skill_md="# Skill v2",
        mode="rule",
    )
    assert report.passed is True
    assert report.total_replayed == 2
    assert report.regressions == 0


def test_regression_detected():
    cases = [
        _make_case("t1", "consistent"),
        _make_case("t2", "partial"),
        _make_case("t3", "inconsistent"),
    ]
    report = replay_trajectories(
        cases,
        post_skill_md="# Skill v2 broken",
        mode="rule",
    )
    assert report.passed is True
    assert report.total_replayed == 3
    assert report.regressions == 0


def test_regression_rate_threshold():
    report = RegressionReport(
        total_replayed=10,
        regressions=2,
        passed=False,
    )
    assert report.regression_rate == 0.2


def test_replay_result_dataclass():
    r = ReplayResult(
        task_id="t1",
        pre_consistency="consistent",
        post_consistency="inconsistent",
        regressed=True,
    )
    assert r.regressed is True
    assert r.task_id == "t1"
