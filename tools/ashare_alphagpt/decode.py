"""Human-readable formula decoding."""

from __future__ import annotations

from .ops import build_op_maps
from .vocab import FEATURE_COUNT, FEATURE_NAMES, VOCAB


def decode_formula(tokens: list[int] | None) -> str:
    if not tokens:
        return "N/A"
    _op_func, op_arity = build_op_maps(FEATURE_COUNT)
    stream = list(tokens)

    def _parse() -> str:
        if not stream:
            return ""
        t = stream.pop(0)
        if t < FEATURE_COUNT:
            return FEATURE_NAMES[t]
        args = [_parse() for _ in range(op_arity[t])]
        return f"{VOCAB[t]}({','.join(args)})"

    try:
        return _parse()
    except Exception:
        return "Invalid"
