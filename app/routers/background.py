"""自定义背景图路由（/api/background，v1.6.6）。

后端：SQLite ``backgrounds`` 表（单行 ``id=1``，BLOB 存图片字节）。
图片不进 ``user_prefs``——prefs 每次全量读取，4MiB 图片会拖垮 GET /api/prefs。

端点：
- GET    ``/api/background``  图片字节（正确 Content-Type）/ 404 未设置
- PUT    ``/api/background``  上传 ``{mime, data(base64)}`` → upsert（≤4MiB）
- DELETE ``/api/background``  幂等删除 → 未设置

设计原则：
- 鉴权由 ``main.py`` 中间件统一拦截，本路由无需额外配置。
- 大小上限 4MiB；魔数白名单 PNG/JPEG/WebP/GIF（背景图用不到 SVG/ICO）。
"""

from __future__ import annotations

import base64
import binascii
import logging
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.models import APIResponse, LogoUploadRequest
from app.services import db as db_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/background", tags=["background"])

# mime 白名单（背景图用不到 SVG/ICO，故比 logos 少两项）
_MIME_WHITELIST = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}
_MAX_SIZE = 4 * 1024 * 1024  # 4 MiB


@router.api_route("", methods=["GET", "HEAD"])
async def api_get_background() -> Response:
    """返回图片字节 + 正确 Content-Type；未设置 → 404。

    同时支持 HEAD（前端探测是否已设置，不下载图片体）。
    """
    if db_service._db is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "db not ready"})
    cur = await db_service._db.execute("SELECT mime, data FROM backgrounds WHERE id = 1")
    row = await cur.fetchone()
    if row is None or not row["data"]:
        return JSONResponse(status_code=404, content={"success": False, "error": "not set"})
    mime = row["mime"] or "application/octet-stream"
    return Response(content=row["data"], media_type=mime)


@router.put("", response_model=APIResponse)
async def api_set_background(req: LogoUploadRequest) -> APIResponse:
    """上传 / 替换背景图（upsert）。校验链任一不过则不落库。"""
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    if req.mime not in _MIME_WHITELIST:
        return APIResponse(success=False, error="unsupported mime type")

    try:
        data = base64.b64decode(req.data, validate=False)
    except (binascii.Error, ValueError) as e:
        return APIResponse(success=False, error=f"invalid base64: {e}")
    if not (1 <= len(data) <= _MAX_SIZE):
        return APIResponse(success=False, error="size must be 1B..4MiB")

    now = int(time.time())
    conn = db_service._db
    await conn.execute(
        "INSERT INTO backgrounds (id, mime, data, updated_at) VALUES (1, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET mime = excluded.mime, data = excluded.data, "
        "updated_at = excluded.updated_at",
        (req.mime, data, now),
    )
    await conn.commit()
    return APIResponse(success=True, message="saved")


@router.delete("", response_model=APIResponse)
async def api_delete_background() -> APIResponse:
    """幂等删除：未设置也返回 success。"""
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    conn = db_service._db
    cur = await conn.execute("DELETE FROM backgrounds WHERE id = 1")
    await conn.commit()
    n = cur.rowcount if hasattr(cur, "rowcount") else 0
    return APIResponse(success=True, message="deleted" if n else "not-set")
