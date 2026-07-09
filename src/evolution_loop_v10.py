#!/usr/bin/env python3
"""
Berkshire AI V10.0 - TextGrad 化进化引擎 (modular)

Thin entrypoint. Core logic in graph.py / optimizer.py / debate.py /
decision_log.py / realized_feedback.py.

See update-platforms.sh for deployment to OpenClaw/QwenPaw.
"""

# Absolute imports for compatibility (sys.path insert to src/ in tests)
try:
    from .debate import DebateResult, run_debate
    from .decision_log import DecisionRecord, append_decision
    from .graph import MASTER_PREFIXES, MASTERS, BerkshireGraph, Gradient, Master, Variable
    from .optimizer import TextualGradientDescent
    from .prompt_optimizer import (
        LLMClient,
        OpenAICompatibleLLMClient,
        StaticLLMClient,
        apply_gradient,
        build_rewrite_messages,
    )
    from .prompt_validation import (
        PromptScorer,
        StaticPromptScorer,
        ValidationResult,
        validated_apply_gradient,
    )
    from .realized_feedback import (
        NetworkPriceProvider,
        PriceProvider,
        ReturnStats,
        StaticPriceProvider,
        realized_scores,
        realized_scores_via_provider,
    )

except ImportError:
    from debate import DebateResult, run_debate
    from decision_log import DecisionRecord, append_decision
    from graph import MASTER_PREFIXES, MASTERS, BerkshireGraph, Gradient, Master, Variable
    from optimizer import TextualGradientDescent
    from prompt_optimizer import (
        LLMClient,
        OpenAICompatibleLLMClient,
        StaticLLMClient,
        apply_gradient,
        build_rewrite_messages,
    )
    from prompt_validation import (
        PromptScorer,
        StaticPromptScorer,
        ValidationResult,
        validated_apply_gradient,
    )
    from realized_feedback import (
        NetworkPriceProvider,
        PriceProvider,
        ReturnStats,
        StaticPriceProvider,
        realized_scores,
        realized_scores_via_provider,
    )
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
    "PromptScorer",
    "StaticPromptScorer",
    "ValidationResult",
    "validated_apply_gradient",
    "DecisionRecord",
    "append_decision",
    "realized_scores",
    "realized_scores_via_provider",
    "PriceProvider",
    "StaticPriceProvider",
    "NetworkPriceProvider",
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
    scorer=None,
    min_improvement=0.0,
    retriever=None,
    retriever_k: int = 3,
    persist_experience=None,
    experience_store=None,
    experience_log_path=None,
    lesson=None,
    include_perf=False,
    perf_eval_dates=None,
    use_llm_gradient=True,
    use_validation=False,
    analyses=None,
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
        scorer: 可选 PromptScorer（V10.15 验证门控）。与 llm 同时传入时，改写后会在
             评测集上打分，只有不劣于旧版(+min_improvement)才接受，否则回滚。
        min_improvement: 验证门控接受所需最小增益（默认 0.0，即「不劣于」即接受）。
        retriever: 可选 ExperienceRetriever；D 段改写前召回 few-shot 经验（V10.19）。
        retriever_k: 召回条数（默认 3）。
        persist_experience: 是否把本次成败沉淀为 Experience（默认与 persist 相同）。
        experience_store: 经验库实例；缺省则新建默认路径的 ExperienceStore。
        experience_log_path: 覆盖 BERKSHIRE_EXPERIENCE_LOG 路径。
        lesson: 经验教训自由文本；缺省则按 alpha 自动生成一句。
        include_perf: 是否在返回中附带 perf_metrics 绩效摘要（PerfReport）。
        perf_eval_dates: 绩效评估用的后续日期列表（配合 price_provider）；缺省时
             方式 A 用锚点+realized_price 两点路径，方式 B 用 [realized_date]。
        use_llm_gradient: 注入 llm 时是否用 ∇_LLM 增强未达标梯度（默认 True）。
        use_validation: 未传 scorer 时是否用经验库 quality_fn 作验证门控（默认 False）。
        analyses: 覆盖 decision.analyses 的大师正文；缺省读 decision.analyses。

    Returns:
        dict: {graph, scores, stats, gradients, updates, debate,
               experience?(Experience), perf?(PerfReport)}
    """
    try:
        from .realized_feedback import DEFAULT_SENSITIVITY
    except ImportError:  # pragma: no cover - flat PYTHONPATH=src
        from realized_feedback import DEFAULT_SENSITIVITY
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
    debate = graph.debate(decision.scores)
    gradients = graph.backward(scores)

    if llm is not None and use_llm_gradient:
        try:
            from .llm_gradient import enrich_gradients_with_llm
        except ImportError:
            from llm_gradient import enrich_gradients_with_llm
        analysis_map = analyses if analyses is not None else getattr(decision, "analyses", None)
        note_text = str(getattr(decision, "note", "") or "")
        if not analysis_map and note_text:
            analysis_map = {p: note_text for p in MASTER_PREFIXES}
        gradients = enrich_gradients_with_llm(
            graph, gradients, analysis_map or {}, llm
        )

    effective_scorer = scorer
    if effective_scorer is None and use_validation and llm is not None:
        try:
            from .prompt_validation import StaticPromptScorer
            from .quality_scorer import build_experience_quality_fn
        except ImportError:
            from prompt_validation import StaticPromptScorer
            from quality_scorer import build_experience_quality_fn
        effective_scorer = StaticPromptScorer(
            fn=build_experience_quality_fn(decision.ticker)
        )

    optimizer = TextualGradientDescent(
        graph,
        llm=llm,
        scorer=effective_scorer,
        min_improvement=min_improvement,
        retriever=retriever,
        retriever_ticker=decision.ticker,
        retriever_k=retriever_k,
    )
    updates = optimizer.step(gradients)

    # --- V10.20：主线接线 — 经验沉淀 + 绩效摘要 ---
    should_persist_exp = persist if persist_experience is None else persist_experience
    experience = None
    if should_persist_exp:
        experience = _persist_experience_from_run(
            decision,
            stats,
            lesson=lesson,
            store=experience_store,
            log_path=experience_log_path,
        )

    perf = None
    if include_perf:
        perf = _compute_perf_report(
            decision,
            realized_price=realized_price,
            benchmark_realized_price=benchmark_realized_price,
            price_provider=price_provider,
            realized_date=realized_date,
            perf_eval_dates=perf_eval_dates,
        )

    result = {
        "graph": graph,
        "scores": scores,
        "stats": stats,
        "gradients": gradients,
        "updates": updates,
        "debate": debate,
    }
    if experience is not None:
        result["experience"] = experience
        _record_feedback_run(decision, stats, experience)
    if perf is not None:
        result["perf"] = perf

    try:
        from .trace_recorder import record_trace
    except ImportError:
        from trace_recorder import record_trace
    record_trace(
        getattr(decision, "ticker", ""),
        "feedback",
        score=float(stats.realized_base),
        output_data={"alpha": float(stats.alpha)},
        notes="run_with_realized_feedback",
    )
    return result


def _record_feedback_run(decision, stats, experience) -> None:
    """记录反馈闭环 run；失败降级。"""
    try:
        try:
            from .observability import get_run_id
            from .run_recorder import RunRecord, RunRecorder

        except ImportError:
            from observability import get_run_id
            from run_recorder import RunRecord, RunRecorder
        RunRecorder().append(
            RunRecord(
                run_id=get_run_id() or "",
                event="feedback",
                ticker=getattr(decision, "ticker", None),
                metrics={
                    "alpha": float(stats.alpha),
                    "realized_base": float(stats.realized_base),
                    "verdict": getattr(experience, "verdict", ""),
                },
                note="run_with_realized_feedback",
            )
        )
    except Exception:  # noqa: BLE001
        return None


def _default_lesson(decision, stats) -> str:
    """按 alpha 自动生成一句简短教训（供经验库检索）。"""
    alpha = float(stats.alpha)
    tkr = getattr(decision, "ticker", "")
    if alpha > 0:
        return f"{tkr} 决策获正超额，alpha={alpha:.3f}"
    if alpha < 0:
        return f"{tkr} 高信心被证伪，alpha={alpha:.3f}"
    return f"{tkr} 超额中性，alpha={alpha:.3f}"


def _persist_experience_from_run(decision, stats, *, lesson=None, store=None, log_path=None):
    """把 realized_feedback 结果沉淀为 Experience；失败返回 None，不崩主链路。"""
    try:
        try:
            from .experience_store import ExperienceStore, experience_from_stats
            from .observability import get_run_id

        except ImportError:
            from experience_store import ExperienceStore, experience_from_stats
            from observability import get_run_id
        exp_store = store or ExperienceStore(path=log_path)
        text = lesson if lesson is not None else _default_lesson(decision, stats)
        hyp_id = getattr(decision, "hypothesis_id", None)
        exp = experience_from_stats(
            decision,
            stats,
            lesson=text,
            hypothesis_id=hyp_id,
            run_id=get_run_id(),
        )
        exp_store.append(exp)
        return exp
    except Exception:  # noqa: BLE001 - 沉淀失败降级，不影响闭环主路径
        return None


def _import_perf_metrics():
    """延迟加载 tools/perf_metrics（避免包路径强耦合）。"""
    import sys
    from pathlib import Path

    tools_dir = Path(__file__).resolve().parent.parent / "tools"
    tools_str = str(tools_dir)
    if tools_str not in sys.path:
        sys.path.insert(0, tools_str)
    import perf_metrics  # noqa: WPS433

    return perf_metrics


def _compute_perf_report(
    decision,
    *,
    realized_price=None,
    benchmark_realized_price=None,
    price_provider=None,
    realized_date=None,
    perf_eval_dates=None,
):
    """计算绩效摘要；数据不足或失败时返回 None。"""
    try:
        pm = _import_perf_metrics()
        if price_provider is not None:
            dates = list(perf_eval_dates or [])
            if not dates and realized_date:
                dates = [realized_date]
            if dates:
                return pm.analyze_decision(decision, dates, price_provider)
        if realized_price is not None:
            path = [float(decision.price_anchor), float(realized_price)]
            bench_path = None
            bench_px = benchmark_realized_price
            bench_anchor = getattr(decision, "benchmark_anchor", None)
            if bench_px is not None and bench_anchor is not None:
                bench_path = [float(bench_anchor), float(bench_px)]
            return pm.analyze_price_path(path, bench_path)
    except Exception:  # noqa: BLE001
        return None
    return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in (
        "status", "reflect", "optimize", "run", "cron", "cycle", "skill-evolve",
    ):
        try:
            from .evolution_cli import main as cli_main
        except ImportError:
            from evolution_cli import main as cli_main
        sys.exit(cli_main())
    run_example()
