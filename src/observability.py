#!/usr/bin/env python3
"""
可观测性：结构化日志 + run_id 贯穿 + LLM 成本/token/延迟埋点。

为什么需要它
--------------------------------------------------
生产系统要能回答：这次 run 调了几次 LLM？花了多少 token / 多少钱 / 多少延迟？
出问题时哪条日志属于哪次 run？此前项目用 `print()` 到处打，既无结构也无关联。
本模块提供最小但够用的一套：

- **结构化 JSON 日志**：`get_logger()` 输出单行 JSON（ts/level/logger/msg/run_id/extra），
  便于 grep / 采集到 ELK、Loki 等。
- **run_id 贯穿**：用 `contextvar` 存当前 run_id，`run_context()` 进入作用域后，
  该作用域内所有日志与埋点自动带上同一 run_id（线程/异步安全）。
- **LLM 埋点**：`LLMCallMetrics`（model/tokens/latency/cost/ok）+ `MetricsCollector`
  聚合一次 run 的总调用数/总 token/总成本/总延迟；`estimate_cost()` 按价目表估算。

零第三方依赖（仅标准库 logging / contextvars）。
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterator, List, Optional

# ---------------------------------------------------------------------------
# run_id 贯穿（contextvar）
# ---------------------------------------------------------------------------
_run_id: ContextVar[Optional[str]] = ContextVar("berkshire_run_id", default=None)


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def get_run_id() -> Optional[str]:
    return _run_id.get()


def set_run_id(run_id: Optional[str]) -> None:
    _run_id.set(run_id)


@contextmanager
def run_context(run_id: Optional[str] = None) -> Iterator[str]:
    """进入一个带 run_id 的作用域；作用域内所有日志/埋点自动带该 run_id。"""
    rid = run_id or new_run_id()
    token = _run_id.set(rid)
    try:
        yield rid
    finally:
        _run_id.reset(token)


# ---------------------------------------------------------------------------
# 结构化 JSON 日志
# ---------------------------------------------------------------------------
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message", "asctime", "taskName"
}


class JsonFormatter(logging.Formatter):
    """把 LogRecord 渲染成单行 JSON。自动注入当前 run_id 与 record 上的 extra 字段。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = getattr(record, "run_id", None) or get_run_id()
        if rid:
            payload["run_id"] = rid
        # 透传 extra={...} 里的自定义字段（跳过 logging 内置属性）
        for k, v in record.__dict__.items():
            if k not in _RESERVED and k != "run_id":
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


_CONFIGURED = False


def configure_logging(level: int = logging.INFO, stream=None) -> None:
    """配置 berkshire 根 logger 为结构化 JSON 输出（幂等，仅装一次 handler）。"""
    global _CONFIGURED
    logger = logging.getLogger("berkshire")
    if not _CONFIGURED:
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED = True
    logger.setLevel(level)


def get_logger(name: str = "berkshire") -> logging.Logger:
    """获取结构化 logger（首次调用自动配置）。name 不以 berkshire 开头则自动加前缀。"""
    configure_logging()
    if name != "berkshire" and not name.startswith("berkshire."):
        name = f"berkshire.{name}"
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# LLM 成本 / token / 延迟埋点
# ---------------------------------------------------------------------------
# 价目表：USD / 1M tokens (input, output)。未知模型用 _DEFAULT_PRICING 估算。
MODEL_PRICING: Dict[str, tuple] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "o3-mini": (1.10, 4.40),
    "deepseek-chat": (0.27, 1.10),
    "qwen-plus": (0.40, 1.20),
}
_DEFAULT_PRICING = (0.50, 1.50)


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """按价目表估算单次调用成本（USD）。未知模型用保守默认价。"""
    pin, pout = MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return (prompt_tokens / 1_000_000) * pin + (completion_tokens / 1_000_000) * pout


def approx_tokens(text: str) -> int:
    """无 tiktoken 依赖时的粗略 token 估算（~4 字符/token，中文偏保守）。"""
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class LLMCallMetrics:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    ok: bool = True
    error: Optional[str] = None
    run_id: Optional[str] = None


@dataclass
class MetricsCollector:
    """聚合一次（或多次）run 的 LLM 调用埋点。线程内使用即可。"""

    calls: List[LLMCallMetrics] = field(default_factory=list)

    def record(self, m: LLMCallMetrics) -> None:
        self.calls.append(m)

    @property
    def count(self) -> int:
        return len(self.calls)

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.calls)

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.calls)

    @property
    def error_count(self) -> int:
        return sum(0 if c.ok else 1 for c in self.calls)

    def summary(self) -> Dict[str, object]:
        return {
            "llm_calls": self.count,
            "llm_errors": self.error_count,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_latency_ms": round(self.total_latency_ms, 1),
        }


def log_llm_call(metrics: LLMCallMetrics, logger: Optional[logging.Logger] = None) -> None:
    """把一次 LLM 调用埋点写成结构化日志。"""
    lg = logger or get_logger("llm")
    rid = metrics.run_id or get_run_id()
    payload = asdict(metrics)
    payload.pop("run_id", None)
    lg.info("llm_call", extra={"event": "llm_call", "run_id": rid, **payload})
