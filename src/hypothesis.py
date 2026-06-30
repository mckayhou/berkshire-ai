#!/usr/bin/env python3
"""
显式 Hypothesis 一等公民：可证伪的投资命题。

借鉴 [microsoft/RD-Agent] 的 `Hypothesis`：把「可证伪的投资命题」做成结构化一等
对象（命题 / 依据 / 证伪条件 / 状态 / 关联 ticker），而不是只把 prompt 文本当作
唯一可优化变量。这是后续 R/D 双循环（主动提案 → 验证 → 沉淀）的地基。

本次范围（避免过度工程）
--------------------------------------------------
只落地**数据对象 + 最小 JSONL 存储 + 测试**，**不强行接入主链路**（graph/optimizer
不变）。仅预留「经验可按 hypothesis 聚合」的纯函数接口，供将来 R 循环复用。

工程约束（与 decision_log / experience_store 一致）
--------------------------------------------------
- 零外部依赖（仅标准库）；结构化字段，控制流读字段不解析文本。
- 复用 graph.py 的单一来源（MASTER_PREFIXES）校验 proposed_by。
- JSONL 落盘，路径可用 BERKSHIRE_HYPOTHESIS_LOG 覆盖。
"""

from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from graph import MASTER_PREFIXES
except ImportError:  # pragma: no cover - 包内导入回退
    from .graph import MASTER_PREFIXES

ENV_LOG_PATH = "BERKSHIRE_HYPOTHESIS_LOG"
DEFAULT_LOG_PATH = os.path.join(os.path.expanduser("~"), ".berkshire", "hypotheses.jsonl")

# status 取值（控制流读字段）
STATUS_OPEN = "open"
STATUS_CONFIRMED = "confirmed"
STATUS_REFUTED = "refuted"
_VALID_STATUS = (STATUS_OPEN, STATUS_CONFIRMED, STATUS_REFUTED)

PROPOSED_BY_SYSTEM = "system"


def default_log_path() -> str:
    """假设库默认路径（环境变量可覆盖）。"""
    return os.environ.get(ENV_LOG_PATH, DEFAULT_LOG_PATH)


@dataclass
class Hypothesis:
    """一条可证伪的投资命题（结构化一等对象）。

    Fields:
        id:                    唯一 id（留空则自动生成）
        ticker:                关联标的
        statement:             可证伪的投资命题
        reasoning:             为何成立（逻辑链）
        justification:         证据/依据支撑
        falsifiable_condition: 何种观测出现即证伪
        proposed_by:           提出者（MASTER_PREFIXES 之一或 "system"）
        status:                open / confirmed / refuted
        linked_decision_id:    关联的决策 trace_id（可选）
        created_at:            创建时间（ISO）
    """

    ticker: str
    statement: str
    reasoning: str = ""
    justification: str = ""
    falsifiable_condition: str = ""
    proposed_by: str = PROPOSED_BY_SYSTEM
    status: str = STATUS_OPEN
    linked_decision_id: Optional[str] = None
    id: str = ""
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        self.ticker = str(self.ticker).strip().upper()
        if not self.ticker:
            raise ValueError("ticker 不能为空")
        if not str(self.statement).strip():
            raise ValueError("statement 不能为空")
        if self.proposed_by != PROPOSED_BY_SYSTEM and self.proposed_by not in MASTER_PREFIXES:
            raise ValueError(
                f"proposed_by '{self.proposed_by}' 应为 {PROPOSED_BY_SYSTEM} 或 {MASTER_PREFIXES}"
            )
        if self.status not in _VALID_STATUS:
            raise ValueError(f"非法 status: {self.status!r}")
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "Hypothesis":
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})


class HypothesisStore:
    """JSONL 落盘的最小假设库（复用 decision_log 风格；路径可被环境变量覆盖）。"""

    def __init__(self, path: Optional[str] = None):
        self.path = path or default_log_path()

    def append(self, hyp: Hypothesis) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(hyp.to_dict(), ensure_ascii=False) + "\n")
        return self.path

    def load(self) -> List[Hypothesis]:
        if not os.path.exists(self.path):
            return []
        out: List[Hypothesis] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(Hypothesis.from_dict(json.loads(line)))
                except (ValueError, TypeError):  # 单行损坏跳过，不崩
                    continue
        return out

    def get(self, hypothesis_id: str) -> Optional[Hypothesis]:
        for h in self.load():
            if h.id == hypothesis_id:
                return h
        return None

    def for_ticker(self, ticker: str) -> List[Hypothesis]:
        tkr = str(ticker).strip().upper()
        return [h for h in self.load() if h.ticker == tkr]


def group_experiences_by_hypothesis(experiences: List[Any]) -> Dict[str, List[Any]]:
    """预留接口：把经验（experience_store.Experience，鸭子类型）按 hypothesis_id 聚合。

    无 hypothesis_id 的经验归入 key ""。纯函数、零依赖，供将来 R 循环按假设复盘复用。
    """
    grouped: Dict[str, List[Any]] = defaultdict(list)
    for exp in experiences:
        hid = getattr(exp, "hypothesis_id", None) or ""
        grouped[hid].append(exp)
    return dict(grouped)
