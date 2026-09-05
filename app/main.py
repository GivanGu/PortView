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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import init_config
from app.routers import auth as auth_router
from app.routers import config as config_router
from app.routers import notes as notes_router
from app.routers import ports as ports_router
from app.routers import prefs as prefs_router
from app.routers import ranges as ranges_router
from app.services import auth as auth_service
from app.services import db as _db_service

logger = logging.getLogger(__name__)

# 前端构建产物目录（Vite build 输出）
_FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend",
    "dist",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时初始化配置 + SQLite 数据库。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    init_config()
    async with _db_service.init_db():
        logger.info("PortView v%s 启动完成（SQLite ready）", __version__)
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

    # 登录守卫：开启 auth 时，除 /api/auth/* 与 /api/health 外的所有 /api/* 都需有效会话。
    # 中间件方式统一拦截，避免每个路由各自声明 Depends；关闭 auth 时全放行。
    _AUTH_WHITELIST = ("/api/health", "/api/auth/login", "/api/auth/set_password",
                       "/api/auth/me", "/api/auth/toggle")

    @app.middleware("http")
    async def _auth_guard(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        if path in _AUTH_WHITELIST or path.startswith("/api/auth/"):
            return await call_next(request)
        if not await auth_service.is_auth_required():
            return await call_next(request)
        token = request.cookies.get("portview_session") or ""
        if await auth_service.is_valid_session(token):
            return await call_next(request)
        return JSONResponse(status_code=401, content={"detail": "login required", "code": "login required"})

    # API 路由
    app.include_router(auth_router.router)       # P1.1 登录
    app.include_router(ports_router.router)
    app.include_router(config_router.router)
    app.include_router(notes_router.router)   # P1-1
    app.include_router(prefs_router.router)   # P1-2
    app.include_router(ranges_router.router)   # P1.1 监控区间

    # 健康检查
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
