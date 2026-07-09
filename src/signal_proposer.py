#!/usr/bin/env python3
"""
量化信号 → HypothesisProposer（V10.28）。

将 factor_screener / limitup_screener 的 JSON 输出转为 R 循环可消费的可证伪命题。
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    from .experience_store import Experience, ExperienceRetriever
    from .hypothesis import STATUS_OPEN, Hypothesis
    from .research_loop import HypothesisProposer
except ImportError:  # pragma: no cover - flat PYTHONPATH=src
    from experience_store import Experience, ExperienceRetriever
    from hypothesis import STATUS_OPEN, Hypothesis
    from research_loop import HypothesisProposer


def _scan_tickers(scan: Optional[dict]) -> List[dict]:
    if not scan or not scan.get("ok"):
        return []
    return list(scan.get("candidates") or [])


class FactorScanHypothesisProposer:
    """factor_screener_bridge / ashare_alphagpt screener JSON → Hypothesis。"""

    def __init__(self, factor_scan: dict):
        self.factor_scan = factor_scan

    def propose(
        self,
        *,
        ticker: str,
        recent: List[Experience],
        retriever: Optional[ExperienceRetriever] = None,
        k: int = 3,
    ) -> List[Hypothesis]:
        out: List[Hypothesis] = []
        for c in _scan_tickers(self.factor_scan)[:k]:
            tkr = str(c.get("ticker", "")).strip().upper()
            if not tkr:
                continue
            direction = c.get("direction", "neutral")
            score = float(c.get("score", 0))
            note = str(c.get("note", ""))[:200]
            out.append(
                Hypothesis(
                    ticker=tkr,
                    statement=f"因子筛选信号偏多：{direction}（score={score:+.3f}）",
                    reasoning=note or "AlphaGPT / factor_screener 候选",
                    justification=f"来源 factor_screener；扫描焦点 {ticker.upper()}",
                    falsifiable_condition="若 20 日 realized alpha < 0 且因子分转负则 refuted",
                    proposed_by="system",
                    status=STATUS_OPEN,
                )
            )
        return out


class LimitupScanHypothesisProposer:
    """limitup_screener_bridge JSON → Hypothesis。"""

    def __init__(self, limitup_scan: dict):
        self.limitup_scan = limitup_scan

    def propose(
        self,
        *,
        ticker: str,
        recent: List[Experience],
        retriever: Optional[ExperienceRetriever] = None,
        k: int = 3,
    ) -> List[Hypothesis]:
        out: List[Hypothesis] = []
        for c in _scan_tickers(self.limitup_scan)[:k]:
            tkr = str(c.get("ticker", "")).strip().upper()
            if not tkr:
                continue
            lu = float(c.get("limitup_score", c.get("score", 0)))
            dims = c.get("dimensions") or {}
            dim_txt = ", ".join(f"{a}={b}" for a, b in list(dims.items())[:3])
            out.append(
                Hypothesis(
                    ticker=tkr,
                    statement=f"五维打板评分 {lu:.0f}，短线情绪/封板质量偏多",
                    reasoning=dim_txt or str(c.get("note", ""))[:200],
                    justification=f"来源 limitup_screener；扫描焦点 {ticker.upper()}",
                    falsifiable_condition="若次日未封板且 limitup_score 跌破 50 则 refuted",
                    proposed_by="system",
                    status=STATUS_OPEN,
                )
            )
        return out


class CompositeHypothesisProposer:
    """串联多个 Proposer，去重 ticker+statement。"""

    def __init__(self, proposers: List[HypothesisProposer]):
        self.proposers = list(proposers)

    def propose(
        self,
        *,
        ticker: str,
        recent: List[Experience],
        retriever: Optional[ExperienceRetriever] = None,
        k: int = 3,
    ) -> List[Hypothesis]:
        seen: set = set()
        out: List[Hypothesis] = []
        for proposer in self.proposers:
            try:
                batch = proposer.propose(
                    ticker=ticker, recent=recent, retriever=retriever, k=k
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "hypothesis proposer failed",
                    exc_info=True,
                    extra={"proposer": type(proposer).__name__},
                )
                batch = []
            for h in batch:
                key = (h.ticker.upper(), h.statement[:80])
                if key in seen:
                    continue
                seen.add(key)
                out.append(h)
                if len(out) >= k:
                    return out
        return out


def proposer_from_signal_scans(
    *,
    factor_scan: Optional[dict] = None,
    limitup_scan: Optional[dict] = None,
    base: Optional[HypothesisProposer] = None,
) -> Optional[HypothesisProposer]:
    """从 thesis_queue 消费的 scan JSON 构建组合 Proposer。"""
    parts: List[HypothesisProposer] = []
    if base is not None:
        parts.append(base)
    if factor_scan:
        parts.append(FactorScanHypothesisProposer(factor_scan))
    if limitup_scan:
        parts.append(LimitupScanHypothesisProposer(limitup_scan))
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return CompositeHypothesisProposer(parts)
