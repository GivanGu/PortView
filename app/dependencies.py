"""FastAPI 依赖注入。"""

from __future__ import annotations

from functools import lru_cache

from app.services.port_monitor import PortMonitor


@lru_cache
def get_monitor() -> PortMonitor:
    """返回共享的 PortMonitor 单例。"""
    return PortMonitor()
