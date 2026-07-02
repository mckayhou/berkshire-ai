"""Load / save mined factor formulas."""

from __future__ import annotations

import json
from pathlib import Path

from .config import MiningConfig


def default_formula_path(cfg: MiningConfig | None = None) -> Path:
    cfg = cfg or MiningConfig()
    return cfg.output_dir / "best_ashare_formula.json"


def load_formula(path: Path | str | None = None) -> dict:
    """Return dict with formula_tokens, formula, best_score."""
    p = Path(path) if path else default_formula_path()
    if not p.is_file():
        raise FileNotFoundError(f"Formula not found: {p}. Run train first.")
    data = json.loads(p.read_text(encoding="utf-8"))
    tokens = data.get("formula_tokens")
    if tokens is None and isinstance(data, list):
        tokens = data
    if not tokens:
        raise ValueError(f"Invalid formula file (no formula_tokens): {p}")
    return {
        "path": str(p),
        "formula_tokens": list(tokens),
        "formula": data.get("formula", ""),
        "best_score": data.get("best_score"),
    }


def save_formula(
    tokens: list[int],
    *,
    formula_str: str = "",
    best_score: float | None = None,
    path: Path | str | None = None,
) -> Path:
    cfg = MiningConfig()
    out = Path(path) if path else default_formula_path(cfg)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "formula_tokens": tokens,
        "formula": formula_str,
        "best_score": best_score,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
