#!/usr/bin/env python3
"""离线单元测试：服务边界纯处理函数（src/service.py）。

只测纯函数（不依赖 FastAPI）；若装了 fastapi 则附加一个 TestClient 冒烟测试。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import service  # noqa: E402


# --------------------------- health / doctor ---------------------------
def test_health():
    h = service.health()
    assert h["status"] == "ok"
    assert h["service"] == "berkshire-ai"
    assert h["version"] == service.APP_VERSION


def test_doctor_structure(monkeypatch):
    for v in ["TAVILY_API_KEYS", "TAVILY_API_KEY", "BERKSHIRE_LLM_API_KEY", "OPENAI_API_KEY"]:
        monkeypatch.delenv(v, raising=False)
    rep = service.doctor()["report"]
    assert "engine" in rep and rep["engine"]["status"] == "ready"


# --------------------------- score ---------------------------
def test_score_with_benchmark():
    payload = {
        "ticker": "AAPL", "date": "2024-01-01",
        "scores": {"buffett": 0.8},
        "price_anchor": 100.0,
        "benchmark": "SPY", "benchmark_anchor": 100.0,
        "realized_price": 110.0, "benchmark_realized_price": 101.0,
    }
    out = service.score(payload)
    assert out["stats"]["raw_return"] == pytest.approx(0.10, abs=1e-9)
    assert out["stats"]["alpha"] == pytest.approx(0.09, abs=1e-9)
    assert out["stats"]["has_benchmark"] is True
    assert "buffett" in out["scores"]


def test_score_missing_field_raises():
    with pytest.raises(ValueError):
        service.score({"ticker": "X"})  # 缺 scores/price_anchor/realized_price


def test_score_bad_payload_type():
    with pytest.raises(ValueError):
        service.score([1, 2, 3])  # type: ignore[arg-type]


# --------------------------- debate ---------------------------
def test_debate_bullish():
    out = service.debate({"scores": {"duan": 0.9, "buffett": 0.85, "munger": 0.8, "lilu": 0.8}})
    assert out["net_stance"] in {"bullish", "neutral", "bearish"}
    assert "net_score" in out and "rationale" in out


def test_debate_empty_scores_raises():
    with pytest.raises(ValueError):
        service.debate({"scores": {}})


# --------------------------- FastAPI 传输层（装了才测）---------------------------
def test_fastapi_app_smoke():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    app = service.create_app()
    client = TestClient(app)

    assert client.get("/health").json()["status"] == "ok"

    r = client.post("/debate", json={"scores": {"duan": 0.9, "buffett": 0.9, "munger": 0.85, "lilu": 0.85}})
    assert r.status_code == 200
    assert "net_stance" in r.json()

    # 缺字段 → 400
    bad = client.post("/score", json={"ticker": "X"})
    assert bad.status_code == 400
