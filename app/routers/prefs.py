"""P1-2 用户偏好路由（/api/prefs）。

后端：SQLite ``user_prefs`` 表（0.7 阶段已建，单行 ``id=1``）。

端点：
- GET   ``/api/prefs``       读取当前用户（单行）
- PATCH ``/api/prefs``       局部更新（theme / accent / lang），未提供字段不修改
- POST  ``/api/prefs/reset`` 重置到默认（theme=dark, accent=indigo, lang=zh）

说明：
- 前端 App.vue 已经在 localStorage 中保留了偏好；这里的持久化是**服务端备份**，
  为将来多设备 / 无头部署 / 从浏览器无痕模式恢复偏好提供基础。
- 前端 SettingsView 每次切换都会同时写 localStorage 和 PUT/PATCH 到后端，
  二者同步即可。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.models import APIResponse, UserPrefsPatch, UserPrefsRead
from app.services import db as db_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/prefs", tags=["prefs"])

_ACCENTS = {"indigo", "blue", "teal", "rose", "amber", "violet"}


@router.get("", response_model=APIResponse)
async def api_get_prefs() -> APIResponse:
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    conn = db_service._db
    cur = await conn.execute(
        "SELECT theme, accent, lang FROM user_prefs WHERE id = 1"
    )
    row = await cur.fetchone()
    if row is None:
        return APIResponse(success=False, error="prefs not seeded")
    return APIResponse(
        success=True,
        data=UserPrefsRead(theme=row["theme"], accent=row["accent"], lang=row["lang"]),
    )


@router.patch("", response_model=APIResponse)
async def api_patch_prefs(patch: UserPrefsPatch) -> APIResponse:
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    if patch.accent is not None and patch.accent not in _ACCENTS:
        return APIResponse(success=False, error=f"accent must be one of {sorted(_ACCENTS)}")

    import time

    # 只更新显式提供的字段
    sets: list[str] = []
    params: list[object] = []
    if patch.theme is not None:
        sets.append("theme = ?")
        params.append(patch.theme)
    if patch.accent is not None:
        sets.append("accent = ?")
        params.append(patch.accent)
    if patch.lang is not None:
        sets.append("lang = ?")
        params.append(patch.lang)
    if not sets:
        return APIResponse(success=True, message="no-op")
    sets.append("updated_at = ?")
    params.append(int(time.time()))
    params.append(1)  # WHERE id = 1

    conn = db_service._db
    cur = await conn.execute(
        f"UPDATE user_prefs SET {', '.join(sets)} WHERE id = ?",
        tuple(params),
    )
    await conn.commit()
    return APIResponse(success=True, message="updated")


@router.post("/reset", response_model=APIResponse)
async def api_reset_prefs() -> APIResponse:
    if db_service._db is None:
        return APIResponse(success=False, error="db not ready")
    import time

    conn = db_service._db
    await conn.execute(
        "UPDATE user_prefs SET theme = 'dark', accent = 'indigo', lang = 'zh', updated_at = ? WHERE id = 1",
        (int(time.time()),),
    )
    await conn.commit()
    return APIResponse(success=True, message="reset")
