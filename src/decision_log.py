#!/usr/bin/env python3
"""
Decision / thesis 持久化日志（已实现收益反馈闭环的第一环）。

借鉴 TradingAgents：每次跑完把"当时的判断 + 价格锚点"落盘，
事后再用真实价格回填，生成 reward 喂回 TextGrad。

设计约束：
- 零外部依赖（只用标准库）。
- 结构化记录（DecisionRecord），控制流读字段而非解析文本。
- 复用 graph.py 的单一来源（MASTER_PREFIXES）校验四大师评分。
- 落盘 JSONL（追加友好），路径可用环境变量 BERKSHIRE_DECISION_LOG 覆盖。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from graph import MASTER_PREFIXES
except ImportError:  # pragma: no cover - 包内导入回退
    from .graph import MASTER_PREFIXES


# 环境变量优先；否则落在 ~/.berkshire/decisions.jsonl
ENV_LOG_PATH = "BERKSHIRE_DECISION_LOG"
DEFAULT_LOG_PATH = os.path.join(os.path.expanduser("~"), ".berkshire", "decisions.jsonl")


def default_log_path() -> str:
    """决策日志默认路径（环境变量可覆盖）。"""
    return os.environ.get(ENV_LOG_PATH, DEFAULT_LOG_PATH)


@dataclass
class DecisionRecord:
    """一次投研决策的结构化快照。

    Fields:
        ticker:           标的代码
        date:             决策日期（ISO，YYYY-MM-DD）
        scores:           四大师当时的判断/信心评分 {prefix: 0~1}
        price_anchor:     决策时的价格锚点（标的）
        benchmark:        基准代码（如 "SPX" / "000300"），可选
        benchmark_anchor: 决策时的基准价格锚点，可选
        note:             备注（自由文本，仅展示，不用于控制流）
        analyses:         各大师分析正文 {prefix: text}，供 ∇_LLM 批评素材，可选
        trace_id:         关联的计算图 trace_id，可选
        hypothesis_id:    关联的可证伪假设 id（衔接 hypothesis.py），可选
        created_at:       落盘时间（ISO）
    """

    ticker: str
    date: str
    scores: Dict[str, float]
    price_anchor: float
    benchmark: Optional[str] = None
    benchmark_anchor: Optional[float] = None
    note: str = ""
    analyses: Optional[Dict[str, str]] = None
    trace_id: Optional[str] = None
    hypothesis_id: Optional[str] = None
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        self.ticker = str(self.ticker).strip().upper()
        if not self.ticker:
            raise ValueError("ticker 不能为空")
        if self.price_anchor is None or float(self.price_anchor) <= 0:
            raise ValueError(f"price_anchor 必须为正数: {self.price_anchor}")
        self.price_anchor = float(self.price_anchor)
        if self.benchmark_anchor is not None:
            if float(self.benchmark_anchor) <= 0:
                raise ValueError(f"benchmark_anchor 必须为正数: {self.benchmark_anchor}")
            self.benchmark_anchor = float(self.benchmark_anchor)
        # 评分归一化为 float，并校验 key 属于单一来源的四大师
        clean: Dict[str, float] = {}
        for k, v in (self.scores or {}).items():
            if k not in MASTER_PREFIXES:
                raise ValueError(f"未知大师前缀 '{k}'，应属于 {MASTER_PREFIXES}")
            clean[k] = float(v)
        self.scores = clean
        if self.analyses:
            clean_a: Dict[str, str] = {}
            for k, text in self.analyses.items():
                if k in MASTER_PREFIXES and text:
                    clean_a[k] = str(text)
            self.analyses = clean_a or None
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "DecisionRecord":
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})


def append_decision(record: DecisionRecord, path: Optional[str] = None) -> str:
    """追加一条决策到 JSONL 日志，返回落盘路径。"""
    path = path or default_log_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    return path


def load_decisions(path: Optional[str] = None) -> List[DecisionRecord]:
    """读取全部决策记录（空文件/不存在返回空列表）。"""
    path = path or default_log_path()
    if not os.path.exists(path):
        return []
    records: List[DecisionRecord] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(DecisionRecord.from_dict(json.loads(line)))
    return records


def decisions_for_ticker(ticker: str, path: Optional[str] = None) -> List[DecisionRecord]:
    """按 ticker 过滤（按 date 升序）。"""
    ticker = str(ticker).strip().upper()
    rows = [r for r in load_decisions(path) if r.ticker == ticker]
    return sorted(rows, key=lambda r: r.date)


def latest_decision(ticker: str, path: Optional[str] = None) -> Optional[DecisionRecord]:
    """取某 ticker 最近一条决策（按 date），无则 None。"""
    rows = decisions_for_ticker(ticker, path)
    return rows[-1] if rows else None
