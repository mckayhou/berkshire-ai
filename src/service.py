#!/usr/bin/env python3
"""
服务边界：把引擎能力暴露为带版本契约的 HTTP 服务（供 OpenClaw / QwenPaw 等消费）。

设计取舍
--------------------------------------------------
- **核心逻辑做成纯处理函数**（health/doctor/score/debate），不依赖任何 Web 框架，
  因此可完全离线单测，CI 无需安装 FastAPI。
- **FastAPI 仅作传输层**（可选 extra `service`）：`create_app()` 把纯处理函数挂到
  路由上；未安装 FastAPI 时给出清晰报错，不影响其余模块导入。
- 入参校验失败抛 `ValueError`（HTTP 层映射为 400）；其余异常映射 500。

注意：当前 /score 用调用方显式提供的「已实现价格」做确定性计算，不在服务内发起
取数（避免把 SSRF / 配额风险带进同步请求路径）；如需真实取数，调用方先取再传入。
"""

from __future__ import annotations

from typing import Any, Dict

try:
    # 绝对导入解析到 src/config.py；与仓库根 config/ 目录同名，mypy 误判故忽略
    from config import doctor as config_doctor  # type: ignore[attr-defined]
    from debate import run_debate
    from decision_log import DecisionRecord
    from realized_feedback import realized_scores
except ImportError:  # pragma: no cover - 包内导入回退
    from .config import doctor as config_doctor
    from .debate import run_debate
    from .decision_log import DecisionRecord
    from .realized_feedback import realized_scores

APP_VERSION = "10.16"
SERVICE_NAME = "berkshire-ai"


# ---------------------------------------------------------------------------
# 纯处理函数（无框架依赖，可离线单测）
# ---------------------------------------------------------------------------
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": SERVICE_NAME, "version": APP_VERSION}


def doctor() -> Dict[str, Any]:
    """配置体检（不含任何密钥明文）。"""
    return {"report": config_doctor()}


def _require(payload: Dict[str, Any], key: str) -> Any:
    if key not in payload or payload[key] is None:
        raise ValueError(f"缺少必填字段: {key}")
    return payload[key]


def score(payload: Dict[str, Any]) -> Dict[str, Any]:
    """由「决策快照 + 已实现价格」计算收益→评分。

    payload: {
        ticker, date, scores:{prefix:0~1}, price_anchor,
        benchmark?, benchmark_anchor?,
        realized_price, benchmark_realized_price?, sensitivity?
    }
    """
    if not isinstance(payload, dict):
        raise ValueError("请求体必须为 JSON 对象")
    try:
        decision = DecisionRecord(
            ticker=str(_require(payload, "ticker")),
            date=str(_require(payload, "date")),
            scores=dict(_require(payload, "scores")),
            price_anchor=float(_require(payload, "price_anchor")),
            benchmark=payload.get("benchmark"),
            benchmark_anchor=(
                float(payload["benchmark_anchor"])
                if payload.get("benchmark_anchor") is not None else None
            ),
        )
    except (TypeError, ValueError) as e:
        raise ValueError(f"决策字段非法: {e}") from e

    realized_price = float(_require(payload, "realized_price"))
    bench_realized = payload.get("benchmark_realized_price")
    bench_realized = float(bench_realized) if bench_realized is not None else None

    kwargs: Dict[str, Any] = {}
    if payload.get("sensitivity") is not None:
        kwargs["sensitivity"] = float(payload["sensitivity"])

    scores, stats = realized_scores(decision, realized_price, bench_realized, **kwargs)
    return {
        "scores": scores,
        "stats": {
            "ticker": stats.ticker,
            "raw_return": stats.raw_return,
            "benchmark_return": stats.benchmark_return,
            "alpha": stats.alpha,
            "realized_base": stats.realized_base,
            "has_benchmark": stats.has_benchmark,
        },
    }


def debate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """由四大师信心分产出多空净判断。payload: {scores:{prefix:0~1}}。"""
    if not isinstance(payload, dict):
        raise ValueError("请求体必须为 JSON 对象")
    scores = _require(payload, "scores")
    if not isinstance(scores, dict) or not scores:
        raise ValueError("scores 必须为非空对象")
    try:
        result = run_debate({k: float(v) for k, v in scores.items()})
    except (TypeError, ValueError) as e:
        raise ValueError(f"scores 值非法: {e}") from e
    return {
        "net_stance": result.net_stance,
        "net_score": result.net_score,
        "ok": result.ok,
        "rationale": result.rationale,
    }


# ---------------------------------------------------------------------------
# FastAPI 传输层（可选；pip install 'berkshire-ai[service]'）
# ---------------------------------------------------------------------------
def create_app():
    """构建 FastAPI 应用（把纯处理函数挂到路由）。未装 FastAPI 时抛清晰错误。"""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
    except ImportError as e:  # pragma: no cover - 仅在未装 fastapi 时触发
        raise RuntimeError(
            "FastAPI 未安装。请 `pip install 'berkshire-ai[service]'`（fastapi + uvicorn）。"
        ) from e

    app = FastAPI(title=SERVICE_NAME, version=APP_VERSION)

    def _guard(fn, body=None):
        try:
            return fn() if body is None else fn(body)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:  # noqa: BLE001
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.get("/health")
    def _health():
        return health()

    @app.get("/config/doctor")
    def _doctor():
        return doctor()

    @app.post("/score")
    async def _score(payload: dict):
        return _guard(score, payload)

    @app.post("/debate")
    async def _debate(payload: dict):
        return _guard(debate, payload)

    return app
