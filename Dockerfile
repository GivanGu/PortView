# syntax=docker/dockerfile:1

# ============================================================
# 阶段 1：构建前端（Vue 3 + Vite）
# ============================================================
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ============================================================
# 阶段 2：Python 运行时（3.12 + uv + FastAPI）
# ============================================================
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORTVIEW_PORT=7577 \
    PATH="/app/.venv/bin:$PATH"

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg lsb-release net-tools procps \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 安装 Docker CLI（用于读取容器端口）
RUN set -eux; \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends docker-ce-cli; \
    rm -rf /var/lib/apt/lists/*

# Python 依赖（uv 安装到独立 venv）
COPY pyproject.toml ./
RUN uv venv /app/.venv --python 3.12 \
    && uv pip install --python /app/.venv/bin/python \
        fastapi "uvicorn[standard]" docker psutil pydantic

# 应用代码 + 前端产物 + 示例配置
COPY app/ ./app/
COPY config/config.json.example ./config/config.json.example
COPY --from=frontend /build/dist ./frontend/dist

EXPOSE 7577

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f "http://localhost:${PORTVIEW_PORT}/api/health" || exit 1

ENTRYPOINT ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORTVIEW_PORT:-7577}"]
