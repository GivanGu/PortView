"""/api/ranges —— 用户自定义监控区间。

表 ``range_rules`` 已存在（0.7 阶段建，P1.1 起真正使用）。
支持任意段数；驱动 ``/api/ports`` 的 ``start_port`` / ``end_port``。

端点：
- GET    /api/ranges
- POST   /api/ranges            {name, start_port, end_port}
- PUT    /api/ranges/{id}      {name?, start_port?, end_port?}
- DELETE /api/ranges/{id}
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.models import APIResponse
from app.services import db as db_service

router = APIRouter(prefix="/api/ranges", tags=["ranges"])


class RangePayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    start_port: int = Field(ge=0, le=65535)
    end_port: int = Field(ge=0, le=65535)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name required")
        return v

    def validate(self) -> None:
        if self.start_port > self.end_port:
            raise ValueError("start_port must be <= end_port")


class RangeUpdate(BaseModel):
    name: str | None = None
    start_port: int | None = Field(default=None, ge=0, le=65535)
    end_port: int | None = Field(default=None, ge=0, le=65535)


class RangeRead(BaseModel):
    id: int
    name: str
    start_port: int
    end_port: int
    created_at: int


async def _list() -> list[dict]:
    conn = db_service.get_db()
    if conn is None:
        return []
    cur = await conn.execute(
        "SELECT id, name, start_port, end_port, created_at"
        " FROM range_rules ORDER BY start_port, id"
    )
    rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "start_port": r["start_port"],
            "end_port": r["end_port"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.get("")
async def list_ranges() -> APIResponse:
    items = await _list()
    return APIResponse(success=True, data=items)


@router.post("")
async def create_range(body: RangePayload) -> APIResponse:
    try:
        body.validate()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    conn = db_service.get_db()
    if conn is None:
        raise HTTPException(status_code=500, detail="db not initialized")
    now = int(time.time())
    try:
        cur = await conn.execute(
            "INSERT INTO range_rules (name, start_port, end_port, created_at)"
            " VALUES (?, ?, ?, ?)",
            (body.name, body.start_port, body.end_port, now),
        )
        await conn.commit()
    except Exception as exc:  # UNIQUE(name) 冲突
        raise HTTPException(status_code=409, detail=f"name '{body.name}' already exists") from exc
    # 找刚插入的 id
    cur2 = await conn.execute(
        "SELECT id FROM range_rules WHERE name = ? ORDER BY id DESC LIMIT 1", (body.name,)
    )
    row = await cur2.fetchone()
    new_id = row["id"] if row else None
    item = await _list()
    created = next((x for x in item if x["id"] == new_id), item[-1] if item else None)
    return APIResponse(success=True, message="created", data=created)


@router.put("/{rid}")
async def update_range(rid: int, body: RangeUpdate) -> APIResponse:
    conn = db_service.get_db()
    if conn is None:
        raise HTTPException(status_code=500, detail="db not initialized")
    cur = await conn.execute("SELECT * FROM range_rules WHERE id = ?", (rid,))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="range not found")
    new_name = body.name if body.name is not None else row["name"]
    new_start = body.start_port if body.start_port is not None else row["start_port"]
    new_end = body.end_port if body.end_port is not None else row["end_port"]
    if new_start > new_end:
        raise HTTPException(status_code=422, detail="start_port > end_port")
    await conn.execute(
        "UPDATE range_rules SET name=?, start_port=?, end_port=? WHERE id=?",
        (new_name, new_start, new_end, rid),
    )
    await conn.commit()
    item = await _list()
    updated = next((x for x in item if x["id"] == rid), None)
    if updated is None:
        raise HTTPException(status_code=404, detail="range not found after update")
    return APIResponse(success=True, data=updated)


@router.delete("/{rid}")
async def delete_range(rid: int) -> APIResponse:
    conn = db_service.get_db()
    if conn is None:
        raise HTTPException(status_code=500, detail="db not initialized")
    cur = await conn.execute("DELETE FROM range_rules WHERE id = ?", (rid,))
    await conn.commit()
    n = cur.rowcount or 0
    return APIResponse(success=True, message=f"deleted {n} range")
