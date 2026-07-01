"""
Berkshire AI V10 engine package.

Exports the main classes for TextGrad-based 4-masters analysis.
"""

from .access_control import RateLimiter, check_api_key, key_fingerprint
from .cron_evolution import CronResult, run_cron
from .debate import DebateCase, DebateResult, run_debate
from .decision_log import DecisionRecord, append_decision, load_decisions
from .eval_harness import (
    EvolutionReport,
    RoundMetrics,
    build_quality_gradients,
    mean_prompt_quality,
    run_multi_round,
)
from .experience_store import (
    Experience,
    ExperienceRetriever,
    ExperienceStore,
    KeywordExperienceRetriever,
    StaticExperienceRetriever,
    classify_verdict,
    experience_from_stats,
)
from .graph import MASTERS, BerkshireGraph, Gradient, Master, Variable
from .hypothesis import (
    Hypothesis,
    HypothesisStore,
    group_experiences_by_hypothesis,
)
from .llm_gradient import (
    LLMGradientGenerator,
    build_critique_messages,
    enrich_gradients_with_llm,
    parse_issues,
)
from .metrics_export import ServiceMetrics, render_prometheus
from .observability import (
    LLMCallMetrics,
    MetricsCollector,
    configure_logging,
    estimate_cost,
    get_logger,
    get_run_id,
    new_run_id,
    run_context,
)
from .optimizer import TextualGradientDescent
from .pipeline import run_full_cycle
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
from .quality_scorer import build_experience_quality_fn
from .realized_feedback import (
    NetworkPriceProvider,
    PriceProvider,
    ReturnStats,
    StaticPriceProvider,
    compute_returns,
    realized_scores,
    realized_scores_via_provider,
)
from .reflect import ReflectionReport, reflect_ticker
from .research_loop import (
    ExperienceDrivenProposer,
    HypothesisProposer,
    LLMHypothesisProposer,
    RDCycleMetrics,
    RDCycleReport,
    StaticHypothesisProposer,
    run_rd_cycle,
)
from .run_recorder import RunRecord, RunRecorder, default_run_log_path
from .scenario import (
    DEFAULT_SCENARIO,
    MASTER_CHECKS,
    SCORE_THRESHOLD,
    TWO_MASTER_DEMO_SCENARIO,
    Scenario,
)
from .trace_recorder import TraceRecorder, default_trace_dir, record_trace

__all__ = [
    "BerkshireGraph",
    "Variable",
    "Gradient",
    "Master",
    "MASTERS",
    "TextualGradientDescent",
    "DecisionRecord",
    "append_decision",
    "load_decisions",
    "realized_scores",
    "realized_scores_via_provider",
    "compute_returns",
    "PriceProvider",
    "StaticPriceProvider",
    "NetworkPriceProvider",
    "ReturnStats",
    "run_debate",
    "DebateResult",
    "DebateCase",
    "LLMClient",
    "StaticLLMClient",
    "OpenAICompatibleLLMClient",
    "apply_gradient",
    "build_rewrite_messages",
    "PromptScorer",
    "StaticPromptScorer",
    "ValidationResult",
    "validated_apply_gradient",
    "EvolutionReport",
    "RoundMetrics",
    "build_quality_gradients",
    "mean_prompt_quality",
    "run_multi_round",
    "LLMCallMetrics",
    "MetricsCollector",
    "configure_logging",
    "estimate_cost",
    "get_logger",
    "get_run_id",
    "new_run_id",
    "run_context",
    "RateLimiter",
    "check_api_key",
    "key_fingerprint",
    "ServiceMetrics",
    "render_prometheus",
    "LLMGradientGenerator",
    "build_critique_messages",
    "enrich_gradients_with_llm",
    "parse_issues",
    "Experience",
    "ExperienceStore",
    "ExperienceRetriever",
    "KeywordExperienceRetriever",
    "StaticExperienceRetriever",
    "classify_verdict",
    "experience_from_stats",
    "Hypothesis",
    "HypothesisStore",
    "group_experiences_by_hypothesis",
    "HypothesisProposer",
    "StaticHypothesisProposer",
    "ExperienceDrivenProposer",
    "LLMHypothesisProposer",
    "RDCycleMetrics",
    "RDCycleReport",
    "run_rd_cycle",
    "Scenario",
    "DEFAULT_SCENARIO",
    "TWO_MASTER_DEMO_SCENARIO",
    "MASTER_CHECKS",
    "SCORE_THRESHOLD",
    "RunRecord",
    "RunRecorder",
    "default_run_log_path",
    "ReflectionReport",
    "reflect_ticker",
    "TraceRecorder",
    "record_trace",
    "default_trace_dir",
    "build_experience_quality_fn",
    "run_full_cycle",
    "run_cron",
    "CronResult",
]
