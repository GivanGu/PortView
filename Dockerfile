# ── Stage 1: Frontend build ──
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Backend runtime ──
FROM python:3.12-slim AS backend

# 安装 docker 扫描依赖 (psutil)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY app/ ./app/
COPY --from=frontend /app/frontend/dist/ ./frontend/dist/

# 安装 Python 依赖 (生产模式)
RUN pip install --no-cache-dir -e .

# 环境
ENV PYTHONUNBUFFERED=1
ENV PORTVIEW_CONFIG_DIR=/app/config
ENV PORTVIEW_HOST=0.0.0.0
ENV PORTVIEW_PORT=7577

EXPOSE 7577

# 创建 config 目录
RUN mkdir -p /app/config

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7577/api/health', timeout=3).read()" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7577"]
