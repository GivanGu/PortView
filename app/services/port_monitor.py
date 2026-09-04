"""PortMonitor — 向后兼容的聚合入口。

⚠️  该文件已被拆分为以下模块，此处仅对旧代码（tests/旧 import）提供兼容：

    - app/services/docker_scanner.py   — DockerScanner
    - app.services.host_scanner.py     — HostScanner
    - app.services.port_analyzer.py    — PortAnalyzer
    - app.services.notification_bus.py — NotificationBus

PortMonitor 仍然可用，但内部委派给 PortAnalyzer。
新代码应直接使用 get_port_analyzer() 依赖注入。
"""
from __future__ import annotations

import warnings
from typing import Any, Optional

from app.services.docker_scanner import DockerScanner
from app.services.host_scanner import HostScanner
from app.services.port_analyzer import PortAnalyzer

_DEFAULT_WARNED = False


class PortMonitor:
    """向后兼容的 PortMonitor（委派给 PortAnalyzer）。"""

    def __init__(self, docker_client: Any | None = None) -> None:
        global _DEFAULT_WARNED
        if not _DEFAULT_WARNED:
            warnings.warn(
                "PortMonitor 已废弃，请使用 get_port_analyzer() + PortAnalyzer "
                "(app.services.port_analyzer)",
                DeprecationWarning,
                stacklevel=2,
            )
            _DEFAULT_WARNED = True

        self._docker = DockerScanner(docker_client)
        self._host = HostScanner(self._docker)
        self._analyzer = PortAnalyzer(self._docker, self._host)

    # ---- 兼容方法 ----
    def reconnect(self) -> None:
        self._docker.reconnect()

    def get_docker_ports(self) -> list[dict[str, Any]]:
        return self._docker.get_docker_ports()

    def get_host_ports(self, config: dict[str, Any]) -> dict[int, dict[str, Any]]:
        return self._host.get_host_ports(config)

    def get_port_analysis(
        self,
        config: dict[str, Any],
        start_port: int = 1,
        end_port: int = 65535,
        protocol_filter: Optional[str] = None,
        hidden_ports: Optional[list[int]] = None,
    ) -> dict[str, Any]:
        return self._analyzer.analyze(
            config=config,
            start_port=start_port,
            end_port=end_port,
            protocol_filter=protocol_filter,
            hidden_ports=hidden_ports,
        )

    # 静态方法继承（测试兼容）
    _card_hidden = PortAnalyzer.__dict__.get("_card_hidden", staticmethod(lambda *a: False))
