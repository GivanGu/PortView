"""P1-1 端口备注路由（/api/notes）。

后端：SQLite ``port_notes`` 表（0.7 阶段已建，P1 阶段补 ``remark`` 列）。

端点：
- GET    ``/api/notes?search=``    列表（可选按 service / remark / 端口号模糊过滤）
- POST   ``/api/notes``            新建或更新（``port`` 为唯一键，upsert）
- DELETE ``/api/notes/{port}``     删除单条

设计原则：
- 无鉴权（内网工具）
- 端口范围 0~65535
- ``remark`` 长度 ≤ 1024
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.models import APIResponse, NoteCreateRequest, NoteRead
from app.services import db as db_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=APIResponse)
async def api_list_notes(search: str = "") -> APIResponse:
    """列表。``search`` 模糊匹配端口号 / service_name / remark。"""
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")

    conn = db_service._db
    if search:
        # 端口号精确或前缀、service/remark LIKE —— 用 OR 合并
        port_like = f"%{search.strip()}%"
        cur = await conn.execute(
            "SELECT port, service_name, protocol, remark, created_at, updated_at "
            "FROM port_notes "
            "WHERE CAST(port AS TEXT) LIKE ? "
            "   OR service_name LIKE ? "
            "   OR remark LIKE ? "
            "ORDER BY port ASC",
            (port_like, port_like, port_like),
        )
    else:
        cur = await conn.execute(
            "SELECT port, service_name, protocol, remark, created_at, updated_at "
            "FROM port_notes ORDER BY port ASC"
        )
    rows = await cur.fetchall()
    data = [
        NoteRead(
            port=r["port"],
            service_name=r["service_name"] or "",
            protocol=(r["protocol"] or ""),
            remark=r["remark"] or "",
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
    return APIResponse(success=True, data=data)


@router.post("", response_model=APIResponse)
async def api_upsert_note(req: NoteCreateRequest) -> APIResponse:
    """新建或更新。``port`` 存在则覆盖。"""
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    if not (0 <= req.port <= 65535):
        return APIResponse(success=False, error="port out of range 0-65535")
    if req.protocol not in ("", "tcp", "udp", "both"):
        return APIResponse(success=False, error="protocol must be '', tcp, udp or both")

    import time

    now = int(time.time())
    conn = db_service._db
    await conn.execute(
        "INSERT INTO port_notes (port, service_name, protocol, remark, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(port) DO UPDATE SET "
        "  service_name = excluded.service_name, "
        "  protocol     = excluded.protocol, "
        "  remark       = excluded.remark, "
        "  updated_at   = excluded.updated_at",
        (req.port, req.service_name, req.protocol, req.remark, now, now),
    )
    await conn.commit()

    # 说明：service_name 单独存于 SQLite，不反向写回 config.json ——
    # PortsView 的"编辑"是**只用于展示覆盖**，与 port_notes 的语义不同，
    # 避免两套 source of truth。前端在拉取端口列表后可按需合并展示（P2 增强）。
    return APIResponse(success=True, message="saved")


@router.delete("/{port}", response_model=APIResponse)
async def api_delete_note(port: int) -> APIResponse:
    """删除指定端口的备注。"""
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    if not (0 <= port <= 65535):
        return APIResponse(success=False, error="port out of range 0-65535")

    conn = db_service._db
    cur = await conn.execute("DELETE FROM port_notes WHERE port = ?", (port,))
    await conn.commit()
    n = cur.rowcount if hasattr(cur, "rowcount") else 0
    if not n:
        return APIResponse(success=True, message="not-found")
    return APIResponse(success=True, message="deleted")
