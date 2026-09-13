"""内置默认 Logo（v1.5.13）：知名服务名 → 静态 SVG 图标。

纯增量回退机制：
- 仅当用户**未上传** Logo 时，按卡片 ``service_name`` 匹配内置图标。
- 用户上传 / discover 的 Logo 始终优先，本模块不覆盖、不写库。
- 图标为只读静态资源（``app/static/logos/*.svg``），随镜像打包。

归一化规则（前后端一致）：小写 + 去除所有非字母数字字符。
例：``"SQL Server"`` → ``sqlserver``，``"DHCP Server"`` → ``dhcpserver``。
"""

from __future__ import annotations

import re
from pathlib import Path

# app/static/logos 目录（相对本文件：services/ → app/ → static/logos）
_LOGO_DIR = Path(__file__).resolve().parent.parent / "static" / "logos"

# 归一化 service_name → SVG 文件名
DEFAULT_LOGOS: dict[str, str] = {
    "mysql": "mysql.svg",
    "mariadb": "mariadb.svg",
    "postgresql": "postgresql.svg",
    "redis": "redis.svg",
    "mongodb": "mongodb.svg",
    "elasticsearch": "elasticsearch.svg",
    "oracle": "oracle.svg",
    "sqlserver": "sqlserver.svg",
    "http": "http.svg",
    "https": "https.svg",
    "ssh": "ssh.svg",
    "ftp": "ftp.svg",
    "tftp": "tftp.svg",
    "smtp": "smtp.svg",
    "smtps": "smtps.svg",
    "dns": "dns.svg",
    "imap": "imap.svg",
    "imaps": "imaps.svg",
    "pop3": "pop3.svg",
    "pop3s": "pop3s.svg",
    "telnet": "telnet.svg",
    "ldap": "ldap.svg",
    "ldaps": "ldaps.svg",
    "smb": "smb.svg",
    "rdp": "rdp.svg",
    "vnc": "vnc.svg",
    "snmp": "snmp.svg",
    "syslog": "syslog.svg",
    "ntp": "ntp.svg",
    "dhcpserver": "dhcpserver.svg",
    "dhcpclient": "dhcpclient.svg",
    "netbiosname": "netbiosname.svg",
    "netbiosdatagram": "netbiosdatagram.svg",
    "netbiossession": "netbiossession.svg",
    "rpc": "rpc.svg",
    "ipp": "ipp.svg",
    "portview": "portview.svg",
}

_NON_ALNUM = re.compile(r"[^a-z0-9]")

# 知名端口 → Logo key（与 port_monitor._DEFAULT_PORTS 对齐，端口匹配最可靠，
# 不受 service_name 为「未知服务」/自定义名的影响）。
PORT_LOGOS: dict[int, str] = {
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "dns",
    67: "dhcpserver",
    68: "dhcpclient",
    69: "tftp",
    80: "http",
    110: "pop3",
    123: "ntp",
    135: "rpc",
    137: "netbiosname",
    138: "netbiosdatagram",
    139: "netbiossession",
    143: "imap",
    161: "snmp",
    389: "ldap",
    443: "https",
    445: "smb",
    465: "smtps",
    514: "syslog",
    587: "smtp",
    631: "ipp",
    636: "ldaps",
    993: "imaps",
    995: "pop3s",
    1433: "sqlserver",
    1521: "oracle",
    3306: "mysql",
    3389: "rdp",
    5432: "postgresql",
    5900: "vnc",
    6379: "redis",
    8080: "http",
    8081: "portview",
    8443: "https",
    9200: "elasticsearch",
    27017: "mongodb",
}


def normalize(name: str) -> str:
    """归一化 service_name：小写 + 去除非字母数字（与前端 logo.ts 一致）。"""
    return _NON_ALNUM.sub("", (name or "").lower())


def available_keys() -> list[str]:
    """所有可用默认 Logo 的归一化 key（供前端按 service_name 匹配）。"""
    return sorted(DEFAULT_LOGOS.keys())


def port_map() -> dict[str, str]:
    """知名端口 → Logo key（JSON 友好，key 转字符串；供前端按端口匹配）。"""
    return {str(p): k for p, k in PORT_LOGOS.items()}


def resolve(key: str) -> Path | None:
    """按归一化 key 解析 SVG 文件路径；未知或文件缺失返回 None。"""
    fname = DEFAULT_LOGOS.get(key)
    if not fname:
        return None
    path = _LOGO_DIR / fname
    return path if path.is_file() else None
