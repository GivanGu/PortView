"""通知总线 — 内存环形缓冲区，保存最近 N 条通知。

用于：
- 端口冲突告警
- 容器启停提醒
- 配置变更记录

不依赖外部消息队列，内存存储（进程重启清空），NAS 场景足够。
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_MAX_SIZE = 200


class NotificationLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class NotificationType(str, Enum):
    PORT_CONFLICT = "port_conflict"
    CONTAINER_START = "container_start"
    CONTAINER_STOP = "container_stop"
    PORT_NEW = "port_new"
    PORT_GONE = "port_gone"
    CONFIG_CHANGE = "config_change"
    SYSTEM = "system"


@dataclass
class Notification:
    """单条通知。"""
    id: str
    type: NotificationType
    level: NotificationLevel
    title: str
    message: str
    timestamp: float = field(default_factory=time.time)
    read: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp,
            "read": self.read,
        }


class NotificationBus:
    """线程安全的通知总线（单例）。"""

    _instance: Optional["NotificationBus"] = None
    _lock = threading.Lock()

    def __init__(self, max_size: int = _DEFAULT_MAX_SIZE) -> None:
        self._deque: deque = deque(maxlen=max_size)
        self._subscribers: list = []

    @classmethod
    def get(cls) -> "NotificationBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def push(
        self,
        notification_type,
        level,
        title: str,
        message: str,
    ):
        """推送一条通知。"""
        if not isinstance(notification_type, NotificationType):
            notification_type = NotificationType(notification_type)
        if not isinstance(level, NotificationLevel):
            level = NotificationLevel(level)

        notif = Notification(
            id=_generate_id(),
            type=notification_type,
            level=level,
            title=title,
            message=message,
        )
        self._deque.appendleft(notif)
        logger.info("通知: [%s] %s", notif.type.value, notif.title)

        for sub in self._subscribers[:]:
            try:
                sub(notif)
            except Exception:  # noqa: BLE001
                logger.debug("订阅者回调异常", exc_info=True)
        return notif

    def get_recent(self, limit: int = 50, unread_only: bool = False) -> list:
        """获取最近 N 条通知。"""
        items = list(self._deque)
        if unread_only:
            items = [n for n in items if not n.read]
        return [n.to_dict() for n in items[:limit]]

    def mark_read(self, notification_id: str) -> bool:
        for notif in self._deque:
            if notif.id == notification_id:
                notif.read = True
                return True
        return False

    def mark_all_read(self) -> int:
        count = 0
        for notif in self._deque:
            if not notif.read:
                notif.read = True
                count += 1
        return count

    def unread_count(self) -> int:
        return sum(1 for n in self._deque if not n.read)

    def clear_read(self) -> int:
        before = len(self._deque)
        self._deque = deque(
            [n for n in self._deque if not n.read],
            maxlen=self._deque.maxlen,
        )
        return before - len(self._deque)

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback) -> None:
        self._subscribers = [s for s in self._subscribers if s != callback]


def _generate_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]
