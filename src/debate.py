#!/usr/bin/env python3
"""
多空对抗辩论（Bull / Bear debate）。

四大师当前是并行的，缺显式反方。本模块在 Layer 2（四大师分析）
与 Layer 3/4（财务验证 / 输出）之间插入一个轻量环节：
综合四大师的结构化产出，生成 bull case / bear case 与一个净判断，
作为 final_report 前的一步。

借鉴 TradingAgents 的 bull/bear researcher 对抗，但保持零外部依赖、
结构化输出（DebateResult，含 ok 字段），不靠解析展示文本。

约定：
- 复用 graph.py 的单一来源 MASTERS（不再硬编码四大师列表）。
- 输入是各大师的"看多信心" conviction ∈ [0,1]：>0.5 偏多，<0.5 偏空。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from .graph import MASTERS
except ImportError:  # pragma: no cover - flat PYTHONPATH=src
    from graph import MASTERS


# 净判断的中性区间：|net_score| < NET_MARGIN 视为 neutral
NET_MARGIN = 0.15


@dataclass
class DebateCase:
    """单方（多/空）论点的结构化汇总。"""

    side: str                  # "bull" / "bear"
    strength: float            # 该方强度 ∈ [0,1]
    supporters: List[str]      # 支持该方的大师中文名
    points: List[str]          # 结构化论据（展示用，控制流读 strength/supporters）


@dataclass
class DebateResult:
    """多空辩论结果。控制流应读 net_stance / net_score / ok，而非解析文本。"""

    bull: DebateCase
    bear: DebateCase
    net_stance: str            # "bullish" / "bearish" / "neutral"
    net_score: float           # bull.strength - bear.strength ∈ [-1,1]
    ok: bool                   # 是否形成明确（非中性）净判断
    rationale: List[str] = field(default_factory=list)

    def __str__(self) -> str:  # 展示兼容
        icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}.get(self.net_stance, "•")
        return f"{icon} 净判断: {self.net_stance} (net={self.net_score:+.3f})"


def run_debate(
    scores: Dict[str, float],
    issues_by_master: Optional[Dict[str, List[str]]] = None,
    net_margin: float = NET_MARGIN,
) -> DebateResult:
    """综合四大师信心分，产出 bull/bear case 与净判断。

    Args:
        scores: {prefix: conviction ∈ [0,1]}，>0.5 偏多、<0.5 偏空。
        issues_by_master: 可选 {prefix: [风险点...]}，用于充实 bear case。
        net_margin: 中性区间阈值。

    强度定义（确定性、可测）：
        bull_strength = mean_over_masters( max(0, score - 0.5) ) / 0.5
        bear_strength = mean_over_masters( max(0, 0.5 - score) ) / 0.5
        net_score     = bull_strength - bear_strength ∈ [-1, 1]
    """
    issues_by_master = issues_by_master or {}

    bull_points: List[str] = []
    bear_points: List[str] = []
    bull_supporters: List[str] = []
    bear_supporters: List[str] = []
    bull_acc = 0.0
    bear_acc = 0.0

    for m in MASTERS:
        s = float(scores.get(m.prefix, 0.5))
        bull_acc += max(0.0, s - 0.5)
        bear_acc += max(0.0, 0.5 - s)
        if s > 0.5:
            bull_supporters.append(m.name)
            bull_points.append(f"{m.name}（{m.focus}）看多，信心 {s:.2f}")
        elif s < 0.5:
            bear_supporters.append(m.name)
            risks = issues_by_master.get(m.prefix) or [f"{m.focus} 维度存疑"]
            bear_points.append(f"{m.name}（{m.focus}）看空，信心 {s:.2f}：{risks[0]}")
        else:
            bull_points.append(f"{m.name}（{m.focus}）中性，信心 {s:.2f}")

    n = len(MASTERS) or 1
    bull_strength = (bull_acc / n) / 0.5
    bear_strength = (bear_acc / n) / 0.5
    net_score = bull_strength - bear_strength

    if net_score >= net_margin:
        net_stance = "bullish"
    elif net_score <= -net_margin:
        net_stance = "bearish"
    else:
        net_stance = "neutral"

    rationale = [
        f"多方强度 {bull_strength:.3f}（{len(bull_supporters)} 位）",
        f"空方强度 {bear_strength:.3f}（{len(bear_supporters)} 位）",
        f"净判断 {net_stance}（net={net_score:+.3f}, margin={net_margin}）",
    ]

    return DebateResult(
        bull=DebateCase("bull", round(bull_strength, 6), bull_supporters, bull_points),
        bear=DebateCase("bear", round(bear_strength, 6), bear_supporters, bear_points),
        net_stance=net_stance,
        net_score=round(net_score, 6),
        ok=net_stance != "neutral",
        rationale=rationale,
    )
