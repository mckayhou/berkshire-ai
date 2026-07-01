#!/usr/bin/env python3
"""离线测试：R/D 双循环 research_loop（HypothesisProposer + run_rd_cycle）。"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from decision_log import DecisionRecord  # noqa: E402
from experience_store import (  # noqa: E402
    VERDICT_REFUTED,
    Experience,
    ExperienceStore,
    KeywordExperienceRetriever,
)
from graph import BerkshireGraph, Variable  # noqa: E402
from hypothesis import Hypothesis, HypothesisStore  # noqa: E402
from prompt_optimizer import LLMClient  # noqa: E402
from research_loop import (  # noqa: E402
    ExperienceDrivenProposer,
    LLMHypothesisProposer,
    StaticHypothesisProposer,
    run_rd_cycle,
)


def quality(prompt: str) -> float:
    return min(1.0, prompt.count("✓") * 0.25)


class GrowingLLM(LLMClient):
    def __init__(self):
        self.n = 0

    def complete(self, system: str, user: str) -> str:
        self.n += 1
        return "P" + "✓" * self.n


class JsonLineLLM(LLMClient):
    """模拟 LLM 假设生成器：返回一行 JSON。"""

    def complete(self, system: str, user: str) -> str:
        row = {
            "statement": "护城河可能被高估",
            "reasoning": "历史 alpha 为负",
            "justification": "经验支持",
            "falsifiable_condition": "12 个月 ROIC 未改善",
        }
        return json.dumps(row, ensure_ascii=False)


def _graph() -> BerkshireGraph:
    g = BerkshireGraph()
    g.variables.clear()
    g.variables["buffett_prompt"] = Variable(
        name="buffett_prompt", value="P", type="prompt", role="巴菲特"
    )
    return g


def test_decision_record_hypothesis_id_optional():
    r = DecisionRecord(
        ticker="AAPL",
        date="2026-01-01",
        scores={"buffett": 0.8, "munger": 0.7, "duan": 0.6, "lilu": 0.5},
        price_anchor=100.0,
        hypothesis_id="hyp-abc",
    )
    assert r.hypothesis_id == "hyp-abc"
    back = DecisionRecord.from_dict(r.to_dict())
    assert back.hypothesis_id == "hyp-abc"


def test_static_proposer_filters_ticker():
    h1 = Hypothesis(ticker="AAPL", statement="s1")
    h2 = Hypothesis(ticker="MSFT", statement="s2")
    p = StaticHypothesisProposer(items=[h1, h2])
    out = p.propose(ticker="AAPL", recent=[])
    assert len(out) == 1 and out[0].ticker == "AAPL"


def test_experience_driven_proposer_from_refuted():
    exp = Experience(
        ticker="AAPL",
        date="2026-01-01",
        stances={"buffett": 0.9},
        alpha=-0.05,
        realized_base=0.4,
        verdict=VERDICT_REFUTED,
        lesson="高估护城河",
    )
    hyps = ExperienceDrivenProposer().propose(ticker="AAPL", recent=[exp])
    assert len(hyps) == 1
    assert "AAPL" in hyps[0].statement


def test_llm_hypothesis_proposer_parses_json():
    hyps = LLMHypothesisProposer(JsonLineLLM()).propose(ticker="AAPL", recent=[])
    assert len(hyps) == 1
    assert hyps[0].falsifiable_condition


def test_run_rd_cycle_no_proposer_equals_pure_d():
    g = _graph()
    report = run_rd_cycle(
        g, "AAPL", GrowingLLM(), quality, proposer=None, dev_rounds=4, threshold=0.70
    )
    assert report.total_hypotheses == 0
    assert len(report.cycles) == 1
    assert report.final_quality >= 0.70
    assert report.monotonic_non_decreasing


def test_run_rd_cycle_with_proposer_and_stores():
    g = _graph()
    with tempfile.TemporaryDirectory() as tmp:
        exp_store = ExperienceStore(path=os.path.join(tmp, "exp.jsonl"))
        exp_store.append(
            Experience(
                ticker="AAPL",
                date="2025-12-01",
                stances={"buffett": 0.9},
                alpha=-0.08,
                realized_base=0.35,
                verdict=VERDICT_REFUTED,
                lesson="估值过乐观",
            )
        )
        hyp_store = HypothesisStore(path=os.path.join(tmp, "hyp.jsonl"))
        retriever = KeywordExperienceRetriever(exp_store)
        report = run_rd_cycle(
            g,
            "AAPL",
            GrowingLLM(),
            quality,
            proposer=ExperienceDrivenProposer(),
            hypothesis_store=hyp_store,
            experience_store=exp_store,
            retriever=retriever,
            research_cycles=1,
            dev_rounds=4,
            threshold=0.70,
        )
        assert report.total_hypotheses >= 1
        assert len(hyp_store.load()) >= 1
        assert report.monotonic_non_decreasing
