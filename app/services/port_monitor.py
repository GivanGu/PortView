"""端口监控核心逻辑。

负责：
1. 通过 Docker API 读取容器端口映射（含已停止容器、host 网络容器）
2. 通过 psutil 读取主机监听端口（TCP/UDP、IPv4/IPv6）
3. 合并两者，生成可视化端口卡片（已用 / 可用 / 未知合并）

与旧版差异：
- ``netstat`` 子进程解析 → ``psutil.net_connections``
- 配置从全局变量 → 由调用方传入（便于测试）
"""

from __future__ import annotations

import logging
import re
import socket
import time
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# 常见端口 → 服务名 兜底映射
_DEFAULT_PORTS: dict[int, str] = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 67: "DHCP Server",
    68: "DHCP Client", 69: "TFTP", 80: "HTTP", 110: "POP3", 123: "NTP", 135: "RPC",
    137: "NetBIOS Name", 138: "NetBIOS Datagram", 139: "NetBIOS Session", 143: "IMAP",
    161: "SNMP", 389: "LDAP", 443: "HTTPS", 445: "SMB", 465: "SMTPS", 514: "Syslog",
    587: "SMTP", 631: "IPP", 636: "LDAPS", 993: "IMAPS", 995: "POP3S", 1433: "SQL Server",
    1521: "Oracle", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
    6379: "Redis", 8080: "HTTP Proxy", 8443: "HTTPS Alt", 9200: "Elasticsearch",
    27017: "MongoDB",
}

_PORT_PATTERNS = [
    r"--port[=\s]+(\d{1,5})",
    r"-p[=\s]+(\d{1,5})",
    r"--listen[=\s]+(\d{1,5})",
    r"--bind[=\s]+[^:]*:(\d{1,5})",
    r":(\d{1,5})\b",
    r"PORT[=\s]+(\d{1,5})",
    r"HTTP_PORT[=\s]+(\d{1,5})",
]


