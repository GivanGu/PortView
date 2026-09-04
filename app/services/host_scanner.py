"""主机监听端口扫描器。

职责：通过 psutil 读取主机监听端口（TCP/UDP、IPv4/IPv6），合并协议信息，
并结合 Docker host-网络容器缓存推断端口所属容器。

使用 psutil.net_connections 替代旧版的 netstat 子进程解析。
"""
from __future__ import annotations

import logging
import socket
from typing import Any, Optional

from app.services.docker_scanner import DockerScanner

logger = logging.getLogger(__name__)

# 常见端口 → 服务名 兜底映射
_DEFAULT_PORTS: dict[int, str] = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    67: "DHCP Server", 68: "DHCP Client", 69: "TFTP", 80: "HTTP",
    110: "POP3", 123: "NTP", 135: "RPC", 137: "NetBIOS Name",
    138: "NetBIOS Datagram", 139: "NetBIOS Session", 143: "IMAP",
    161: "SNMP", 389: "LDAP", 443: "HTTPS", 445: "SMB",
    465: "SMTPS", 514: "Syslog", 587: "SMTP", 631: "IPP",
    636: "LDAPS", 993: "IMAPS", 995: "POP3S", 1433: "SQL Server",
    1521: "Oracle", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    5900: "VNC", 6379: "Redis", 8080: "HTTP Proxy", 8443: "HTTPS Alt",
    9200: "Elasticsearch", 27017: "MongoDB",
}


class HostScanner:
    """主机监听端口扫描器。"""

    def __init__(self, docker_scanner: Optional[DockerScanner] = None) -> None:
        self.docker_scanner = docker_scanner
        self.default_ports = _DEFAULT_PORTS

    def get_host_ports(
        self, config: dict[str, Any]
    ) -> dict[int, dict[str, Any]]:
        """获取主机监听端口信息（psutil 实现，替代 netstat）。"""
        port_info: dict[int, dict[str, Any]] = {}
        port_protocols: dict[int, dict[str, set[str]]] = {}
        host_containers = (
            self.docker_scanner.get_host_network_containers()
            if self.docker_scanner
            else {}
        )

        try:
            import psutil  # type: ignore

            for conn in psutil.net_connections(kind="inet"):
                if conn.status != psutil.CONN_LISTEN:
                    continue
                try:
                    port = conn.laddr.port
                    address = conn.laddr.address
                except Exception:  # noqa: BLE001
                    continue

                proto_type = "UDP" if conn.proto == 17 else "TCP"
                ip_version = (
                    "IPv6" if conn.family == socket.AF_INET6 else "IPv4"
                )

                entry = port_protocols.setdefault(
                    port, {"protocols": set(), "ip_versions": set()}
                )
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

        # 合并协议字符串（含 IPv4/IPv6 信息，如 TCP/TCP6）
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

    def get_service_name(
        self, port: int, config: dict[str, Any]
    ) -> str:
        """根据端口号获取服务名称（配置文件映射 + 默认映射）。"""
        port_to_service: dict[int, str] = {}
        for key, value in config.items():
            if isinstance(value, dict) and "port" in value:
                port_to_service[value["port"]] = key
            elif isinstance(value, int):
                port_to_service[value] = key

        if port in port_to_service:
            return port_to_service[port]
        if port in self.default_ports:
            return self.default_ports[port]
        return "未知服务"
