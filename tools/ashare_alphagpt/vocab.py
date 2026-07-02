"""Formula vocabulary: features + operators."""

from __future__ import annotations

from .ops import OPS_CONFIG

FEATURE_NAMES: tuple[str, ...] = ("RET", "RET5", "VOL_CHG", "V_RET", "TREND")
OPERATOR_NAMES: tuple[str, ...] = tuple(cfg[0] for cfg in OPS_CONFIG)
VOCAB: tuple[str, ...] = FEATURE_NAMES + OPERATOR_NAMES
VOCAB_SIZE: int = len(VOCAB)
FEATURE_COUNT: int = len(FEATURE_NAMES)
