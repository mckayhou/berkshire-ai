#!/usr/bin/env python3
"""
生产级 quality_fn：用历史经验中的「信心 vs alpha」校准误差估计 prompt 质量。

供 eval_harness / run_rd_cycle / optimize 使用；无经验时回退到中性分 0.72。
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

try:
    from experience_store import Experience, ExperienceStore
    from graph import MASTER_PREFIXES
except ImportError:  # pragma: no cover
    from .experience_store import Experience, ExperienceStore
    from .graph import MASTER_PREFIXES

DEFAULT_NEUTRAL = 0.72


def _master_from_prompt(prompt: str) -> Optional[str]:
    for prefix in MASTER_PREFIXES:
        if prefix in prompt or f"{prefix}_prompt" in prompt:
            return prefix
    return None


def conviction_alpha_errors(experiences: List[Experience]) -> Dict[str, float]:
    """各大师 |stance - realized_base| 的历史均值（越小越好）。"""
    sums: Dict[str, float] = {p: 0.0 for p in MASTER_PREFIXES}
    counts: Dict[str, int] = {p: 0 for p in MASTER_PREFIXES}
    for exp in experiences:
        rb = float(exp.realized_base)
        for prefix, stance in (exp.stances or {}).items():
            if prefix in sums:
                sums[prefix] += abs(float(stance) - rb)
                counts[prefix] += 1
    return {
        p: (sums[p] / counts[p] if counts[p] else 0.5)
        for p in MASTER_PREFIXES
    }


def build_experience_quality_fn(
    ticker: Optional[str] = None,
    *,
    store: Optional[ExperienceStore] = None,
    neutral: float = DEFAULT_NEUTRAL,
) -> Callable[[str], float]:
    """构建 quality_fn：误差大 → 低分（需优化）。"""
    exp_store = store or ExperienceStore()
    exps = exp_store.load()
    if ticker:
        tkr = str(ticker).strip().upper()
        exps = [e for e in exps if e.ticker == tkr]
    errors = conviction_alpha_errors(exps) if exps else {}

    def quality_fn(prompt: str) -> float:
        prefix = _master_from_prompt(prompt)
        if prefix and prefix in errors:
            # 误差 0 → 1.0；误差 0.5 → 0.5
            return max(0.35, min(0.95, 1.0 - errors[prefix]))
        return neutral

    return quality_fn
