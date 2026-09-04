"""通知面板路由。

提供获取最近通知、标记已读、清除已读接口。
用于前端右上角 Bell 图标下拉面板。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.models import APIResponse
from app.services.notification_bus import NotificationBus

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def get_bus() -> NotificationBus:
    return NotificationBus.get()


@router.get("", response_model=APIResponse)
def get_recent(
    bus: NotificationBus = Depends(get_bus),
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
):
    """获取最近 N 条通知。"""
    items = bus.get_recent(limit=limit, unread_only=unread_only)
    return APIResponse(
        success=True,
        data={
            "notifications": items,
            "unread_count": bus.unread_count(),
        },
    )


@router.post("/read-all", response_model=APIResponse)
def mark_all_read(bus: NotificationBus = Depends(get_bus)):
    """标记所有通知为已读。"""
    count = bus.mark_all_read()
    return APIResponse(success=True, data={"marked": count, "unread_count": 0})


@router.post("/read/{notification_id}", response_model=APIResponse)
def mark_read(notification_id: str, bus: NotificationBus = Depends(get_bus)):
    """标记单条通知为已读。"""
    ok = bus.mark_read(notification_id)
    if not ok:
        return APIResponse(success=False, error=f"通知 ID {notification_id} 不存在")
    return APIResponse(success=True, data={"unread_count": bus.unread_count()})


@router.delete("/clear-read", response_model=APIResponse)
def clear_read(bus: NotificationBus = Depends(get_bus)):
    """清除所有已读通知。"""
    deleted = bus.clear_read()
    return APIResponse(success=True, data={"deleted": deleted})
