"""
Berkshire AI V10 engine package.

Exports the main classes for TextGrad-based 4-masters analysis.
"""

from .debate import DebateCase, DebateResult, run_debate
from .decision_log import DecisionRecord, append_decision, load_decisions
from .graph import MASTERS, BerkshireGraph, Gradient, Master, Variable
from .optimizer import TextualGradientDescent
from .prompt_optimizer import (
    LLMClient,
    OpenAICompatibleLLMClient,
    StaticLLMClient,
    apply_gradient,
    build_rewrite_messages,
)
from .realized_feedback import (
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
    "ReturnStats",
    "run_debate",
    "DebateResult",
    "DebateCase",
    "LLMClient",
    "StaticLLMClient",
    "OpenAICompatibleLLMClient",
    "apply_gradient",
    "build_rewrite_messages",
]
