#!/usr/bin/env python3
"""离线单元测试：指标导出（src/metrics_export.py）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from metrics_export import ServiceMetrics, render_prometheus  # noqa: E402
from observability import LLMCallMetrics, MetricsCollector  # noqa: E402


def test_service_metrics_incr_and_get():
    m = ServiceMetrics()
    m.incr("score_requests")
    m.incr("score_requests")
    m.incr("score_ok", 1)
    assert m.get("score_requests") == 2
    assert m.get("score_ok") == 1
    assert m.get("missing") == 0


def test_snapshot_is_copy():
    m = ServiceMetrics()
    m.incr("x")
    snap = m.snapshot()
    snap["x"] = 999
    assert m.get("x") == 1  # 快照是拷贝，不影响内部


def test_render_prometheus_counters():
    m = ServiceMetrics()
    m.incr("score_requests", 3)
    out = render_prometheus(m)
    assert "berkshire_score_requests_total 3" in out
    assert "# TYPE berkshire_score_requests_total counter" in out
    assert out.endswith("\n")


def test_render_prometheus_sanitizes_names():
    m = ServiceMetrics()
    m.incr("weird-name/here")
    out = render_prometheus(m)
    assert "berkshire_weird_name_here_total" in out


def test_render_prometheus_empty():
    out = render_prometheus(ServiceMetrics())
    assert "no metrics recorded yet" in out


def test_render_prometheus_with_llm_collector():
    m = ServiceMetrics()
    coll = MetricsCollector()
    coll.record(LLMCallMetrics(model="gpt-4o-mini", total_tokens=100, cost_usd=0.001, latency_ms=42))
    out = render_prometheus(m, llm=coll)
    assert "berkshire_llm_calls 1" in out
    assert "berkshire_llm_total_tokens 100" in out
    assert "# TYPE berkshire_llm_total_tokens gauge" in out
