# syntax=docker/dockerfile:1
# Berkshire AI 服务镜像（生产化硬化 档D）
# 多阶段构建：builder 装依赖并生成 wheel，runtime 仅带运行所需，非 root 运行。

# ---------- builder ----------
FROM python:3.12-slim AS builder

WORKDIR /build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
COPY tools ./tools

# 安装含 service extra（fastapi + uvicorn）的依赖到一个独立前缀，便于拷贝
RUN python -m pip install --upgrade pip build \
    && python -m pip install --prefix=/install ".[service]"

# ---------- runtime ----------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="berkshire-ai" \
      org.opencontainers.image.source="https://github.com/mckayhou/berkshire-ai" \
      org.opencontainers.image.description="四大师并行投研系统 + V10 TextGrad 自进化引擎"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BERKSHIRE_HOST=0.0.0.0 \
    BERKSHIRE_PORT=8000 \
    PYTHONPATH=/app/src

WORKDIR /app

# 拷贝已装好的依赖与应用源码
COPY --from=builder /install /usr/local
COPY src ./src
COPY tools ./tools
COPY README.md pyproject.toml ./

# 非 root 运行
RUN useradd --create-home --uid 10001 berkshire \
    && chown -R berkshire:berkshire /app
USER berkshire

EXPOSE 8000

# 容器内健康检查（命中 /health）
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.getenv('BERKSHIRE_PORT','8000')+'/health',timeout=3).status==200 else 1)"

# 经 service.run() 起 uvicorn（读 BERKSHIRE_HOST/PORT/API_KEYS/RATE_LIMIT_PER_MIN）
CMD ["python", "-m", "service"]
