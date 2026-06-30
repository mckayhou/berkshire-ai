"""
Berkshire AI V10 engine package.

Exports the main classes for TextGrad-based 4-masters analysis.
"""

from .debate import DebateCase, DebateResult, run_debate
from .decision_log import DecisionRecord, append_decision, load_decisions
from .eval_harness import (
    EvolutionReport,
    RoundMetrics,
    build_quality_gradients,
    mean_prompt_quality,
    run_multi_round,
)
from .graph import MASTERS, BerkshireGraph, Gradient, Master, Variable
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
    compute_returns,
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
]
