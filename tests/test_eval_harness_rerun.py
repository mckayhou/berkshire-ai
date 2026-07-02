#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from eval_harness import run_multi_round  # noqa: E402
from graph import BerkshireGraph, Variable  # noqa: E402
from graph_analysis import PromptHeuristicAnalysisRunner  # noqa: E402
from prompt_optimizer import LLMClient  # noqa: E402


def quality(prompt: str) -> float:
    return min(1.0, prompt.count("✓") * 0.25)


class GrowingLLM(LLMClient):
    def __init__(self):
        self.n = 0

    def complete(self, system: str, user: str) -> str:
        self.n += 1
        return "P" + "✓" * self.n


def _graph():
    g = BerkshireGraph()
    g.variables["buffett_prompt"].value = "P"
    return g


def test_rerun_analysis_improves_master_scores():
    g = _graph()
    runner = PromptHeuristicAnalysisRunner(score_fn=quality)
    report = run_multi_round(
        g,
        GrowingLLM(),
        quality,
        rounds=6,
        threshold=0.70,
        prompt_nodes=["buffett_prompt"],
        rerun_analysis=True,
        analysis_runner=runner,
        ticker="TEST",
    )
    assert report.rerun_analysis is True
    assert report.final_quality >= 0.70
    assert report.monotonic_non_decreasing is True
    assert report.rounds[-1].analysis_scores is not None
