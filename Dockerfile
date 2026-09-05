# syntax=docker/dockerfile:1

# ============================================================
# Stage 1: Build frontend (Vue 3 + Vite)
# ============================================================
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
# Use vite build directly in Docker (skip vue-tsc type-check for speed)
RUN npx vite build

# ============================================================
# Stage 2: Python runtime (3.12 + uv + FastAPI)
# ============================================================
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORTVIEW_PORT=7577 \
    PATH="/app/.venv/bin:$PATH"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Docker CLI (for reading container ports)
RUN set -eux; \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends docker-ce-cli; \
    rm -rf /var/lib/apt/lists/*

# Python dependencies (uv installs pre-built wheels, no compilation needed)
COPY pyproject.toml ./
RUN uv venv /app/.venv --python 3.12 \
    && uv pip install --python /app/.venv/bin/python \
        fastapi "uvicorn[standard]" docker psutil pydantic bcrypt "python-jose[cryptography]"

# App code + frontend build artifact
COPY app/ ./app/
COPY --from=frontend /build/dist ./frontend/dist

EXPOSE 7577

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f "http://localhost:${PORTVIEW_PORT}/api/health" || exit 1

ENTRYPOINT ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORTVIEW_PORT:-7577}"]
