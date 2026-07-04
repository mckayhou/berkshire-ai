#!/usr/bin/env python3
"""
多源证据通道 + EvidenceBrainstormProposer（V10.29）。

借鉴 AgentX Brainstorm Agent 的四路证据加权方案：
  1. 历史经验（ExperienceStore）—— 已有
  2. 异动信号扫描（AkTools / signal_proposer）—— V10.28 已建
  3. 知识图谱节点（graphify）
  4. 研报/行业摘要（报告文本）

每条通道实现 `EvidenceChannel` 协议，brainstorm proposer 聚合所有通道
产出的证据生成可证伪 Hypothesis。通道失败静默降级、绝不阻塞主链路。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

try:
    from experience_store import Experience, ExperienceRetriever
    from hypothesis import STATUS_OPEN, Hypothesis
    from research_loop import HypothesisProposer
    from sanitize import sanitize_untrusted
except ImportError:  # pragma: no cover
    from .experience_store import Experience, ExperienceRetriever
    from .hypothesis import STATUS_OPEN, Hypothesis
    from .research_loop import HypothesisProposer
    from .sanitize import sanitize_untrusted

logger = logging.getLogger(__name__)


@dataclass
class Evidence:
    """单条结构化证据（来自任一通道）。"""

    channel: str
    ticker: str
    summary: str
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class EvidenceChannel(Protocol):
    """可注入的证据通道接口。"""

    name: str

    def collect(self, ticker: str, k: int = 5) -> List[Evidence]: ...


# --- 具体通道实现 ---


class ExperienceEvidenceChannel:
    """从 ExperienceStore 提取历史成败作为证据。"""

    name = "experience"

    def __init__(self, retriever: ExperienceRetriever):
        self._retriever = retriever

    def collect(self, ticker: str, k: int = 5) -> List[Evidence]:
        try:
            experiences = self._retriever.retrieve(ticker=ticker, k=k)
        except Exception:  # noqa: BLE001
            return []
        out: List[Evidence] = []
        for exp in experiences:
            conf = 0.8 if exp.verdict == "confirmed" else 0.3
            out.append(
                Evidence(
                    channel=self.name,
                    ticker=exp.ticker,
                    summary=f"[{exp.verdict}] {exp.lesson or f'alpha={exp.alpha:.3f}'}",
                    confidence=conf,
                    metadata={"date": exp.date, "alpha": exp.alpha},
                )
            )
        return out[:k]


class AnomalyScanEvidenceChannel:
    """从量化信号扫描结果（factor_scan / limitup_scan JSON）提取证据。"""

    name = "anomaly_scan"

    def __init__(
        self,
        scan_loader: Optional[Callable[[], Optional[Dict[str, Any]]]] = None,
    ):
        self._loader = scan_loader

    def collect(self, ticker: str, k: int = 5) -> List[Evidence]:
        if self._loader is None:
            return []
        try:
            scan = self._loader()
        except Exception:  # noqa: BLE001
            return []
        if not scan or not scan.get("ok"):
            return []
        out: List[Evidence] = []
        for c in (scan.get("candidates") or [])[:k]:
            tkr = str(c.get("ticker", "")).strip().upper()
            if not tkr:
                continue
            direction = c.get("direction", "neutral")
            score = float(c.get("score", 0))
            out.append(
                Evidence(
                    channel=self.name,
                    ticker=tkr,
                    summary=f"信号 {direction}（score={score:+.3f}）",
                    confidence=min(1.0, abs(score)),
                    metadata=c,
                )
            )
        return out[:k]


class GraphifyEvidenceChannel:
    """从 graphify 知识图谱查询相关节点摘要作为证据。"""

    name = "knowledge_graph"

    def __init__(self, graph_json_path: Optional[str] = None):
        self._path = graph_json_path

    def _load_graph(self) -> Optional[Dict]:
        import os
        path = self._path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "graphify-out",
            "graph.json",
        )
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            return None

    def collect(self, ticker: str, k: int = 5) -> List[Evidence]:
        graph = self._load_graph()
        if not graph:
            return []
        nodes = graph.get("nodes") or []
        out: List[Evidence] = []
        tkr_lower = ticker.lower()
        for node in nodes:
            label = str(node.get("label", ""))
            src = str(node.get("src", ""))
            if tkr_lower in label.lower() or tkr_lower in src.lower():
                out.append(
                    Evidence(
                        channel=self.name,
                        ticker=ticker.upper(),
                        summary=label[:200],
                        confidence=0.4,
                        metadata={"src": src, "community": node.get("community")},
                    )
                )
                if len(out) >= k:
                    break
        return out


class ReportEvidenceChannel:
    """从研报/行业摘要文本提取证据（传入回调，不耦合具体数据源）。"""

    name = "report"

    def __init__(
        self,
        report_loader: Optional[Callable[[str], List[str]]] = None,
    ):
        self._loader = report_loader

    def collect(self, ticker: str, k: int = 5) -> List[Evidence]:
        if self._loader is None:
            return []
        try:
            snippets = self._loader(ticker)
        except Exception:  # noqa: BLE001
            return []
        out: List[Evidence] = []
        for s in (snippets or [])[:k]:
            out.append(
                Evidence(
                    channel=self.name,
                    ticker=ticker.upper(),
                    summary=str(s)[:300],
                    confidence=0.6,
                )
            )
        return out


# --- 聚合层 ---


class EvidenceBrainstormProposer:
    """多源证据聚合 → 加权排序 → 生成可证伪 Hypothesis（零 LLM 版本）。

    对应 AgentX Brainstorm Agent 的核心逻辑：从多通道收集证据，
    按 confidence 加权排序，为每条高质量证据生成一条 Hypothesis。
    """

    def __init__(
        self,
        channels: List[EvidenceChannel],
        *,
        min_confidence: float = 0.3,
        base_proposer: Optional[HypothesisProposer] = None,
    ):
        self.channels = list(channels)
        self.min_confidence = min_confidence
        self._base = base_proposer

    def propose(
        self,
        *,
        ticker: str,
        recent: List[Experience],
        retriever: Optional[ExperienceRetriever] = None,
        k: int = 3,
    ) -> List[Hypothesis]:
        all_evidence: List[Evidence] = []

        for ch in self.channels:
            try:
                batch = ch.collect(ticker, k=k)
                all_evidence.extend(batch)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "evidence channel failed",
                    exc_info=True,
                    extra={"channel": getattr(ch, "name", "unknown")},
                )

        filtered = [
            e for e in all_evidence if e.confidence >= self.min_confidence
        ]
        filtered.sort(key=lambda e: e.confidence, reverse=True)

        seen: set = set()
        hypotheses: List[Hypothesis] = []

        if self._base is not None:
            try:
                base_hyps = self._base.propose(
                    ticker=ticker, recent=recent, retriever=retriever, k=k
                )
                for h in base_hyps:
                    key = (h.ticker, h.statement[:60])
                    if key not in seen:
                        seen.add(key)
                        hypotheses.append(h)
            except Exception:  # noqa: BLE001
                pass

        for ev in filtered:
            if len(hypotheses) >= k:
                break
            key = (ev.ticker.upper(), ev.summary[:60])
            if key in seen:
                continue
            seen.add(key)
            hypotheses.append(
                Hypothesis(
                    ticker=ev.ticker.upper() or ticker.upper(),
                    statement=f"[{ev.channel}] {ev.summary}",
                    reasoning=f"来源通道 {ev.channel}；confidence={ev.confidence:.2f}",
                    justification=json.dumps(
                        ev.metadata, ensure_ascii=False, default=str
                    )[:200] if ev.metadata else "",
                    falsifiable_condition="若后续验证 alpha < 0 或信号消失则 refuted",
                    proposed_by="system",
                    status=STATUS_OPEN,
                )
            )

        return hypotheses[:k]


def build_brainstorm_proposer(
    *,
    retriever: Optional[ExperienceRetriever] = None,
    factor_scan_loader: Optional[Callable[[], Optional[Dict]]] = None,
    limitup_scan_loader: Optional[Callable[[], Optional[Dict]]] = None,
    report_loader: Optional[Callable[[str], List[str]]] = None,
    graph_json_path: Optional[str] = None,
    base_proposer: Optional[HypothesisProposer] = None,
    min_confidence: float = 0.3,
) -> EvidenceBrainstormProposer:
    """工厂函数：从可用数据源构建多通道 brainstorm proposer。"""
    channels: List[EvidenceChannel] = []

    if retriever is not None:
        channels.append(ExperienceEvidenceChannel(retriever))
    if factor_scan_loader is not None:
        channels.append(AnomalyScanEvidenceChannel(factor_scan_loader))
    if limitup_scan_loader is not None:
        channels.append(AnomalyScanEvidenceChannel(limitup_scan_loader))
    channels.append(GraphifyEvidenceChannel(graph_json_path))
    if report_loader is not None:
        channels.append(ReportEvidenceChannel(report_loader))

    return EvidenceBrainstormProposer(
        channels,
        min_confidence=min_confidence,
        base_proposer=base_proposer,
    )
