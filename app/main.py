"""PortView - FastAPI 主入口。

启动方式（开发）::

    uv run uvicorn app.main:app --host 0.0.0.0 --port 7577 --reload

启动时：
1. 初始化配置目录与文件
2. 注册 API 路由
3. 挂载前端构建产物（``frontend/dist``），SPA 兜底回退到 ``index.html``
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import init_config
from app.routers.auth import get_current_user, init_db
from app.routers import auth as auth_router
from app.routers import config as config_router
from app.routers import notifications as notifications_router
from app.routers import ports as ports_router
from app.routers import ranges as ranges_router
from app.utils.errors import PortViewError

logger = logging.getLogger(__name__)

# 前端构建产物目录（Vite build 输出）
_FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend",
    "dist",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时初始化配置。"""
    init_config()
    yield


def create_app() -> FastAPI:
    """应用工厂。"""
    app = FastAPI(
        title="PortView",
        version=__version__,
        description="Docker 容器与主机端口监控与可视化工具",
        lifespan=lifespan,
    )

    # CORS（开发时 Vite dev server 跨域；生产同源不触发）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API 路由
    app.include_router(auth_router.router)
    # 受保护的路由需要认证
    app.include_router(ports_router.router, dependencies=[Depends(get_current_user)])
    app.include_router(config_router.router, dependencies=[Depends(get_current_user)])
    app.include_router(ranges_router.router, dependencies=[Depends(get_current_user)])
    app.include_router(notifications_router.router, dependencies=[Depends(get_current_user)])

    # 初始化 SQLite 用户数据库
    init_db()

    # 统一错误处理
    @app.exception_handler(PortViewError)
    async def handle_portview_error(request, exc: PortViewError):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    # 前端静态资源（若已构建）
    if os.path.isdir(_FRONTEND_DIST):
        assets_dir = os.path.join(_FRONTEND_DIST, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        index_path = os.path.join(_FRONTEND_DIST, "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            """SPA 兜底：非 API、非静态资源的路径都回退到 index.html。"""
            candidate = os.path.join(_FRONTEND_DIST, full_path)
            if full_path and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(index_path)

    else:
        # 未构建前端时的提示页
        @app.get("/", include_in_schema=False)
        def root() -> dict:
            return {
                "name": "PortView",
                "version": __version__,
                "hint": "前端尚未构建。运行 `cd frontend && npm install && npm run build` 后刷新。",
                "docs": "/docs",
            }

    return app


app = create_app()
