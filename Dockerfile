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
# 阶段 2：Python 运行时（uv 官方镜像：内置 uv + CPython 3.12 on bookworm-slim）
#
# 使用 uv 官方提供的 python 运行时镜像（ghcr.io/astral-sh/uv），
# 该镜像已内置 uv 与 CPython 3.12，等价于 python:3.12-slim + uv，
# 但少了一整层 uv COPY，构建更快、镜像更小。
# 镜像 tag 中 uv 版本固定到 0.4.x，保证可复现。
# ============================================================
FROM ghcr.io/astral-sh/uv:0.4.4-python3.12-bookworm-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1 \
    PORTVIEW_PORT=8081 \
    PATH="/app/.venv/bin:$PATH"

# 系统依赖（gnupg：gpg --dearmor 需要，--no-install-recommends 不会自动带上）
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg lsb-release net-tools procps \
    && rm -rf /var/lib/apt/lists/*

# 安装 Docker CLI（用于读取容器端口）
RUN set -eux; \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends docker-ce-cli; \
    rm -rf /var/lib/apt/lists/*

# 非 root 运行用户（安全加固：降低容器被攻破后的权限）
# 固定 UID/GID 1000，便于宿主机 bind 挂载目录对齐属主。
RUN groupadd -g 1000 portview && useradd -u 1000 -g portview -m portview

# Python 运行时依赖（uv 从锁文件安装，跳过项目本体与 dev 依赖 → 可复现且更快）
COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project --no-dev --python 3.12

# 应用代码 + 前端产物 + 示例配置
COPY app/ ./app/
COPY config/config.json.example ./config/config.json.example
COPY --from=frontend /build/dist ./frontend/dist

# 属主对齐：应用代码、venv 与运行时数据目录全部归 portview，
# 保证非 root 用户可读写。/app/.data 是命名卷挂载点，Docker 首次挂载时
# 会把镜像内该目录的属主复制进卷；/app/config 为 bind 挂载点，宿主机
# 目录需自行保证属主为 UID 1000（或 world-writable），否则写配置会失败。
RUN chown -R portview:portview /app \
    && mkdir -p /app/.data /app/config \
    && chown portview:portview /app/.data /app/config

USER portview

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f "http://localhost:${PORTVIEW_PORT}/api/health" || exit 1

ENTRYPOINT ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORTVIEW_PORT:-8081}"]
