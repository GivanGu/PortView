"""FastAPI 依赖注入。

提供共享的服务单例：
- :func:`get_docker_scanner`   — Docker 扫描器
- :func:`get_host_scanner`     — 主机端口扫描器
- :func:`get_port_analyzer`    — 端口分析器（依赖上两者）
- :func:`get_notification_bus` — 通知总线
"""
from __future__ import annotations

from functools import lru_cache

from app.services.docker_scanner import DockerScanner
from app.services.host_scanner import HostScanner
from app.services.notification_bus import NotificationBus
from app.services.port_analyzer import PortAnalyzer


@lru_cache
def get_docker_scanner() -> DockerScanner:
    """返回共享的 DockerScanner 单例。"""
    return DockerScanner()


@lru_cache
def get_host_scanner() -> HostScanner:
    """返回共享的 HostScanner 单例。"""
    return HostScanner(get_docker_scanner())


@lru_cache
def get_port_analyzer() -> PortAnalyzer:
    """返回共享的 PortAnalyzer 单例。"""
    return PortAnalyzer(get_docker_scanner(), get_host_scanner())


@lru_cache
def get_notification_bus() -> NotificationBus:
    """返回共享的 NotificationBus 单例。"""
    return NotificationBus.get()
