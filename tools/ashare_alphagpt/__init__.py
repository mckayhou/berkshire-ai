"""A-share factor mining (AlphaGPT times.py logic) for berkshire-ai.

Requires optional deps: pip install '.[factor-mining]'
"""

from .config import MiningConfig
from .decode import decode_formula
from .formula_store import default_formula_path, load_formula, save_formula
from .vocab import FEATURE_NAMES, VOCAB, VOCAB_SIZE

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
