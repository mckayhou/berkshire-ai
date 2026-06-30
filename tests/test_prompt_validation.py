#!/usr/bin/env python3
"""离线单元测试：验证门控的 Prompt 改写（src/prompt_validation.py + optimizer 集成）。

覆盖：
- StaticPromptScorer：dict / fn 两种模式 + 调用记录
- validated_apply_gradient：接受(更优) / 拒绝(更差,回滚) / 并列接受 / min_improvement 阈值
                            / no_candidate / scorer_error 保守拒绝 / gradient.ok 短路
- TextualGradientDescent 集成：
    * 有 llm + scorer 且候选更优 → 回填 + validation.accepted
    * 有 llm + scorer 但候选更差 → 回滚（保持旧 Prompt）+ rewrite_rejected
    * 仅 llm 无 scorer → 走 V10.13 无验证路径（向后兼容）
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from graph import BerkshireGraph, Gradient, Variable  # noqa: E402
from optimizer import TextualGradientDescent  # noqa: E402
from prompt_optimizer import StaticLLMClient  # noqa: E402
from prompt_validation import (  # noqa: E402
    StaticPromptScorer,
    validated_apply_gradient,
)


def _bad_gradient(text="需要补充估值锚点"):
    return Gradient(node="buffett_prompt", ok=False, text=text, issues=["缺少估值锚点"])


def _good_gradient():
    return Gradient(node="buffett_prompt", ok=True, text="达标", issues=[])


def _prompt_var(name="buffett_prompt", value="你是巴菲特，分析护城河。"):
    return Variable(name=name, value=value, type="prompt", role="buffett")


# --------------------------- StaticPromptScorer ---------------------------
def test_scorer_dict_mode():
    sc = StaticPromptScorer(scores={"a": 1.0, "b": 2.0}, default=-1.0)
    assert sc.score("a") == 1.0
    assert sc.score("missing") == -1.0
    assert sc.calls == ["a", "missing"]


def test_scorer_fn_mode_priority():
    sc = StaticPromptScorer(scores={"a": 1.0}, fn=lambda p: float(len(p)))
    assert sc.score("abc") == 3.0  # fn 优先于 dict


# --------------------------- validated_apply_gradient ---------------------------
def test_validated_accept_when_better():
    var = _prompt_var(value="OLD")
    llm = StaticLLMClient(fn=lambda s, u: "NEW")
    scorer = StaticPromptScorer(scores={"OLD": 0.5, "NEW": 0.9})
    res = validated_apply_gradient(var, _bad_gradient(), llm, scorer, base_prompt="OLD")
    assert res.accepted is True
    assert res.reason == "accepted"
    assert res.new_prompt == "NEW"
    assert res.old_score == 0.5 and res.new_score == 0.9
    assert abs(res.improvement - 0.4) < 1e-9


def test_validated_reject_when_worse():
    var = _prompt_var(value="OLD")
    llm = StaticLLMClient(fn=lambda s, u: "NEW")
    scorer = StaticPromptScorer(scores={"OLD": 0.9, "NEW": 0.5})
    res = validated_apply_gradient(var, _bad_gradient(), llm, scorer, base_prompt="OLD")
    assert res.accepted is False
    assert res.reason == "rejected_not_better"
    assert res.improvement < 0


def test_validated_tie_is_accepted_by_default():
    var = _prompt_var(value="OLD")
    llm = StaticLLMClient(fn=lambda s, u: "NEW")
    scorer = StaticPromptScorer(scores={"OLD": 0.7, "NEW": 0.7})
    res = validated_apply_gradient(var, _bad_gradient(), llm, scorer, base_prompt="OLD")
    assert res.accepted is True  # 默认 min_improvement=0.0，并列即接受


def test_validated_min_improvement_threshold():
    var = _prompt_var(value="OLD")
    llm = StaticLLMClient(fn=lambda s, u: "NEW")
    scorer = StaticPromptScorer(scores={"OLD": 0.70, "NEW": 0.75})
    res = validated_apply_gradient(
        var, _bad_gradient(), llm, scorer, base_prompt="OLD", min_improvement=0.1
    )
    assert res.accepted is False  # +0.05 < 阈值 0.1


def test_validated_no_candidate_when_llm_returns_same():
    var = _prompt_var(value="OLD")
    llm = StaticLLMClient(fn=lambda s, u: "OLD")  # 与原文一致
    scorer = StaticPromptScorer(scores={"OLD": 0.5})
    res = validated_apply_gradient(var, _bad_gradient(), llm, scorer, base_prompt="OLD")
    assert res.accepted is False
    assert res.reason == "no_candidate"


def test_validated_scorer_error_is_conservative():
    var = _prompt_var(value="OLD")
    llm = StaticLLMClient(fn=lambda s, u: "NEW")

    def boom(_):
        raise RuntimeError("scoring backend down")

    scorer = StaticPromptScorer(fn=boom)
    res = validated_apply_gradient(var, _bad_gradient(), llm, scorer, base_prompt="OLD")
    assert res.accepted is False
    assert res.reason == "scorer_error"  # 无法验证 → 保守回滚


def test_validated_gradient_ok_short_circuits():
    var = _prompt_var()
    llm = StaticLLMClient(fn=lambda s, u: "NEW")
    scorer = StaticPromptScorer(fn=lambda p: 1.0)
    res = validated_apply_gradient(var, _good_gradient(), llm, scorer)
    assert res.accepted is False
    assert res.reason == "gradient_ok"


# --------------------------- optimizer 集成 ---------------------------
def _graph_with_prompt(value="OLD"):
    g = BerkshireGraph()
    var = _prompt_var(value=value)
    g.variables[var.name] = var
    return g, var


def test_optimizer_validated_accept_writes_back():
    g, var = _graph_with_prompt("OLD")
    llm = StaticLLMClient(fn=lambda s, u: "NEW")
    scorer = StaticPromptScorer(scores={"OLD": 0.4, "NEW": 0.9})
    opt = TextualGradientDescent(g, llm=llm, scorer=scorer)
    updates = opt.step({var.name: _bad_gradient()})
    assert var.value == "NEW"  # 接受后回填
    u = updates[0]
    assert u["rewritten"] is True
    assert u["validation"]["accepted"] is True
    assert u["old_value"] == "OLD" and u["new_value"] == "NEW"


def test_optimizer_validated_reject_rolls_back():
    g, var = _graph_with_prompt("OLD")
    llm = StaticLLMClient(fn=lambda s, u: "NEW")
    scorer = StaticPromptScorer(scores={"OLD": 0.9, "NEW": 0.3})
    opt = TextualGradientDescent(g, llm=llm, scorer=scorer)
    updates = opt.step({var.name: _bad_gradient()})
    assert var.value == "OLD"  # 回滚，保持旧 Prompt
    u = updates[0]
    assert u["rewritten"] is False
    assert u["validation"]["accepted"] is False
    assert u["rewrite_rejected"] == "rejected_not_better"


def test_optimizer_without_scorer_uses_unvalidated_path():
    g, var = _graph_with_prompt("OLD")
    llm = StaticLLMClient(fn=lambda s, u: "NEW")
    opt = TextualGradientDescent(g, llm=llm)  # 无 scorer → V10.13 路径
    updates = opt.step({var.name: _bad_gradient()})
    assert var.value == "NEW"
    u = updates[0]
    assert u["rewritten"] is True
    assert "validation" not in u  # 未走验证门控


def test_optimizer_validated_min_improvement_rejects_marginal():
    g, var = _graph_with_prompt("OLD")
    llm = StaticLLMClient(fn=lambda s, u: "NEW")
    scorer = StaticPromptScorer(scores={"OLD": 0.70, "NEW": 0.74})
    opt = TextualGradientDescent(g, llm=llm, scorer=scorer, min_improvement=0.1)
    opt.step({var.name: _bad_gradient()})
    assert var.value == "OLD"  # 增益不足阈值 → 回滚
