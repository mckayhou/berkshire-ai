#!/usr/bin/env python3
"""
轻量 Run Recorder（借鉴 Qlib Recorder / MLflow 理念，零重依赖）。

把每次进化 / 反馈 / 反思的（run_id + 配置 + 指标 + 产物路径）追加 JSONL，
便于 list_runs / load_run 复现与对比。复用 observability.run_id 与 decision_log 落盘范式。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from observability import get_run_id, new_run_id
except ImportError:  # pragma: no cover
    from .observability import get_run_id, new_run_id


ENV_RUN_LOG = "BERKSHIRE_RUN_LOG"
DEFAULT_RUN_LOG = os.path.join(os.path.expanduser("~"), ".berkshire", "runs.jsonl")


def default_run_log_path() -> str:
    return os.environ.get(ENV_RUN_LOG, DEFAULT_RUN_LOG)


@dataclass
class RunRecord:
    """一次 run 的结构化记录。"""

    run_id: str
    event: str  # feedback | evolution | reflect | optimize | rd_cycle | status
    ticker: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    note: str = ""
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.ticker:
            self.ticker = str(self.ticker).strip().upper()
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class RunRecorder:
    """JSONL 追加式 run 记录器。"""

    def __init__(self, path: Optional[str] = None):
        self.path = path or default_run_log_path()

    def append(self, record: RunRecord) -> RunRecord:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if not record.run_id:
            record.run_id = get_run_id() or new_run_id()
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        return record

    def load(self) -> List[RunRecord]:
        if not os.path.isfile(self.path):
            return []
        rows: List[RunRecord] = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    rows.append(RunRecord(**data))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        return rows

    def list_runs(
        self,
        *,
        event: Optional[str] = None,
        ticker: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[RunRecord]:
        rows = self.load()
        if event:
            rows = [r for r in rows if r.event == event]
        if ticker:
            t = str(ticker).strip().upper()
            rows = [r for r in rows if r.ticker == t]
        if limit is not None and limit > 0:
            rows = rows[-limit:]
        return rows

    def load_run(self, run_id: str) -> Optional[RunRecord]:
        for row in reversed(self.load()):
            if row.run_id == run_id:
                return row
        return None

    def count(self) -> int:
        return len(self.load())
