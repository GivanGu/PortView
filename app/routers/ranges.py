"""自定义监控区间 CRUD 路由。

管理用户自定义的端口监控区间，如「22500-22600」这样的固定端口段，
在菜单栏点击后快速切换到该区间视图。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.config import (
    add_custom_range,
    load_custom_ranges,
    remove_custom_range,
    save_custom_ranges,
)
from app.models import PortRange, PortRangeCreate, PortRangeUpdate
from app.utils.errors import ErrorCodes, make_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config/ranges", tags=["ranges"])


@router.get("", response_model=list[PortRange])
def get_ranges():
    """获取所有自定义监控区间。"""
    return load_custom_ranges()


@router.post("", response_model=list[PortRange], status_code=201)
def create_range(req: PortRangeCreate):
    """添加自定义监控区间。"""
    ranges = load_custom_ranges()

    # 校验 ID 不冲突 (实际 ID 是 uuid 生成，防御性检查)
    import uuid

    range_data = {
        **req.model_dump(),
        "id": uuid.uuid4().hex[:8],
        "created_at": _utcnow_iso(),
    }
    ranges.append(range_data)
    save_custom_ranges(ranges)
    _log_change("添加", range_data)
    return ranges


@router.put("/{range_id}", response_model=list[PortRange])
def update_range(range_id: str, req: PortRangeUpdate):
    """修改自定义监控区间。"""
    ranges = load_custom_ranges()
    updated = False
    for r in ranges:
        if r.get("id") == range_id:
            r.update(req.model_dump(exclude_unset=True))
            updated = True
            break

    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"区间 ID {range_id} 不存在",
        )
    save_custom_ranges(ranges)
    _log_change("修改", next(r for r in ranges if r.get("id") == range_id))
    return ranges


@router.delete("/{range_id}", response_model=list[PortRange])
def delete_range(range_id: str):
    """删除自定义监控区间。"""
    ranges = load_custom_ranges()
    before = len(ranges)
    ranges = [r for r in ranges if r.get("id") != range_id]
    if len(ranges) == before:
        raise HTTPException(
            status_code=404,
            detail=f"区间 ID {range_id} 不存在",
        )
    save_custom_ranges(ranges)
    _log_change("删除", {"id": range_id})
    return ranges


def _utcnow_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


def _log_change(action: str, data: dict):
    logger.info("自定义区间 %s: %s", action, data)
