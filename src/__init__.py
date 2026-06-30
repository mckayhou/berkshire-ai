"""
Berkshire AI V10 engine package.

Exports the main classes for TextGrad-based 4-masters analysis.
"""

from .graph import BerkshireGraph, Variable, Gradient, Master, MASTERS
from .optimizer import TextualGradientDescent
from .decision_log import DecisionRecord, append_decision, load_decisions
from .realized_feedback import (
    realized_scores,
    realized_scores_via_provider,
    compute_returns,
    PriceProvider,
    StaticPriceProvider,
    ReturnStats,
)
from .debate import run_debate, DebateResult, DebateCase

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
]
