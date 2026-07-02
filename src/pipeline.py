#!/usr/bin/env python3
"""
统一主链路编排：R/D 双循环 → 收益反馈 → 经验沉淀 → 轨迹/run 记录。

这是推荐的默认生产入口，替代分散调用 run_rd_cycle / run_with_realized_feedback。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from decision_log import DecisionRecord
    from experience_store import ExperienceStore, KeywordExperienceRetriever
    from graph import BerkshireGraph
    from observability import run_context
    from prompt_optimizer import LLMClient, StaticLLMClient
    from quality_scorer import build_experience_quality_fn
    from research_loop import HypothesisProposer, run_rd_cycle
    from run_recorder import RunRecord, RunRecorder
    from scenario import DEFAULT_SCENARIO, Scenario
    from trace_recorder import record_trace
except ImportError:  # pragma: no cover
    from .decision_log import DecisionRecord
    from .experience_store import ExperienceStore, KeywordExperienceRetriever
    from .graph import BerkshireGraph
    from .observability import run_context
    from .prompt_optimizer import LLMClient, StaticLLMClient
    from .quality_scorer import build_experience_quality_fn
    from .research_loop import HypothesisProposer, run_rd_cycle
    from .run_recorder import RunRecord, RunRecorder
    from .scenario import DEFAULT_SCENARIO, Scenario
    from .trace_recorder import record_trace


def run_full_cycle(
    decision: DecisionRecord,
    *,
    realized_price=None,
    benchmark_realized_price=None,
    realized_date=None,
    price_provider=None,
    persist: bool = True,
    include_perf: bool = True,
    run_rd: bool = True,
    rd_cycles: int = 1,
    dev_rounds: int = 3,
    proposer: Optional[HypothesisProposer] = None,
    llm: Optional[LLMClient] = None,
    scenario: Scenario = DEFAULT_SCENARIO,
    record_traces: bool = True,
    use_llm_gradient: bool = True,
    use_validation: bool = True,
    rerun_analysis: bool = False,
    analysis_runner: Optional[Any] = None,
    factor_scan: Optional[Dict[str, Any]] = None,
    limitup_scan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """完整闭环：可选 R/D → realized feedback → 经验 + 绩效 + 轨迹。

    Args:
        decision: 决策快照。
        run_rd: 是否在反馈前跑 R/D 双循环（默认 True）。
        rd_cycles: R/D 轮数（每轮 R→D）。
        dev_rounds: 每轮 D 段 `run_multi_round` 最大轮数（默认 3）。
        proposer: 假设提案器；None 时 D 段仍跑但 R 为空列表。
        use_llm_gradient / use_validation: 反馈段是否启用 ∇_LLM 与验证门控。
        rerun_analysis: D 段改写后重跑分析（V10.26，默认关，耗 LLM）。
        factor_scan / limitup_scan: V10.28 量化信号 JSON，并入 HypothesisProposer。
        其余参数同 run_with_realized_feedback。
    """
    try:
        from signal_proposer import proposer_from_signal_scans
    except ImportError:
        from .signal_proposer import proposer_from_signal_scans

    effective_proposer = proposer
    if factor_scan or limitup_scan:
        merged = proposer_from_signal_scans(
            factor_scan=factor_scan,
            limitup_scan=limitup_scan,
            base=proposer,
        )
        if merged is not None:
            effective_proposer = merged
    try:
        from evolution_loop_v10 import run_with_realized_feedback
    except ImportError:
        from .evolution_loop_v10 import run_with_realized_feedback

    result: Dict[str, Any] = {"decision": decision, "rd": None, "feedback": None}

    with run_context() as rid:
        retriever = KeywordExperienceRetriever(ExperienceStore())
        quality_fn = build_experience_quality_fn(decision.ticker)
        llm_client = llm or StaticLLMClient(responses={"*": "pipeline-optimized"})

        if run_rd:
            graph = BerkshireGraph(scenario=scenario)
            for name, var in graph.variables.items():
                if var.type == "prompt" and not var.value:
                    var.value = f"Prompt for {name}"
            rd_report = run_rd_cycle(
                graph,
                decision.ticker,
                llm_client,
                quality_fn,
                proposer=effective_proposer,
                retriever=retriever,
                research_cycles=rd_cycles,
                dev_rounds=dev_rounds,
                run_id=rid,
                rerun_analysis=rerun_analysis,
                analysis_runner=analysis_runner,
            )
            result["rd"] = rd_report
            if record_traces:
                record_trace(
                    decision.ticker,
                    "rd_cycle",
                    output_data={
                        "cycles": len(rd_report.cycles),
                        "hypotheses": sum(
                            getattr(c, "hypotheses_proposed", 0) for c in rd_report.cycles
                        ),
                    },
                    notes="run_full_cycle rd",
                )

        feedback = run_with_realized_feedback(
            decision,
            realized_price=realized_price,
            benchmark_realized_price=benchmark_realized_price,
            realized_date=realized_date,
            price_provider=price_provider,
            persist=persist,
            include_perf=include_perf,
            retriever=retriever,
            llm=llm_client,
            use_llm_gradient=use_llm_gradient,
            use_validation=use_validation,
        )
        result["feedback"] = feedback
        result["run_id"] = rid

        if record_traces:
            stats = feedback.get("stats")
            record_trace(
                decision.ticker,
                "feedback",
                score=float(getattr(stats, "realized_base", 0) or 0),
                output_data={
                    "alpha": float(getattr(stats, "alpha", 0) or 0),
                    "debate": getattr(feedback.get("debate"), "net_stance", ""),
                },
                notes="run_full_cycle feedback",
            )

        try:
            RunRecorder().append(
                RunRecord(
                    run_id=rid,
                    event="full_cycle",
                    ticker=decision.ticker,
                    metrics={
                        "run_rd": run_rd,
                        "alpha": float(getattr(feedback.get("stats"), "alpha", 0) or 0),
                    },
                    note="pipeline.run_full_cycle",
                )
            )
        except OSError:
            pass

    return result
