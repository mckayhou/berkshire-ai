#!/usr/bin/env python3
"""离线单元测试：变量真实改写（Option B）。

覆盖：
- StaticLLMClient：固定响应 / 回调 / echo 三种 mock 模式
- build_rewrite_messages：system/user 文本包含角色、当前 Prompt、诊断、检查项
- apply_gradient：正常改写 / ok 无需改写 / 无底稿 / 代码块清洗 / 空返回
- OpenAICompatibleLLMClient：缺 key 报错 + env 解析（不连网络）
- TextualGradientDescent.step：有 llm 真实改写 var.value、无 llm 向后兼容、
  LLM 异常优雅降级、底稿缺失记跳过

全部用 mock，不依赖真实网络。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import prompt_optimizer as po  # noqa: E402
from graph import BerkshireGraph, Gradient, Variable  # noqa: E402
from optimizer import TextualGradientDescent  # noqa: E402


def _bad_gradient(node="buffett_prompt"):
    return Gradient(
        node=node,
        ok=False,
        text="❌ 巴菲特 分析存在问题:\n  - 缺少 DCF\n  - 护城河未评估",
        issues=["检查: 是否包含 PE/PB/DCF 估值分析？", "检查: 是否评估了护城河宽度？"],
    )


# --------------------------- StaticLLMClient ---------------------------
def test_static_llm_fn_mode():
    llm = po.StaticLLMClient(fn=lambda s, u: "REWRITTEN")
    assert llm.complete("sys", "user") == "REWRITTEN"
    assert llm.calls[0]["user"] == "user"


def test_static_llm_responses_substring():
    llm = po.StaticLLMClient(responses={"巴菲特": "新巴菲特Prompt"})
    assert llm.complete("s", "角色是巴菲特，请改写") == "新巴菲特Prompt"


def test_static_llm_echo_fallback():
    llm = po.StaticLLMClient()
    assert llm.complete("s", "echo-me") == "echo-me"


# --------------------------- build_rewrite_messages ---------------------------
def test_build_rewrite_messages_contains_context():
    var = Variable("buffett_prompt", "prompt", role="巴菲特", value="原始Prompt", layer=2)
    grad = _bad_gradient()
    msgs = po.build_rewrite_messages(var, grad, "原始Prompt")
    assert "system" in msgs and "user" in msgs
    assert "巴菲特" in msgs["user"]
    assert "原始Prompt" in msgs["user"]
    assert "DCF" in msgs["user"]  # 诊断文本
    assert "护城河" in msgs["user"]  # issue


# --------------------------- apply_gradient ---------------------------
def test_apply_gradient_rewrites():
    var = Variable("buffett_prompt", "prompt", role="巴菲特", value="原始Prompt", layer=2)
    llm = po.StaticLLMClient(fn=lambda s, u: "改进后的 Prompt：必须含 DCF 与护城河评估")
    out = po.apply_gradient(var, _bad_gradient(), llm)
    assert out == "改进后的 Prompt：必须含 DCF 与护城河评估"


def test_apply_gradient_ok_returns_none():
    var = Variable("buffett_prompt", "prompt", role="巴菲特", value="原始", layer=2)
    ok_grad = Gradient(node="buffett_prompt", ok=True, text="✅ 无需修改")
    assert po.apply_gradient(var, ok_grad, po.StaticLLMClient()) is None


def test_apply_gradient_no_base_returns_none():
    var = Variable("buffett_prompt", "prompt", role="巴菲特", value=None, layer=2)
    assert po.apply_gradient(var, _bad_gradient(), po.StaticLLMClient()) is None


def test_apply_gradient_uses_explicit_base_prompt():
    var = Variable("buffett_prompt", "prompt", role="巴菲特", value=None, layer=2)
    captured = {}

    def fn(s, u):
        captured["user"] = u
        return "new"

    out = po.apply_gradient(var, _bad_gradient(), po.StaticLLMClient(fn=fn), base_prompt="显式底稿")
    assert out == "new"
    assert "显式底稿" in captured["user"]


def test_apply_gradient_strips_code_fences():
    var = Variable("buffett_prompt", "prompt", role="巴菲特", value="x", layer=2)
    llm = po.StaticLLMClient(fn=lambda s, u: "```text\n干净的Prompt\n```")
    assert po.apply_gradient(var, _bad_gradient(), llm) == "干净的Prompt"


def test_apply_gradient_empty_output_returns_none():
    var = Variable("buffett_prompt", "prompt", role="巴菲特", value="x", layer=2)
    llm = po.StaticLLMClient(fn=lambda s, u: "   ")
    assert po.apply_gradient(var, _bad_gradient(), llm) is None


# --------------------------- OpenAICompatibleLLMClient ---------------------------
def test_openai_client_requires_key(monkeypatch):
    monkeypatch.delenv("BERKSHIRE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        po.OpenAICompatibleLLMClient()


def test_openai_client_env_resolution(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_LLM_API_KEY", "k-123")
    monkeypatch.setenv("BERKSHIRE_LLM_BASE_URL", "https://gw.example.com/v1/")
    monkeypatch.setenv("BERKSHIRE_LLM_MODEL", "my-model")
    c = po.OpenAICompatibleLLMClient()
    assert c.api_key == "k-123"
    assert c.base_url == "https://gw.example.com/v1"  # 去尾斜杠
    assert c.model == "my-model"


def test_openai_client_openai_key_fallback(monkeypatch):
    monkeypatch.delenv("BERKSHIRE_LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fallback")
    c = po.OpenAICompatibleLLMClient()
    assert c.api_key == "sk-fallback"


# --------------------------- step() 集成 ---------------------------
def _graph_with_seeded_prompt():
    g = BerkshireGraph()
    g.variables["buffett_prompt"].value = "原始巴菲特 Prompt"
    return g


def test_step_rewrites_prompt_with_llm():
    g = _graph_with_seeded_prompt()
    grads = g.backward({"duan": 0.95, "buffett": 0.40, "munger": 0.95, "lilu": 0.95})
    llm = po.StaticLLMClient(fn=lambda s, u: "改进版巴菲特 Prompt：含 DCF/护城河")
    opt = TextualGradientDescent(g, llm=llm)
    updates = opt.step(grads)

    rewritten = [u for u in updates if u.get("rewritten")]
    assert any(u["variable"] == "buffett_prompt" for u in rewritten)
    assert g.variables["buffett_prompt"].value == "改进版巴菲特 Prompt：含 DCF/护城河"
    bp = next(u for u in updates if u["variable"] == "buffett_prompt")
    assert bp["old_value"] == "原始巴菲特 Prompt"
    assert bp["new_value"] == "改进版巴菲特 Prompt：含 DCF/护城河"


def test_step_without_llm_is_backward_compatible():
    g = _graph_with_seeded_prompt()
    grads = g.backward({"duan": 0.95, "buffett": 0.40, "munger": 0.95, "lilu": 0.95})
    opt = TextualGradientDescent(g)  # 无 llm
    updates = opt.step(grads)
    assert all(u["rewritten"] is False for u in updates)
    assert g.variables["buffett_prompt"].value == "原始巴菲特 Prompt"  # 未改


def test_step_llm_error_degrades_gracefully():
    g = _graph_with_seeded_prompt()
    grads = g.backward({"duan": 0.95, "buffett": 0.40, "munger": 0.95, "lilu": 0.95})

    def boom(s, u):
        raise RuntimeError("network down")

    opt = TextualGradientDescent(g, llm=po.StaticLLMClient(fn=boom))
    updates = opt.step(grads)  # 不应抛错
    bp = next(u for u in updates if u["variable"] == "buffett_prompt")
    assert bp["rewritten"] is False
    assert "rewrite_error" in bp
    assert g.variables["buffett_prompt"].value == "原始巴菲特 Prompt"  # 未改


def test_step_skips_when_no_base_prompt():
    g = BerkshireGraph()  # prompt 变量 value 默认 None
    grads = g.backward({"duan": 0.95, "buffett": 0.40, "munger": 0.95, "lilu": 0.95})
    llm = po.StaticLLMClient(fn=lambda s, u: "不该被采用")
    opt = TextualGradientDescent(g, llm=llm)
    updates = opt.step(grads)
    bp = next(u for u in updates if u["variable"] == "buffett_prompt")
    assert bp["rewritten"] is False
    assert "rewrite_skipped" in bp
    assert g.variables["buffett_prompt"].value is None


def test_step_only_rewrites_unmet_prompts():
    g = _graph_with_seeded_prompt()
    g.variables["munger_prompt"].value = "原始芒格 Prompt"
    # buffett 不达标、munger 达标
    grads = g.backward({"duan": 0.95, "buffett": 0.40, "munger": 0.95, "lilu": 0.95})
    llm = po.StaticLLMClient(fn=lambda s, u: "X")
    opt = TextualGradientDescent(g, llm=llm)
    opt.step(grads)
    assert g.variables["buffett_prompt"].value == "X"          # 改了
    assert g.variables["munger_prompt"].value == "原始芒格 Prompt"  # 未动
