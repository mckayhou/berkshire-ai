#!/usr/bin/env python3
"""
Berkshire AI V10.0 - TextGrad 化进化引擎 (modular)

Thin entrypoint. Core logic in graph.py / optimizer.py / debate.py /
decision_log.py / realized_feedback.py.

See update-platforms.sh for deployment to OpenClaw/QwenPaw.
"""

# Absolute imports for compatibility (sys.path insert to src/ in tests)
try:
    from graph import BerkshireGraph, Variable, Gradient, Master, MASTERS
    from optimizer import TextualGradientDescent
    from prompt_optimizer import (
        LLMClient,
        StaticLLMClient,
        OpenAICompatibleLLMClient,
        apply_gradient,
        build_rewrite_messages,
    )
    from decision_log import DecisionRecord, append_decision
    from realized_feedback import (
        realized_scores,
        realized_scores_via_provider,
        PriceProvider,
        StaticPriceProvider,
        ReturnStats,
    )
    from debate import run_debate, DebateResult
except ImportError:
    from .graph import BerkshireGraph, Variable, Gradient, Master, MASTERS
    from .optimizer import TextualGradientDescent
    from .prompt_optimizer import (
        LLMClient,
        StaticLLMClient,
        OpenAICompatibleLLMClient,
        apply_gradient,
        build_rewrite_messages,
    )
    from .decision_log import DecisionRecord, append_decision
    from .realized_feedback import (
        realized_scores,
        realized_scores_via_provider,
        PriceProvider,
        StaticPriceProvider,
        ReturnStats,
    )
    from .debate import run_debate, DebateResult

__all__ = [
    "BerkshireGraph",
    "Variable",
    "Gradient",
    "Master",
    "MASTERS",
    "TextualGradientDescent",
    "LLMClient",
    "StaticLLMClient",
    "OpenAICompatibleLLMClient",
    "apply_gradient",
    "build_rewrite_messages",
    "DecisionRecord",
    "append_decision",
    "realized_scores",
    "realized_scores_via_provider",
    "PriceProvider",
    "StaticPriceProvider",
    "ReturnStats",
    "run_debate",
    "DebateResult",
    "run_example",
    "run_with_realized_feedback",
]


def run_example():
    """Simple runner for the engine."""
    graph = BerkshireGraph()
    print("Graph created with", len(graph.variables), "nodes")
    scores = {"duan": 0.92, "buffett": 0.68, "munger": 0.85, "lilu": 0.55}
    gradients = graph.backward(scores)
    optimizer = TextualGradientDescent(graph)
    updates = optimizer.step(gradients)
    print("Updates needed:", len(updates))
    return graph, gradients, updates


def run_with_realized_feedback(
    decision,
    realized_price=None,
    benchmark_realized_price=None,
    *,
    realized_date=None,
    price_provider=None,
    sensitivity=None,
    persist=False,
    log_path=None,
    llm=None,
):
    """已实现收益 → 评分 → backward 的反馈闭环。

    替代 run_example 里硬编码的 scores：用真实已实现收益算出各大师评分，
    再跑 graph.backward() + optimizer.step()。同时返回决策时信心的
    多空辩论净判断（debate），作为 final_report 前的一步。

    两种取价方式（二选一）：
      A. 直接传 realized_price (+ benchmark_realized_price)
      B. 传 realized_date + price_provider（可注入/可 mock，不连网络）

    Args:
        decision: DecisionRecord（含 ticker/date/scores/price_anchor）。
        realized_price: 后续真实价格（方式 A）。
        benchmark_realized_price: 后续基准价格（方式 A，可选）。
        realized_date: 取价日期（方式 B）。
        price_provider: PriceProvider 实例（方式 B）。
        sensitivity: 收益→真相分灵敏度（默认用 realized_feedback 的默认值）。
        persist: 是否把该决策追加到决策日志。
        log_path: 决策日志路径（默认 BERKSHIRE_DECISION_LOG / ~/.berkshire）。
        llm: 可选 LLMClient（Option B）。传入后，优化器会对未达标的 prompt 变量
             调用 LLM 真实改写 `Variable.value`；未传则仅记录优化动作（向后兼容）。
             注意：被改写的 prompt 变量需先有 `value`（底稿），否则该变量记为跳过。

    Returns:
        dict: {graph, scores, stats(ReturnStats), gradients, updates, debate(DebateResult)}
    """
    from realized_feedback import DEFAULT_SENSITIVITY  # local import for default
    sens = DEFAULT_SENSITIVITY if sensitivity is None else sensitivity

    if persist:
        append_decision(decision, path=log_path)

    if price_provider is not None and realized_date is not None:
        scores, stats = realized_scores_via_provider(
            decision, realized_date, price_provider, sensitivity=sens
        )
    elif realized_price is not None:
        scores, stats = realized_scores(
            decision, realized_price, benchmark_realized_price, sensitivity=sens
        )
    else:
        raise ValueError(
            "需要 realized_price，或同时提供 realized_date + price_provider"
        )

    graph = BerkshireGraph()
    graph.trace_id = decision.trace_id
    # 多空辩论：用决策当时的信心分，作为 final_report 前的净判断
    debate = graph.debate(decision.scores)
    # 反馈：用已实现收益映射出的校准分驱动 backward
    gradients = graph.backward(scores)
    optimizer = TextualGradientDescent(graph, llm=llm)
    updates = optimizer.step(gradients)

    return {
        "graph": graph,
        "scores": scores,
        "stats": stats,
        "gradients": gradients,
        "updates": updates,
        "debate": debate,
    }


if __name__ == "__main__":
    run_example()
