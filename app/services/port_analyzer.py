"""端口分析器 — 合并 Docker + 主机端口，生成卡片 & 统计。

本模块负责：
1. 合并 Docker 端口映射 + 主机监听端口，去重
2. 合并连续未知服务端口 & 插入可用端口间隙卡片
3. 过滤隐藏端口
4. 端口冲突检测
5. 协议过滤 & 搜索过滤

输出 PortCard 列表 + 统计摘要，供 /api/ports 返回。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.docker_scanner import DockerScanner
from app.services.host_scanner import HostScanner

logger = logging.getLogger(__name__)


class PortAnalyzer:
    """端口分析与合并引擎。"""

    def __init__(
        self,
        docker_scanner: DockerScanner,
        host_scanner: HostScanner,
    ) -> None:
        self.docker_scanner = docker_scanner
        self.host_scanner = host_scanner

    # ------------------------------------------------------------------ #
    # 入口
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        config: dict[str, Any],
        start_port: int = 1,
        end_port: int = 65535,
        protocol_filter: Optional[str] = None,
        hidden_ports: Optional[list[int]] = None,
    ) -> dict[str, Any]:
        """生成一次完整的端口分析结果。"""
        hidden_ports = hidden_ports or []

        # 1. 扫描
        docker_ports = self.docker_scanner.get_docker_ports()
        host_ports_info = self.host_scanner.get_host_ports(config)

        # 2. 收集协议集合
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
        docker_ports.sort(key=lambda p: p.get("is_running", True))
        docker_port_map: dict[int, dict[str, Any]] = {}
        for port_info in docker_ports:
            if not port_info.get("port"):
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

        # 3. 协议过滤
        if protocol_filter == "TCP":
            filtered_ports = tcp_ports
        elif protocol_filter == "UDP":
            filtered_ports = udp_ports
        else:
            filtered_ports = tcp_ports.union(udp_ports)

        sorted_ports = sorted(filtered_ports)

        # 4. 生成卡片
        port_data_list = self._build_port_cards(
            sorted_ports, config, docker_port_map, host_ports_info, port_protocol_map
        )

        # 5. 合并 + 间隙
        port_cards = self._merge_unknown_and_gaps(port_data_list, start_port, end_port)

        # 6. 冲突检测
        conflict_map = self._detect_conflicts(
            sorted_ports, docker_port_map, host_ports_info
        )
        for card in port_cards:
            if card["type"] == "used" and card["port"] in conflict_map:
                card["conflict"] = True
                card["conflict_sources"] = conflict_map[card["port"]]

        # 7. 过滤隐藏端口
        if hidden_ports:
            port_cards = [c for c in port_cards if not self._card_hidden(c, hidden_ports)]

        # 8. 统计
        docker_container_count = len(
            {
                p.get("container", p.get("container_name", ""))
                for p in port_cards
                if p.get("source") == "docker" and p.get("container")
            }
        )

        # 统计时使用未过滤的 filtered_ports
        total_used = len(filtered_ports)
        total_available = max(0, (end_port - start_port + 1) - total_used)

        result: dict[str, Any] = {
            "port_cards": port_cards,
            "total_used": total_used,
            "total_available": total_available,
            "tcp_used": len(tcp_ports),
            "udp_used": len(udp_ports),
            "docker_containers": docker_container_count,
            "hidden_ports": hidden_ports,
            "protocol_filter": protocol_filter,
            "start_port": start_port,
            "end_port": end_port,
        }
        return result

    # ------------------------------------------------------------------ #
    # 卡片生成
    # ------------------------------------------------------------------ #
    def _build_port_cards(
        self,
        sorted_ports: list[int],
        config: dict[str, Any],
        docker_port_map: dict[int, dict[str, Any]],
        host_ports_info: dict[int, dict[str, Any]],
        port_protocol_map: dict[int, str],
    ) -> list[dict[str, Any]]:
        """为每个使用中的端口生成 used 卡片。"""
        port_data_list: list[dict[str, Any]] = []
        for port in sorted_ports:
            protocol = port_protocol_map.get(port, "TCP")
            config_service_type, config_service_name = self._lookup_config(port, config)

            docker_info = docker_port_map.get(port)
            docker_is_running = docker_info.get("is_running", True) if docker_info else True
            port_actively_listened = port in host_ports_info
            use_docker_card = docker_info is not None and (
                docker_is_running or not port_actively_listened
            )

            if use_docker_card:
                source = (
                    config_service_type
                    if config_service_type in ("docker", "host")
                    else "docker"
                )
                card = {
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
                    "is_host_network": False,
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
                card = {
                    "port": port,
                    "type": "used",
                    "source": source,
                    "protocol": protocol,
                    "service_name": config_service_name
                    or host_info.get("service_name", "未知服务"),
                    "container": host_info.get("container_name"),
                    "is_host_network": is_host_container,
                }
            port_data_list.append(card)
        return port_data_list

    # ------------------------------------------------------------------ #
    # 合并未知 + 间隙
    # ------------------------------------------------------------------ #
    def _merge_unknown_and_gaps(
        self,
        port_data_list: list[dict[str, Any]],
        start_port: int,
        end_port: int,
    ) -> list[dict[str, Any]]:
        """合并连续未知服务端口，并插入可用端口间隙卡片。"""
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
                current_last_port = (
                    last_card["end_port"]
                    if last_card["type"] == "unknown_range"
                    else last_card.get("port")
                )
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
                    last_card["available_count"] = (
                        last_card["end_port"] - last_card["start_port"] + 1
                    )
            else:
                last_port = (
                    last_card["end_port"]
                    if last_card["type"] == "unknown_range"
                    else last_card.get("port", 0)
                )
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

    # ------------------------------------------------------------------ #
    # 隐藏过滤
    # ------------------------------------------------------------------ #
    @staticmethod
    def _card_hidden(card: dict[str, Any], hidden_ports: list[int]) -> bool:
        hidden = set(hidden_ports)
        if card["type"] == "used":
            return card["port"] in hidden
        if card["type"] == "unknown_range":
            return any(p in hidden for p in range(card["start_port"], card["end_port"] + 1))
        return False

    # ------------------------------------------------------------------ #
    # 配置查找
    # ------------------------------------------------------------------ #
    @staticmethod
    def _lookup_config(
        port: int, config: dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """从 config 查找端口对应的 service_type + service_name。"""
        for service_name, service_config in config.items():
            if isinstance(service_config, dict) and service_config.get("port") == port:
                return service_config.get("service_type"), service_name
        return None, None

    # ------------------------------------------------------------------ #
    # 冲突检测
    # ------------------------------------------------------------------ #
    def _detect_conflicts(
        self,
        sorted_ports: list[int],
        docker_port_map: dict[int, dict[str, Any]],
        host_ports_info: dict[int, dict[str, Any]],
    ) -> dict[int, list[str]]:
        """检测同端口被多个来源占用。

        :return: {port: [冲突源描述列表]}
        """
        conflicts: dict[int, list[str]] = {}
        for port in sorted_ports:
            sources: list[str] = []
            docker_info = docker_port_map.get(port)
            if docker_info:
                sources.append(
                    f"Docker: {docker_info['container_name']} "
                    f"({docker_info.get('container_status', 'unknown')})"
                )
            host_info = host_ports_info.get(port)
            if host_info and host_info.get("container_name"):
                sources.append(f"主机容器: {host_info['container_name']}")

            if len(sources) >= 2:
                conflicts[port] = sources
        return conflicts
