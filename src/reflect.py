#!/usr/bin/env python3
"""
对比反思（Contrastive Reflection）：同一标的多次决策/经验的成败对比。

从 experience_store 与 decision_log 读取历史，归纳分歧点、成功因素与失败模式。
供 evolution_cli reflect / optimize 子命令使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from decision_log import load_decisions
    from experience_store import VERDICT_CONFIRMED, VERDICT_REFUTED, Experience, ExperienceStore
    from graph import MASTER_PREFIXES
except ImportError:  # pragma: no cover
    from .decision_log import load_decisions
    from .experience_store import VERDICT_CONFIRMED, VERDICT_REFUTED, Experience, ExperienceStore
    from .graph import MASTER_PREFIXES


@dataclass
class ReflectionReport:
    """对比反思结构化输出。"""

    ticker: str
    n_decisions: int
    n_experiences: int
    high_alpha: List[Experience] = field(default_factory=list)
    low_alpha: List[Experience] = field(default_factory=list)
    divergence_points: List[str] = field(default_factory=list)
    success_factors: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)
    volatility_root_cause: str = ""
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "n_decisions": self.n_decisions,
            "n_experiences": self.n_experiences,
            "divergence_points": self.divergence_points,
            "success_factors": self.success_factors,
            "failure_modes": self.failure_modes,
            "volatility_root_cause": self.volatility_root_cause,
            "suggestions": self.suggestions,
            "high_alpha_count": len(self.high_alpha),
            "low_alpha_count": len(self.low_alpha),
        }


def _master_conviction_gap(
    high: List[Experience], low: List[Experience], prefix: str
) -> Optional[float]:
    """高 alpha 与低 alpha 组在某大师信心上的平均差。"""
    def _avg(rows: List[Experience]) -> Optional[float]:
        vals = [e.stances.get(prefix) for e in rows if e.stances.get(prefix) is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    ah, al = _avg(high), _avg(low)
    if ah is None or al is None:
        return None
    return ah - al


def reflect_ticker(
    ticker: str,
    *,
    decision_path: Optional[str] = None,
    experience_path: Optional[str] = None,
    alpha_split: float = 0.0,
) -> ReflectionReport:
    """对单一标的做对比反思。

    优先使用 ExperienceStore（含 alpha）；decision_log 仅补充计数。
    alpha > alpha_split → high 组；alpha < alpha_split → low 组。
    """
    tkr = str(ticker).strip().upper()
    decisions = [d for d in load_decisions(path=decision_path) if d.ticker == tkr]
    store = ExperienceStore(path=experience_path)
    exps = [e for e in store.load() if e.ticker == tkr]

    high = [e for e in exps if e.alpha > alpha_split]
    low = [e for e in exps if e.alpha < alpha_split]

    report = ReflectionReport(
        ticker=tkr,
        n_decisions=len(decisions),
        n_experiences=len(exps),
        high_alpha=high,
        low_alpha=low,
    )

    if len(exps) < 2:
        report.volatility_root_cause = "经验不足（<2 条），无法做可靠对比反思"
        report.suggestions.append("继续积累决策并实现收益反馈后再运行 reflect")
        return report

    # 大师信心分歧
    for prefix in MASTER_PREFIXES:
        gap = _master_conviction_gap(high, low, prefix)
        if gap is not None and abs(gap) >= 0.15:
            direction = "更高" if gap > 0 else "更低"
            report.divergence_points.append(
                f"{prefix} 信心在成功组比失败组平均 {direction} {abs(gap):.2f}"
            )

    # 成败模式
    refuted = [e for e in exps if e.verdict == VERDICT_REFUTED]
    confirmed = [e for e in exps if e.verdict == VERDICT_CONFIRMED]
    if confirmed:
        avg_alpha = sum(e.alpha for e in confirmed) / len(confirmed)
        report.success_factors.append(
            f"已证实假设 {len(confirmed)} 条，平均 alpha={avg_alpha:.3f}"
        )
    if refuted:
        overconfident = [
            e for e in refuted
            if max(e.stances.values(), default=0) >= 0.85
        ]
        if overconfident:
            report.failure_modes.append(
                f"{len(overconfident)} 次高信心被证伪（过度自信）"
            )
        report.failure_modes.append(f"共 {len(refuted)} 条经验被 refuted")

    if report.divergence_points:
        report.volatility_root_cause = "大师信心与事后 alpha 校准不一致"
    elif refuted and confirmed:
        report.volatility_root_cause = "同一标的上信心分与实现收益反复背离"
    else:
        report.volatility_root_cause = "样本间 alpha 分布分散，需更多数据"

    if report.failure_modes:
        report.suggestions.append("对 refuted 经验召回 few-shot，强化 D 段改写约束")
    if report.divergence_points:
        report.suggestions.append("检查分歧最大的大师 prompt 是否缺少反偏见检查")

    return report
