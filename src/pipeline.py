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
    proposer: Optional[HypothesisProposer] = None,
    llm: Optional[LLMClient] = None,
    scenario: Scenario = DEFAULT_SCENARIO,
    record_traces: bool = True,
) -> Dict[str, Any]:
    """完整闭环：可选 R/D → realized feedback → 经验 + 绩效 + 轨迹。

    Args:
        decision: 决策快照。
        run_rd: 是否在反馈前跑 R/D 双循环（默认 True）。
        rd_cycles: R/D 轮数（每轮 R→D）。
        proposer: 假设提案器；None 时 D 段仍跑但 R 为空列表。
        其余参数同 run_with_realized_feedback。
    """
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
                proposer=proposer,
                retriever=retriever,
                research_cycles=rd_cycles,
                dev_rounds=1,
                run_id=rid,
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
