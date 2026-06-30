#!/usr/bin/env python3
"""离线单元测试：可观测性（src/observability.py）+ LLM 客户端埋点。

覆盖：
- run_context / get_run_id 嵌套与还原
- JsonFormatter：单行 JSON、含 run_id、透传 extra、脱敏由调用方负责（这里验证结构）
- estimate_cost（已知/未知模型）、approx_tokens、MetricsCollector 汇总
- log_llm_call 写出带 event=llm_call 的结构化日志
- OpenAICompatibleLLMClient._emit_metrics：用 API usage 优先、缺失回退粗估，写入 collector
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import observability as obs  # noqa: E402
from prompt_optimizer import OpenAICompatibleLLMClient  # noqa: E402


# --------------------------- run_id ---------------------------
def test_run_context_sets_and_restores():
    assert obs.get_run_id() is None
    with obs.run_context("run-abc") as rid:
        assert rid == "run-abc"
        assert obs.get_run_id() == "run-abc"
        with obs.run_context() as inner:
            assert inner.startswith("run-")
            assert obs.get_run_id() == inner
        assert obs.get_run_id() == "run-abc"  # 内层退出后还原
    assert obs.get_run_id() is None  # 外层退出后清空


def test_new_run_id_unique():
    assert obs.new_run_id() != obs.new_run_id()


# --------------------------- JsonFormatter ---------------------------
def _capture_logs(name, level=logging.INFO):
    import io
    stream = io.StringIO()
    logger = logging.getLogger(name)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(obs.JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger, stream, handler


def test_json_formatter_emits_single_line_json_with_run_id_and_extra():
    logger, stream, handler = _capture_logs("berkshire.test.fmt")
    try:
        with obs.run_context("run-xyz"):
            logger.info("hello", extra={"event": "unit", "n": 3})
    finally:
        logger.removeHandler(handler)
    line = stream.getvalue().strip()
    assert "\n" not in line  # 单行
    obj = json.loads(line)
    assert obj["msg"] == "hello"
    assert obj["level"] == "INFO"
    assert obj["run_id"] == "run-xyz"
    assert obj["event"] == "unit"
    assert obj["n"] == 3


# --------------------------- cost / tokens / collector ---------------------------
def test_estimate_cost_known_and_unknown():
    # gpt-4o-mini: (0.15, 0.60) / 1M
    c = obs.estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
    assert abs(c - (0.15 + 0.60)) < 1e-9
    # 未知模型走默认价 (0.50, 1.50)
    c2 = obs.estimate_cost("totally-unknown", 1_000_000, 0)
    assert abs(c2 - 0.50) < 1e-9


def test_approx_tokens():
    assert obs.approx_tokens("") == 0
    assert obs.approx_tokens("abcd") >= 1


def test_metrics_collector_summary():
    col = obs.MetricsCollector()
    col.record(obs.LLMCallMetrics(model="m", prompt_tokens=10, completion_tokens=5,
                                  total_tokens=15, latency_ms=100.0, cost_usd=0.001, ok=True))
    col.record(obs.LLMCallMetrics(model="m", prompt_tokens=20, completion_tokens=0,
                                  total_tokens=20, latency_ms=50.0, cost_usd=0.002, ok=False))
    s = col.summary()
    assert s["llm_calls"] == 2
    assert s["llm_errors"] == 1
    assert s["total_tokens"] == 35
    assert abs(s["total_cost_usd"] - 0.003) < 1e-9
    assert s["total_latency_ms"] == 150.0


def test_log_llm_call_writes_event(monkeypatch):
    logger, stream, handler = _capture_logs("berkshire.llm")
    m = obs.LLMCallMetrics(model="gpt-4o-mini", prompt_tokens=3, completion_tokens=2,
                           total_tokens=5, latency_ms=12.3, cost_usd=0.0001, ok=True)
    obs.log_llm_call(m, logger=logger)
    logger.removeHandler(handler)
    obj = json.loads(stream.getvalue().strip())
    assert obj["event"] == "llm_call"
    assert obj["model"] == "gpt-4o-mini"
    assert obj["total_tokens"] == 5


# --------------------------- 客户端埋点 ---------------------------
def test_client_emit_metrics_prefers_api_usage():
    col = obs.MetricsCollector()
    client = OpenAICompatibleLLMClient(api_key="dummy", model="gpt-4o-mini", collector=col)
    data = {"usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140}}
    client._emit_metrics(data, "some content", "sys", "user", started=0.0, ok=True)
    assert col.count == 1
    m = col.calls[0]
    assert m.prompt_tokens == 100 and m.completion_tokens == 40 and m.total_tokens == 140
    assert m.cost_usd > 0
    assert m.ok is True


def test_client_emit_metrics_fallback_estimates_tokens():
    col = obs.MetricsCollector()
    client = OpenAICompatibleLLMClient(api_key="dummy", model="x", collector=col)
    client._emit_metrics(None, "content text here", "system prompt", "user prompt",
                         started=0.0, ok=False, error="boom")
    m = col.calls[0]
    assert m.prompt_tokens >= 1  # 无 usage → 粗估
    assert m.ok is False and m.error == "boom"
