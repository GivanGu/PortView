"""Docker 容器端口扫描器。

职责单一：通过 Docker SDK 读取容器端口映射信息（含已停止容器、host 网络容器）。
不涉及主机端口扫描、合并分析或配置逻辑。

扫描策略：
- ``get_docker_ports`` 读取所有容器（all=True），解析端口绑定
  来源：HostConfig.PortBindings（权威） + NetworkSettings.Ports（运行时）
- ``get_host_network_containers`` 通过缓存（TTL 30s）读取 host 模式容器
  的暴露端口、健康检查、入口命令、环境变量中的端口号
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 命令行参数中提取端口号的正则模式
_PORT_PATTERNS = [
    r"--port[=\s]+(\d{1,5})",
    r"-p[=\s]+(\d{1,5})",
    r"--listen[=\s]+(\d{1,5})",
    r"--bind[=\s]+[^:]*:(\d{1,5})",
    r":(\d{1,5})\b",
    r"PORT[=\s]+(\d{1,5})",
    r"HTTP_PORT[=\s]+(\d{1,5})",
]


class DockerScanner:
    """读取 Docker 容器端口映射。"""

    def __init__(self, docker_client: Any | None = None) -> None:
        self.docker_client: Any | None = docker_client
        if docker_client is None:
            self._try_connect()

        # host 网络容器缓存
        self._host_container_cache: dict[str, dict[str, Any]] = {}
        self._cache_timestamp: float = 0.0
        self._cache_ttl: int = 30  # 秒

    def _try_connect(self) -> None:
        """ 尝试从环境加载 Docker 客户端。"""
        try:
            import docker  # type: ignore

            self.docker_client = docker.from_env()
            logger.info("Docker 客户端连接成功")
        except Exception as e:  # noqa: BLE001
            logger.error("Docker 客户端连接失败: %s", e)
            self.docker_client = None

    def reconnect(self) -> None:
        """ 重新连接 Docker 客户端并清空缓存。"""
        self._try_connect()
        self._host_container_cache = {}
        self._cache_timestamp = 0.0

    # ------------------------------------------------------------------ #
    # 容器端口映射
    # ------------------------------------------------------------------ #
    def get_docker_ports(self) -> list[dict[str, Any]]:
        """获取所有容器（含已停止）的端口映射信息。"""
        if not self.docker_client:
            logger.warning("Docker 客户端未连接，跳过容器端口扫描")
            return []

        try:
            containers = self.docker_client.containers.list(all=True)
            logger.info("发现 %d 个容器（含已停止）", len(containers))
        except Exception as e:  # noqa: BLE001
            logger.error("获取 Docker 容器列表失败: %s", e)
            return []

        ports_info: list[dict[str, Any]] = []
        for container in containers:
            try:
                ports_info.extend(self._parse_container(container))
            except Exception as e:  # noqa: BLE001
                name = getattr(container, "name", "unknown")
                logger.warning("处理容器 %s 端口信息失败，已跳过: %s", name, e)
        return ports_info

    def _parse_container(self, container: Any) -> list[dict[str, Any]]:
        """解析单个容器的端口映射。"""
        result: list[dict[str, Any]] = []
        attrs = container.attrs or {}
        name = container.name

        state_info = attrs.get("State", {}) or {}
        is_running = bool(state_info.get("Running", False))
        container_status = str(
            state_info.get("Status", container.status or "unknown")
        ).lower()
        container_image = attrs.get("Config", {}).get("Image", "")

        # 端口绑定双来源去重
        seen: set[tuple[int, str]] = set()
        mappings: list[tuple[int, str]] = []
        for source_ports in (
            attrs.get("HostConfig", {}).get("PortBindings", {}) or {},
            attrs.get("NetworkSettings", {}).get("Ports", {}) or {},
        ):
            if not source_ports:
                continue
            for container_port, host_bindings in source_ports.items():
                if not host_bindings:
                    continue
                for binding in host_bindings:
                    host_port_str = binding.get("HostPort")
                    if not host_port_str:
                        continue
                    try:
                        host_port = int(host_port_str)
                    except (ValueError, TypeError):
                        continue
                    key = (host_port, container_port)
                    if key in seen:
                        continue
                    seen.add(key)
                    mappings.append(key)

        for host_port, container_port in mappings:
            protocol = "UDP" if "/udp" in str(container_port).lower() else "TCP"
            result.append(
                {
                    "port": host_port,
                    "container_name": name,
                    "container_port": container_port,
                    "type": "docker_mapped",
                    "container_image": container_image,
                    "is_running": is_running,
                    "container_status": container_status,
                    "protocol": protocol,
                }
            )

        # host 网络模式容器
        if attrs.get("HostConfig", {}).get("NetworkMode", "") == "host":
            result.append(
                {
                    "port": None,
                    "container_name": name,
                    "container_port": "host模式",
                    "type": "docker_host",
                    "container_image": container_image,
                    "is_running": is_running,
                    "container_status": container_status,
                }
            )
        return result

    # ------------------------------------------------------------------ #
    # host 网络容器信息（用于主机端口映射推断）
    # ------------------------------------------------------------------ #
    def get_host_network_containers(self) -> dict[str, dict[str, Any]]:
        """获取 host 网络容器信息（带 TTL 缓存）。"""
        current_time = time.time()
        if (
            (current_time - self._cache_timestamp) < self._cache_ttl
            and self._host_container_cache
        ):
            return self._host_container_cache

        self._host_container_cache = {}
        if not self.docker_client:
            return self._host_container_cache

        try:
            containers = self.docker_client.containers.list()
            for container in containers:
                if (container.attrs or {}).get("HostConfig", {}).get(
                    "NetworkMode", ""
                ) != "host":
                    continue
                info: dict[str, Any] = {
                    "name": container.name,
                    "id": container.id[:12],
                    "image": container.image.tags[0]
                    if container.image.tags
                    else "unknown",
                    "exposed_ports": set(),
                    "potential_ports": set(),
                    "healthcheck_ports": set(),
                    "entrypoint_ports": set(),
                }
                config = container.attrs.get("Config", {}) or {}

                self._extract_exposed(info, config)
                self._extract_healthcheck(info, config)
                self._extract_entrypoint(info, config)
                self._extract_env(info, config)

                info["exposed_ports"].update(info["potential_ports"])
                self._host_container_cache[container.name] = info
        except Exception as e:  # noqa: BLE001
            logger.error("获取 Docker 容器信息失败: %s", e)

        self._cache_timestamp = current_time
        return self._host_container_cache

    @staticmethod
    def _extract_exposed(info: dict[str, Any], config: dict[str, Any]) -> None:
        for port_spec in config.get("ExposedPorts", {}) or {}:
            if "/" in port_spec:
                try:
                    info["exposed_ports"].add(int(port_spec.split("/")[0]))
                except ValueError:
                    continue

    @staticmethod
    def _extract_healthcheck(info: dict[str, Any], config: dict[str, Any]) -> None:
        healthcheck = config.get("Healthcheck", {})
        if not healthcheck or "Test" not in healthcheck:
            return
        test_cmd = (
            " ".join(healthcheck["Test"])
            if isinstance(healthcheck["Test"], list)
            else str(healthcheck["Test"])
        )
        for port_str in re.findall(
            r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0):?(\d{1,5})", test_cmd
        ):
            port = int(port_str)
            if 1 <= port <= 65535:
                info["healthcheck_ports"].add(port)
                info["potential_ports"].add(port)

    @staticmethod
    def _extract_entrypoint(info: dict[str, Any], config: dict[str, Any]) -> None:
        full_command: list[str] = []
        entrypoint = config.get("Entrypoint", [])
        cmd = config.get("Cmd", [])
        if entrypoint:
            full_command.extend(
                entrypoint if isinstance(entrypoint, list) else [entrypoint]
            )
        if cmd:
            full_command.extend(cmd if isinstance(cmd, list) else [cmd])
        command_str = " ".join(str(arg) for arg in full_command)
        for pattern in _PORT_PATTERNS:
            for port_str in re.findall(pattern, command_str, re.IGNORECASE):
                port = int(port_str)
                if 1 <= port <= 65535:
                    info["entrypoint_ports"].add(port)
                    info["potential_ports"].add(port)

    @staticmethod
    def _extract_env(info: dict[str, Any], config: dict[str, Any]) -> None:
        for env_var in config.get("Env", []) or []:
            if "=" not in env_var:
                continue
            key, value = env_var.split("=", 1)
            if any(kw in key.upper() for kw in ("PORT", "LISTEN", "BIND")):
                for port_str in re.findall(r"\b(\d{1,5})\b", value):
                    port = int(port_str)
                    if 1 <= port <= 65535:
                        info["potential_ports"].add(port)
