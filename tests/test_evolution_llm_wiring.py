#!/usr/bin/env python3
"""run_with_realized_feedback 接入 ∇_LLM 与验证门控。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import decision_log as dl  # noqa: E402
from evolution_loop_v10 import run_with_realized_feedback  # noqa: E402
from graph import MASTER_PREFIXES  # noqa: E402
from prompt_optimizer import StaticLLMClient  # noqa: E402


def _decision(**kw):
    base = dict(
        ticker="AAPL",
        date="2026-01-01",
        scores={"duan": 0.9, "buffett": 0.55, "munger": 0.85, "lilu": 0.6},
        price_anchor=100.0,
        analyses={"buffett": "巴菲特分析：护城河尚可但估值偏贵"},
    )
    base.update(kw)
    return dl.DecisionRecord(**base)


def test_llm_gradient_enriches_underperforming_master():
    llm = StaticLLMClient(responses={
        "*": "- 缺少现金流分析\n- 估值假设过乐观\n- 未讨论竞争格局",
    })
    d = _decision(scores={
        "duan": 0.5, "buffett": 0.95, "munger": 0.5, "lilu": 0.5,
    })
    out = run_with_realized_feedback(
        d,
        realized_price=80.0,
        llm=llm,
        use_llm_gradient=True,
    )
    grads = out["gradients"]
    buffett_grad = next(
        g for n, g in grads.items() if n == "buffett_analysis"
    )
    assert not buffett_grad.ok
    assert any("现金流" in i or "估值" in i for i in buffett_grad.issues)


def test_llm_gradient_disabled_keeps_rule_template():
    d = _decision(scores={
        "duan": 0.5, "buffett": 0.95, "munger": 0.5, "lilu": 0.5,
    })
    out = run_with_realized_feedback(
        d,
        realized_price=80.0,
        llm=StaticLLMClient(responses={"*": "- LLM issue"}),
        use_llm_gradient=False,
    )
    buffett_grad = next(
        g for n, g in out["gradients"].items() if n == "buffett_analysis"
    )
    assert "LLM 批评" not in buffett_grad.text


def test_analyses_fallback_from_note():
    d = dl.DecisionRecord(
        "MSFT", "2026-01-02",
        {p: 0.5 for p in MASTER_PREFIXES},
        price_anchor=400.0,
        note="统一备注：需补充管理层质量讨论",
    )
    llm = StaticLLMClient(responses={"*": "- 管理层章节缺失"})
    out = run_with_realized_feedback(
        d, realized_price=380.0, llm=llm, use_llm_gradient=True,
    )
    assert out["updates"] is not None


def test_use_validation_attaches_scorer(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_EXPERIENCE_LOG", str(tmp_path / "e.jsonl"))
    d = _decision()
    llm = StaticLLMClient(responses={"*": "rewritten prompt"})
    out = run_with_realized_feedback(
        d,
        realized_price=110.0,
        llm=llm,
        use_validation=True,
    )
    assert out["updates"] is not None
