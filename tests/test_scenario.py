#!/usr/bin/env python3
"""Scenario 抽象层测试（P1-D）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


from graph import BerkshireGraph  # noqa: E402
from scenario import (  # noqa: E402
    DEFAULT_SCENARIO,
    MASTERS,
    SCORE_THRESHOLD,
    TWO_MASTER_DEMO_SCENARIO,
)


def test_default_scenario_matches_four_masters():
    assert DEFAULT_SCENARIO.masters == MASTERS
    assert DEFAULT_SCENARIO.threshold == SCORE_THRESHOLD
    assert len(DEFAULT_SCENARIO.prefixes) == 4


def test_default_graph_node_count_unchanged():
    g = BerkshireGraph()
    assert len(g.variables) == 18
    assert len(g.edges) > 0


def test_two_master_scenario_smaller_graph():
    g = BerkshireGraph(TWO_MASTER_DEMO_SCENARIO)
    assert len(g.variables) == 12  # 3 in + tavily + 2*3 masters + rigor + report
    assert g.scenario.name == "value_pair_demo"


def test_backward_uses_scenario_threshold():
    g = BerkshireGraph(TWO_MASTER_DEMO_SCENARIO)
    scores = {"duan": 0.82, "buffett": 0.82}
    grads = g.backward(scores)
    # threshold 0.80 → avg 0.82 passes
    assert grads["final_report"].ok is True


def test_backward_fails_below_custom_threshold():
    g = BerkshireGraph(TWO_MASTER_DEMO_SCENARIO)
    scores = {"duan": 0.75, "buffett": 0.75}
    grads = g.backward(scores)
    assert grads["final_report"].ok is False
