"""应用 Logo 路由（/api/logos，v1.5.0）。

后端：SQLite ``service_logos`` 表（三态：无记录 / found / not_found）。

端点：
- GET    ``/api/logos``            元数据列表 ``[{app_key, status, mime}]``
- GET    ``/api/logos/{app_key}``  图片字节（正确 Content-Type）/ 404
- PUT    ``/api/logos/{app_key}``  手动上传 ``{mime, data(base64)}`` → found（upsert）
- DELETE ``/api/logos/{app_key}``  幂等删除 → 无记录
- POST   ``/api/logos/discover``   服务端抓取 + 持久化 ``{app_key, port, path?}``（幂等）

设计原则：
- 鉴权由 ``main.py`` 中间件统一拦截，本路由无需额外配置。
- 统一 ``APIResponse`` 包裹；``GET /{app_key}`` 例外，直接返回图片字节。
- 大小上限 1MiB；魔数校验 PNG/JPEG/ICO/SVG/GIF/WebP（不引 Pillow）。
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.models import (
    APIResponse,
    DiscoverRequest,
    LogoMeta,
    LogoUploadRequest,
)
from app.services import db as db_service
from app.services import default_logos, icon_discovery

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logos", tags=["logos"])

# app_key 字符集：小写字母 / 数字 / . _ : / -（前端派生，后端仅校验）
_APP_KEY_RE = re.compile(r"[a-z0-9._:/-]{1,128}")
# mime 白名单
_MIME_WHITELIST = {
    "image/png",
    "image/jpeg",
    "image/svg+xml",
    "image/gif",
    "image/webp",
    "image/x-icon",
    "image/vnd.microsoft.icon",
}
_MAX_SIZE = 1024 * 1024  # 1 MiB


def _valid_app_key(app_key: str) -> bool:
    return bool(app_key) and _APP_KEY_RE.fullmatch(app_key) is not None


async def _get_logo_row(app_key: str) -> dict | None:
    """读取单条 logo 行（dict），不存在返回 None。"""
    conn = db_service._db
    cur = await conn.execute(
        "SELECT app_key, status, mime, data, created_at, updated_at "
        "FROM service_logos WHERE app_key = ?",
        (app_key,),
    )
    row = await cur.fetchone()
    return dict(row) if row is not None else None


@router.get("", response_model=APIResponse)
async def api_list_logos() -> APIResponse:
    """元数据列表（不含图片字节），供前端判断哪些卡片有 logo。"""
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    cur = await db_service._db.execute(
        "SELECT app_key, status, mime FROM service_logos ORDER BY app_key ASC"
    )
    rows = await cur.fetchall()
    data = [LogoMeta(app_key=r["app_key"], status=r["status"], mime=r["mime"]) for r in rows]
    return APIResponse(success=True, data=data)


@router.get("/defaults", response_model=APIResponse)
async def api_list_default_logos() -> APIResponse:
    """内置默认 Logo 的归一化 key 列表（供前端判断某 service_name 是否有默认图标）。"""
    return APIResponse(success=True, data=default_logos.available_keys())


@router.get("/default/{key}")
async def api_get_default_logo(key: str) -> Response:
    """返回内置默认 Logo 的 SVG 字节；未知 key → 404。

    纯只读静态资源，不查库、不写库；用户上传 Logo 始终优先于本回退。
    """
    path = default_logos.resolve(key)
    if path is None:
        return JSONResponse(status_code=404, content={"success": False, "error": "not found"})
    return Response(content=path.read_bytes(), media_type="image/svg+xml")


@router.get("/{app_key}")
async def api_get_logo(app_key: str) -> Response:
    """返回图片字节 + 正确 Content-Type；缺失（无记录 / not_found）→ 404。"""
    if db_service._db is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "db not ready"})
    if not _valid_app_key(app_key):
        return JSONResponse(status_code=400, content={"success": False, "error": "invalid app_key"})

    row = await _get_logo_row(app_key)
    if row is None or row["status"] != "found" or not row["data"]:
        return JSONResponse(status_code=404, content={"success": False, "error": "not found"})

    mime = row["mime"] or "application/octet-stream"
    return Response(content=row["data"], media_type=mime)


@router.put("/{app_key}", response_model=APIResponse)
async def api_upload_logo(app_key: str, req: LogoUploadRequest) -> APIResponse:
    """手动上传 / 替换 Logo（upsert → found）。校验链任一不过则不落库。"""
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    if not _valid_app_key(app_key):
        return APIResponse(success=False, error="invalid app_key")
    if req.mime not in _MIME_WHITELIST:
        return APIResponse(success=False, error="unsupported mime type")

    try:
        data = base64.b64decode(req.data, validate=False)
    except (binascii.Error, ValueError) as e:
        return APIResponse(success=False, error=f"invalid base64: {e}")
    if not (1 <= len(data) <= _MAX_SIZE):
        return APIResponse(success=False, error="size must be 1B..1MiB")

    now = int(time.time())
    conn = db_service._db
    await conn.execute(
        "INSERT INTO service_logos (app_key, status, mime, data, created_at, updated_at) "
        "VALUES (?, 'found', ?, ?, ?, ?) "
        "ON CONFLICT(app_key) DO UPDATE SET "
        "  status = 'found', mime = excluded.mime, data = excluded.data, "
        "  updated_at = excluded.updated_at",
        (app_key, req.mime, data, now, now),
    )
    await conn.commit()
    return APIResponse(success=True, message="saved")


@router.delete("/{app_key}", response_model=APIResponse)
async def api_delete_logo(app_key: str) -> APIResponse:
    """幂等删除：不存在也返回 success。删除后回到「无记录」，可重新 discover。"""
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    if not _valid_app_key(app_key):
        return APIResponse(success=False, error="invalid app_key")

    conn = db_service._db
    cur = await conn.execute("DELETE FROM service_logos WHERE app_key = ?", (app_key,))
    await conn.commit()
    n = cur.rowcount if hasattr(cur, "rowcount") else 0
    return APIResponse(success=True, message="deleted" if n else "not-found")


@router.post("/discover", response_model=APIResponse)
async def api_discover_logo(req: DiscoverRequest) -> APIResponse:
    """服务端抓取 favicon 并持久化（幂等）。

    - 已有记录（found / not_found）→ 直接返回当前状态，不重复抓取。
    - 无记录 → 执行抓取：成功落 found，失败落 not_found。
    """
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    if not _valid_app_key(req.app_key):
        return APIResponse(success=False, error="invalid app_key")

    # 幂等：已有终态记录则直接返回
    existing = await _get_logo_row(req.app_key)
    if existing is not None:
        return APIResponse(
            success=True,
            data={"status": existing["status"], "mime": existing["mime"]},
            message="cached",
        )

    # 仅 HTTP 端口可抓取；port 非法直接落 not_found
    result = None
    if 1 <= req.port <= 65535:
        result = await icon_discovery.discover_icon(
            icon_discovery.DISCOVER_HOST, req.port, req.path
        )

    now = int(time.time())
    conn = db_service._db
    if result is not None:
        data, mime = result
        await conn.execute(
            "INSERT INTO service_logos (app_key, status, mime, data, created_at, updated_at) "
            "VALUES (?, 'found', ?, ?, ?, ?) "
            "ON CONFLICT(app_key) DO UPDATE SET "
            "  status = 'found', mime = excluded.mime, data = excluded.data, "
            "  updated_at = excluded.updated_at",
            (req.app_key, mime, data, now, now),
        )
        await conn.commit()
        return APIResponse(
            success=True, data={"status": "found", "mime": mime}, message="discovered"
        )

    await conn.execute(
        "INSERT INTO service_logos (app_key, status, mime, data, created_at, updated_at) "
        "VALUES (?, 'not_found', NULL, NULL, ?, ?) "
        "ON CONFLICT(app_key) DO UPDATE SET "
        "  status = 'not_found', mime = NULL, data = NULL, updated_at = excluded.updated_at",
        (req.app_key, now, now),
    )
    await conn.commit()
    return APIResponse(
        success=True, data={"status": "not_found", "mime": None}, message="not-found"
    )
