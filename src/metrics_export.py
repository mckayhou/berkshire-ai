#!/usr/bin/env python3
"""
指标导出：进程级计数器 + Prometheus 文本格式（生产化硬化 档D）。

为什么需要它
--------------------------------------------------
`observability.MetricsCollector` 聚合的是「一次 run 内」的 LLM 埋点；服务长期运行
还需要「进程级」可被监控系统拉取的指标：各端点请求数 / 成功 / 失败 / 鉴权拒绝 /
被限流次数等。本模块提供：

- `ServiceMetrics`：线程安全的命名计数器（incr/get/snapshot）；
- `render_prometheus()`：把计数器 + （可选）LLM 聚合渲染成 Prometheus 文本格式，
  由 `service` 的 `/metrics` 端点暴露，供 Prometheus / VictoriaMetrics 抓取。

零第三方依赖（不引入 prometheus_client，保持核心可离线）。
"""

from __future__ import annotations

import threading
from typing import Dict, Optional

try:
    from .observability import MetricsCollector
except ImportError:  # pragma: no cover - flat PYTHONPATH=src
    from observability import MetricsCollector

_METRIC_PREFIX = "berkshire"


class ServiceMetrics:
    """线程安全的命名计数器集合（进程级）。"""

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._lock = threading.Lock()

    def incr(self, name: str, amount: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + amount

    def get(self, name: str) -> float:
        with self._lock:
            return self._counters.get(name, 0.0)

    def snapshot(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._counters)


def _sanitize_metric_name(name: str) -> str:
    """把计数器名规整为合法 Prometheus 指标名（[a-zA-Z0-9_]）。"""
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in name)


def render_prometheus(
    metrics: ServiceMetrics,
    llm: Optional[MetricsCollector] = None,
) -> str:
    """渲染 Prometheus 文本格式（text/plain; version=0.0.4）。

    - 每个服务计数器导出为 `berkshire_<name>_total`（counter 类型）；
    - 若给了 LLM 聚合，附带 token/cost/latency/calls 几个 gauge。
    """
    lines: list[str] = []
    snap = metrics.snapshot()
    for raw_name, value in sorted(snap.items()):
        metric = f"{_METRIC_PREFIX}_{_sanitize_metric_name(raw_name)}_total"
        lines.append(f"# TYPE {metric} counter")
        lines.append(f"{metric} {value:g}")

    if llm is not None:
        s = llm.summary()
        gauges = {
            "llm_calls": s.get("llm_calls", 0),
            "llm_errors": s.get("llm_errors", 0),
            "llm_total_tokens": s.get("total_tokens", 0),
            "llm_total_cost_usd": s.get("total_cost_usd", 0.0),
            "llm_total_latency_ms": s.get("total_latency_ms", 0.0),
        }
        for name, value in gauges.items():
            metric = f"{_METRIC_PREFIX}_{name}"
            lines.append(f"# TYPE {metric} gauge")
            lines.append(f"{metric} {value:g}")

    if not lines:
        lines.append(f"# {_METRIC_PREFIX}: no metrics recorded yet")
    return "\n".join(lines) + "\n"
