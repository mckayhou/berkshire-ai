"""A-share factor mining (AlphaGPT times.py logic) for berkshire-ai.

Heavy deps (torch / full decode path) are **lazy** so modules like
``limitup_scoring`` can be imported without ``pip install '.[factor-mining]'``.

Training / formula mining still requires: ``pip install '.[factor-mining]'``.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "MiningConfig",
    "decode_formula",
    "default_formula_path",
    "load_formula",
    "save_formula",
    "FEATURE_NAMES",
    "VOCAB",
    "VOCAB_SIZE",
]


def __getattr__(name: str) -> Any:
    if name == "MiningConfig":
        from .config import MiningConfig

        return MiningConfig
    if name == "decode_formula":
        from .decode import decode_formula

        return decode_formula
    if name in ("default_formula_path", "load_formula", "save_formula"):
        from . import formula_store

        return getattr(formula_store, name)
    if name in ("FEATURE_NAMES", "VOCAB", "VOCAB_SIZE"):
        from . import vocab

        return getattr(vocab, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
