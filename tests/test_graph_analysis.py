#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from graph import BerkshireGraph, Variable  # noqa: E402
from graph_analysis import (  # noqa: E402
    PromptHeuristicAnalysisRunner,
    mean_master_scores,
    prompt_gradients_from_scores,
)


def test_prompt_heuristic_runner_scores():
    g = BerkshireGraph()
    g.variables["buffett_prompt"].value = "P✓✓"
    runner = PromptHeuristicAnalysisRunner()
    scores = runner.run(g, "600519")
    assert scores["buffett"] == 0.5
    assert mean_master_scores(scores) > 0


def test_prompt_gradients_from_low_buffett():
    g = BerkshireGraph()
    scores = {"duan": 0.9, "buffett": 0.5, "munger": 0.9, "lilu": 0.9}
    grads = prompt_gradients_from_scores(g, scores)
    assert grads["buffett_prompt"].ok is False
