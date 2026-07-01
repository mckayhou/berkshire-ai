#!/usr/bin/env python3
"""
轨迹自动记录（QwenPaw / OpenClaw 侧）。

每次投研/反馈/进化任务完成后追加 JSON 轨迹，默认目录
~/.qwenpaw/berkshire_traces/（可用 BERKSHIRE_TRACE_DIR 覆盖）。
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from observability import get_run_id
except ImportError:  # pragma: no cover
    from .observability import get_run_id

ENV_TRACE_DIR = "BERKSHIRE_TRACE_DIR"
DEFAULT_TRACE_DIR = os.path.join(os.path.expanduser("~"), ".qwenpaw", "berkshire_traces")


def default_trace_dir() -> str:
    return os.environ.get(ENV_TRACE_DIR, DEFAULT_TRACE_DIR)


@dataclass
class TraceRecord:
    """单条投研/进化轨迹（对齐 config/skill.md 格式）。"""

    task_id: str
    ticker: str
    timestamp: str
    phase: str  # hunter|maker|checker|pm|feedback|evolution|reflect|rd_cycle
    agent_role: str = ""
    model_used: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    score: float = 0.0
    errors: List[str] = field(default_factory=list)
    notes: str = ""
    run_id: Optional[str] = None

    def __post_init__(self) -> None:
        self.ticker = str(self.ticker).strip().upper()
        if not self.task_id:
            self.task_id = f"trace-{uuid.uuid4().hex[:12]}"
        if not self.run_id:
            self.run_id = get_run_id()


class TraceRecorder:
    """按 ticker+日期分文件追加轨迹（每文件 JSON 数组，便于 QwenPaw 消费）。"""

    def __init__(self, directory: Optional[str] = None):
        self.directory = directory or default_trace_dir()

    def _path_for(self, ticker: str) -> str:
        tkr = str(ticker).strip().upper() or "UNKNOWN"
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in tkr)
        return os.path.join(self.directory, f"{safe}_{day}.json")

    def append(self, record: TraceRecord) -> str:
        os.makedirs(self.directory, exist_ok=True)
        path = self._path_for(record.ticker)
        rows: List[dict] = []
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    rows = data
            except (json.JSONDecodeError, OSError):
                rows = []
        if not record.timestamp:
            record.timestamp = datetime.now(timezone.utc).isoformat()
        rows.append(asdict(record))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=2)
        return path

    def list_files(self) -> List[str]:
        if not os.path.isdir(self.directory):
            return []
        return sorted(
            os.path.join(self.directory, f)
            for f in os.listdir(self.directory)
            if f.endswith(".json")
        )

    def count(self) -> int:
        total = 0
        for path in self.list_files():
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    total += len(data)
            except (json.JSONDecodeError, OSError):
                continue
        return total


def record_trace(
    ticker: str,
    phase: str,
    *,
    agent_role: str = "",
    score: float = 0.0,
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    notes: str = "",
    errors: Optional[List[str]] = None,
) -> Optional[str]:
    """便捷写入；失败返回 None，不崩主链路。"""
    try:
        rec = TraceRecorder()
        path = rec.append(
            TraceRecord(
                task_id="",
                ticker=ticker,
                timestamp=datetime.now(timezone.utc).isoformat(),
                phase=phase,
                agent_role=agent_role,
                input_data=dict(input_data or {}),
                output_data=dict(output_data or {}),
                score=float(score),
                notes=notes,
                errors=list(errors or []),
            )
        )
        return path
    except OSError:
        return None
