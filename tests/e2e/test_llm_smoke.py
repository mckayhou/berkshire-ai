#!/usr/bin/env python3
"""端到端冒烟：接真实 LLM 跑一次 ∇_LLM 批评 + Option B 改写。

默认 **跳过**——仅当配置了真实 LLM（BERKSHIRE_LLM_API_KEY / OPENAI_API_KEY）时运行。
CI 可在带 secret 的独立 job 中执行（见 .github/workflows/test.yml 的 e2e job）。
本测试只验证「真实链路能跑通且产出非空」，不对模型具体措辞做脆弱断言。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest  # noqa: E402

_HAS_LLM = bool(
    os.getenv("BERKSHIRE_LLM_API_KEY", "").strip()
    or os.getenv("OPENAI_API_KEY", "").strip()
)

pytestmark = pytest.mark.skipif(
    not _HAS_LLM, reason="未配置真实 LLM（BERKSHIRE_LLM_API_KEY/OPENAI_API_KEY），跳过 e2e 冒烟"
)


def test_real_llm_critique_and_rewrite():
    from graph import BerkshireGraph
    from llm_gradient import LLMGradientGenerator
    from observability import MetricsCollector
    from prompt_optimizer import OpenAICompatibleLLMClient, apply_gradient

    collector = MetricsCollector()
    llm = OpenAICompatibleLLMClient(collector=collector)

    # 1) ∇_LLM：对一段"薄"分析生成批评
    gen = LLMGradientGenerator(llm)
    issues = gen.critique("巴菲特", "这家公司还不错，建议买入。", 0.4)
    assert isinstance(issues, list) and len(issues) >= 1

    # 2) Option B：用批评驱动真实改写
    g = BerkshireGraph()
    var = g.variables[g.prompt_node("buffett")]
    var.value = "你是巴菲特，请分析这家公司。"
    grad = g.backward({"duan": 0.9, "buffett": 0.5, "munger": 0.9, "lilu": 0.9})[
        g.prompt_node("buffett")
    ]
    new_prompt = apply_gradient(var, grad, llm)
    assert new_prompt and new_prompt != var.value

    # 3) 埋点确有记录（≥2 次调用、token>0）
    assert collector.count >= 2
    assert collector.total_tokens > 0