class PortMonitor:
    """端口监控器。"""

    def __init__(self, docker_client: Any | None = None) -> None:
        """初始化 Docker 客户端。

        :param docker_client: 可注入的 docker 客户端（测试用）；
            为 ``None`` 时尝试 ``docker.from_env()``。
        """
        if docker_client is not None:
            self.docker_client = docker_client
        else:
            try:
                import docker

                self.docker_client = docker.from_env()
                logger.info("Docker 客户端连接成功")
            except Exception as e:  # noqa: BLE001
                logger.error("Docker 客户端连接失败: %s", e)
                self.docker_client = None

        # host 网络容器缓存
        self.container_cache: dict[str, dict[str, Any]] = {}
        self.cache_timestamp = 0.0
        self.cache_ttl = 30  # 秒

        self.default_ports = _DEFAULT_PORTS

    def reconnect(self) -> None:
        """重新连接 Docker 客户端并清空缓存（供刷新接口调用）。"""
        try:
            import docker

            self.docker_client = docker.from_env()
            logger.info("Docker 客户端重连成功")
        except Exception as e:  # noqa: BLE001
            logger.error("Docker 客户端重连失败: %s", e)
            self.docker_client = None
        self.container_cache = {}
        self.cache_timestamp = 0.0

    # ------------------------------------------------------------------ #
    # Docker
    # ------------------------------------------------------------------ #
    def get_docker_ports(self) -> list[dict[str, Any]]:
        """获取 Docker 容器端口映射信息（含已停止容器）。"""
        ports_info: list[dict[str, Any]] = []
        if not self.docker_client:
            logger.warning("Docker 客户端未连接")
            return ports_info

        try:
            containers = self.docker_client.containers.list(all=True)
            logger.info("发现 %d 个容器（含已停止）", len(containers))
        except Exception as e:  # noqa: BLE001
            logger.error("获取 Docker 端口信息失败: %s", e)
            return ports_info

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
        container_status = str(state_info.get("Status", container.status or "unknown")).lower()
        container_image = attrs.get("Config", {}).get("Image", "")

        # 端口绑定两个来源：HostConfig.PortBindings（权威）+ NetworkSettings.Ports（运行时）
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
    # Host
    # ------------------------------------------------------------------ #
    def get_host_ports(self, config: dict[str, Any]) -> dict[int, dict[str, Any]]:
        """获取主机监听端口（psutil 实现，替代 netstat）。"""
        port_info: dict[int, dict[str, Any]] = {}
        port_protocols: dict[int, dict[str, set[str]]] = {}
        host_containers = self.get_host_network_containers_cached()

        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status != psutil.CONN_LISTEN:
                    continue
                try:
                    port = conn.laddr.port
                    address = conn.laddr.address
                except Exception:  # noqa: BLE001
                    continue

                proto_type = "UDP" if conn.proto == 17 else "TCP"
                ip_version = "IPv6" if conn.family == socket.AF_INET6 else "IPv4"

                entry = port_protocols.setdefault(port, {"protocols": set(), "ip_versions": set()})
                entry["protocols"].add(proto_type)
                entry["ip_versions"].add(ip_version)

                if port not in port_info:
                    container_name = None
                    for cinfo in host_containers.values():
                        if port in cinfo["exposed_ports"]:
                            container_name = cinfo["name"]
                            break
                    port_info[port] = {
                        "port": port,
                        "protocol": proto_type,
                        "ip_version": ip_version,
                        "address": address,
                        "service_name": self.get_service_name(port, config),
                        "container_name": container_name,
                    }
        except Exception as e:  # noqa: BLE001
            logger.error("获取主机端口信息失败: %s", e)

        # 合并协议（含 IPv4/IPv6 信息，如 TCP/TCP6）
        for port, info in port_info.items():
            protocols = port_protocols[port]["protocols"]
            ip_versions = port_protocols[port]["ip_versions"]
            protocol_list: list[str] = []
            for protocol in sorted(protocols):
                if "IPv4" in ip_versions and "IPv6" in ip_versions:
                    protocol_list.extend([protocol, protocol + "6"])
                elif "IPv6" in ip_versions:
                    protocol_list.append(protocol + "6")
                else:
                    protocol_list.append(protocol)
            info["protocol"] = "/".join(sorted(set(protocol_list)))
            info.pop("ip_version", None)

        return port_info

    def get_service_name(self, port: int, config: dict[str, Any]) -> str:
        """根据端口号获取服务名称（配置文件映射 + 默认映射）。"""
        port_to_service: dict[int, str] = {}
        for k, v in config.items():
            if isinstance(v, dict) and "port" in v:
                port_to_service[v["port"]] = k
            elif isinstance(v, int):
                port_to_service[v] = k

        if port in port_to_service:
            return port_to_service[port]
        if port in self.default_ports:
            return self.default_ports[port]
        return "未知服务"

    def get_host_network_containers_cached(self) -> dict[str, dict[str, Any]]:
        """获取 host 网络容器信息（带缓存）。"""
        current_time = time.time()
        if (current_time - self.cache_timestamp) < self.cache_ttl and self.container_cache:
            return self.container_cache

        self.container_cache = {}
        if not self.docker_client:
            return self.container_cache

        try:
            containers = self.docker_client.containers.list()
            for container in containers:
                if (container.attrs or {}).get("HostConfig", {}).get("NetworkMode", "") != "host":
                    continue
                info: dict[str, Any] = {
                    "name": container.name,
                    "id": container.id[:12],
                    "image": (container.image.tags[0] if container.image.tags else "unknown"),
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
                self.container_cache[container.name] = info
        except Exception as e:  # noqa: BLE001
            logger.error("获取 Docker 容器信息失败: %s", e)

        self.cache_timestamp = current_time
        return self.container_cache

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
        test_cmd = " ".join(healthcheck["Test"]) if isinstance(healthcheck["Test"], list) else str(healthcheck["Test"])
        for port_str in re.findall(r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0):?(\d{1,5})", test_cmd):
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
            full_command.extend(entrypoint if isinstance(entrypoint, list) else [entrypoint])
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

    # ------------------------------------------------------------------ #
    # 分析
    # ------------------------------------------------------------------ #
    def get_port_analysis(
        self,
        config: dict[str, Any],
        start_port: int = 1,
        end_port: int = 65535,
        protocol_filter: str | None = None,
        hidden_ports: list[int] | None = None,
    ) -> dict[str, Any]:
        """分析端口使用情况并生成可视化数据。"""
        hidden_ports = hidden_ports if hidden_ports is not None else []
        docker_ports = self.get_docker_ports()
        host_ports_info = self.get_host_ports(config)

        tcp_ports: set[int] = set()
        udp_ports: set[int] = set()
        port_protocol_map: dict[int, str] = {}

        # 主机端口
        for port, info in host_ports_info.items():
            if port < start_port or port > end_port:
                continue
            protocol = info.get("protocol", "TCP")
            port_protocol_map[port] = protocol
            if "TCP" in protocol.upper():
                tcp_ports.add(port)
            if "UDP" in protocol.upper():
                udp_ports.add(port)

        # Docker 端口（运行中优先）
        docker_ports = sorted(docker_ports, key=lambda p: p.get("is_running", True))
        docker_port_map: dict[int, dict[str, Any]] = {}
        for port_info in docker_ports:
            if not port_info["port"]:
                continue
            port = port_info["port"]
            if port < start_port or port > end_port:
                continue
            if port in docker_port_map and port_info.get("is_running", True):
                docker_port_map[port] = port_info
            elif port not in docker_port_map:
                docker_port_map[port] = port_info
            docker_protocol = port_info.get("protocol", "TCP")
            if docker_protocol == "UDP":
                udp_ports.add(port)
            else:
                tcp_ports.add(port)
            port_protocol_map.setdefault(port, docker_protocol)

        # 协议过滤
        if protocol_filter == "TCP":
            filtered_ports = tcp_ports
        elif protocol_filter == "UDP":
            filtered_ports = udp_ports
        else:
            filtered_ports = tcp_ports.union(udp_ports)

        sorted_ports = sorted(filtered_ports)

        # 生成卡片
        port_data_list: list[dict[str, Any]] = []
        for port in sorted_ports:
            protocol = port_protocol_map.get(port, "TCP")
            if protocol_filter and protocol_filter.upper() not in protocol.upper():
                continue

            config_service_type = None
            config_service_name = None
            for service_name, service_config in config.items():
                if isinstance(service_config, dict) and service_config.get("port") == port:
                    config_service_type = service_config.get("service_type")
                    config_service_name = service_name
                    break

            docker_info = docker_port_map.get(port)
            docker_is_running = docker_info.get("is_running", True) if docker_info else True
            port_actively_listened = port in host_ports_info
            use_docker_card = docker_info is not None and (docker_is_running or not port_actively_listened)

            if use_docker_card:
                source = config_service_type if config_service_type in ("docker", "host") else "docker"
                card_data: dict[str, Any] = {
                    "port": port,
                    "type": "used",
                    "source": source,
                    "protocol": protocol,
                    "container": docker_info["container_name"],
                    "process": f"Docker: {docker_info['container_name']}",
                    "image": docker_info.get("container_image", ""),
                    "container_port": docker_info["container_port"],
                    "service_name": config_service_name or docker_info["container_name"],
                    "is_running": docker_info.get("is_running", True),
                    "container_status": docker_info.get("container_status", "running"),
                }
            else:
                host_info = host_ports_info.get(port, {})
                is_host_container = bool(host_info.get("container_name"))
                if config_service_type in ("docker", "host"):
                    source = config_service_type
                elif is_host_container:
                    source = "docker"
                else:
                    source = "system"
                card_data = {
                    "port": port,
                    "type": "used",
                    "source": source,
                    "protocol": protocol,
                    "service_name": config_service_name or host_info.get("service_name", "未知服务"),
                    "container": host_info.get("container_name"),
                    "is_host_network": is_host_container,
                }
            port_data_list.append(card_data)

        port_cards = self._merge_unknown_and_gaps(port_data_list, start_port, end_port)

        # 过滤隐藏端口
        if hidden_ports:
            port_cards = [c for c in port_cards if not self._card_hidden(c, hidden_ports)]

        # 统计
        docker_container_count = len(
            {
                p.get("container", p.get("container_name", ""))
                for p in port_cards
                if p.get("source") == "docker" and p.get("container")
            }
        )
        total_ports_in_range = end_port - start_port + 1
        if protocol_filter:
            available_ports = total_ports_in_range - len(filtered_ports)
        else:
            all_used_ports = tcp_ports.union(udp_ports)
            available_ports = total_ports_in_range - len(all_used_ports)

        return {
            "port_cards": port_cards,
            "total_used": len(filtered_ports),
            "total_available": max(0, available_ports),
            "tcp_used": len(tcp_ports),
            "udp_used": len(udp_ports),
            "docker_containers": docker_container_count,
            "hidden_ports": hidden_ports,
            "protocol_filter": protocol_filter,
        }

    @staticmethod
    def _card_hidden(card: dict[str, Any], hidden_ports: list[int]) -> bool:
        hidden = set(hidden_ports)
        if card["type"] == "used":
            return card["port"] in hidden
        if card["type"] == "unknown_range":
            return any(p in hidden for p in range(card["start_port"], card["end_port"] + 1))
        return False

    def _merge_unknown_and_gaps(
        self,
        port_data_list: list[dict[str, Any]],
        start_port: int,
        end_port: int,
    ) -> list[dict[str, Any]]:
        """合并连续未知端口，并插入可用端口间隙卡片。"""
        port_cards: list[dict[str, Any]] = []
        i = 0
        while i < len(port_data_list):
            current = port_data_list[i]

            if current["service_name"] == "未知服务":
                consecutive = [current]
                j = i + 1
                while (
                    j < len(port_data_list)
                    and port_data_list[j]["service_name"] == "未知服务"
                    and port_data_list[j]["port"] == port_data_list[j - 1]["port"] + 1
                ):
                    consecutive.append(port_data_list[j])
                    j += 1

                if len(consecutive) >= 2:
                    port_cards.append(
                        {
                            "type": "unknown_range",
                            "start_port": consecutive[0]["port"],
                            "end_port": consecutive[-1]["port"],
                            "port_count": len(consecutive),
                            "source": consecutive[0]["source"],
                            "protocol": consecutive[0]["protocol"],
                            "service_name": "未知服务",
                            "container": consecutive[0].get("container"),
                            "is_host_network": consecutive[0].get("is_host_network", False),
                        }
                    )
                    i = j
                else:
                    port_cards.append(current)
                    i += 1
            else:
                port_cards.append(current)
                i += 1

            # 间隙卡片
            if i < len(port_data_list):
                last_card = port_cards[-1]
                current_last_port = last_card["end_port"] if last_card["type"] == "unknown_range" else last_card.get("port")
                next_port = port_data_list[i]["port"]
                gap = next_port - current_last_port - 1
                if gap > 0:
                    port_cards.append(
                        {
                            "type": "gap",
                            "start_port": current_last_port + 1,
                            "end_port": next_port - 1,
                            "available_count": gap,
                        }
                    )

        # 末尾到 end_port 的间隙
        if port_cards:
            last_card = port_cards[-1]
            if last_card["type"] == "gap":
                if last_card["end_port"] < end_port:
                    last_card["end_port"] = end_port
                    last_card["available_count"] = last_card["end_port"] - last_card["start_port"] + 1
            else:
                last_port = last_card["end_port"] if last_card["type"] == "unknown_range" else last_card.get("port", 0)
                if last_port < end_port:
                    final_gap = end_port - last_port
                    if final_gap > 0:
                        port_cards.append(
                            {
                                "type": "gap",
                                "start_port": last_port + 1,
                                "end_port": end_port,
                                "available_count": final_gap,
                            }
                        )
        else:
            port_cards.append(
                {
                    "type": "gap",
                    "start_port": start_port,
                    "end_port": end_port,
                    "available_count": end_port - start_port + 1,
                }
            )
        return port_cards
