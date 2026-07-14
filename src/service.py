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

import os
from typing import Any, Dict

try:
    from .access_control import RateLimiter, check_api_key
    from .config import doctor as config_doctor
    from .debate import run_debate
    from .decision_log import DecisionRecord
    from .metrics_export import ServiceMetrics, render_prometheus
    from .observability import get_logger
    from .realized_feedback import realized_scores

except ImportError:  # pragma: no cover - 包内导入回退
    # 绝对导入解析到 src/config.py；与仓库根 config/ 目录同名，mypy 误判故忽略
    from access_control import RateLimiter, check_api_key  # type: ignore[attr-defined]
    from config import doctor as config_doctor  # type: ignore[attr-defined]
    from debate import run_debate
    from decision_log import DecisionRecord
    from metrics_export import ServiceMetrics, render_prometheus
    from observability import get_logger
    from realized_feedback import realized_scores

APP_VERSION = "10.29.2"
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
def create_app(
    *,
    api_keys: "list[str] | None" = None,
    rate_limit_per_min: "int | None" = None,
    metrics: "ServiceMetrics | None" = None,
):
    """构建 FastAPI 应用（把纯处理函数挂到路由）。未装 FastAPI 时抛清晰错误。

    生产防护（均可选，缺省回退到环境变量 / 关闭）：
      - api_keys：受保护端点（/score /debate）要求 `X-API-Key` 命中其一；
        缺省读 `BERKSHIRE_API_KEYS`（逗号分隔）；都没有则不鉴权（开发/内网）。
      - rate_limit_per_min：每个 API key（或匿名按客户端 IP）每分钟最大请求数；
        缺省读 `BERKSHIRE_RATE_LIMIT_PER_MIN`；0/None 关闭。
      - metrics：进程级请求/错误计数器；缺省自动新建并经 `/metrics` 暴露。
    """
    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import JSONResponse, PlainTextResponse
    except ImportError as e:  # pragma: no cover - 仅在未装 fastapi 时触发
        raise RuntimeError(
            "FastAPI 未安装。请 `pip install 'berkshire-ai[service]'`（fastapi + uvicorn）。"
        ) from e

    # `from __future__ import annotations` 把路由参数注解变成字符串，FastAPI 需从
    # 模块全局解析它们；Request 在本函数内才导入，注入模块全局以便注解解析，
    # 否则 `request: Request` 会被误判为查询参数（422）。
    globals()["Request"] = Request

    keys = api_keys if api_keys is not None else _keys_from_env()
    rpm = rate_limit_per_min if rate_limit_per_min is not None else _rpm_from_env()
    limiter = RateLimiter(max_per_min=rpm) if rpm else None
    svc_metrics = metrics or ServiceMetrics()
    logger = get_logger("service")

    app = FastAPI(title=SERVICE_NAME, version=APP_VERSION)
    app.state.metrics = svc_metrics

    def _auth(request: "Request") -> str:
        """鉴权 + 限流；返回限流配额键（key 指纹或 ip）。失败抛 HTTPException。

        从请求头读 X-API-Key、从连接读客户端 IP，避免把鉴权参数混入请求体 schema。
        """
        provided = request.headers.get("x-api-key")
        request_ip = request.client.host if request.client else "unknown"
        ok, ident = check_api_key(provided, keys)
        if not ok:
            svc_metrics.incr("auth_rejected")
            raise HTTPException(status_code=401, detail="无效或缺失 X-API-Key")
        bucket = ident or request_ip
        if limiter is not None and not limiter.allow(bucket):
            svc_metrics.incr("rate_limited")
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        return bucket

    def _guard(name: str, fn, body=None):
        svc_metrics.incr(f"{name}_requests")
        try:
            result = fn() if body is None else fn(body)
            svc_metrics.incr(f"{name}_ok")
            return result
        except ValueError as e:
            svc_metrics.incr(f"{name}_bad_request")
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:  # noqa: BLE001
            svc_metrics.incr(f"{name}_error")
            logger.warning("handler_error", extra={"endpoint": name, "error": str(e)})
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.get("/health")
    def _health():
        return health()

    @app.get("/config/doctor")
    def _doctor():
        return doctor()

    @app.get("/metrics")
    def _metrics():
        return PlainTextResponse(render_prometheus(svc_metrics))

    @app.post("/score")
    async def _score(payload: dict, request: Request):
        _auth(request)
        return _guard("score", score, payload)

    @app.post("/debate")
    async def _debate(payload: dict, request: Request):
        _auth(request)
        return _guard("debate", debate, payload)

    return app


def _keys_from_env() -> "list[str]":
    raw = os.getenv("BERKSHIRE_API_KEYS", "").strip()
    return [k.strip() for k in raw.split(",") if k.strip()]


def _rpm_from_env() -> int:
    raw = os.getenv("BERKSHIRE_RATE_LIMIT_PER_MIN", "").strip()
    try:
        return max(0, int(raw)) if raw else 0
    except ValueError:
        return 0


def run() -> None:  # pragma: no cover - 进程入口，由容器/CLI 调用
    """uvicorn 进程入口：`python -m src.service` 或 console_script `berkshire-serve`。

    监听地址/端口走环境变量：BERKSHIRE_HOST(默认 0.0.0.0) / BERKSHIRE_PORT(默认 8000)。
    """
    try:
        import uvicorn
    except ImportError as e:
        raise RuntimeError(
            "uvicorn 未安装。请 `pip install 'berkshire-ai[service]'`。"
        ) from e

    try:
        from .config import load_dotenv
    except ImportError:  # pragma: no cover
        from config import load_dotenv  # type: ignore[attr-defined]
    load_dotenv()

    host = os.getenv("BERKSHIRE_HOST", "0.0.0.0")  # noqa: S104 - 容器内监听
    port = int(os.getenv("BERKSHIRE_PORT", "8000"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    run()
