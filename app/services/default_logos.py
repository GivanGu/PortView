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


def normalize(name: str) -> str:
    """归一化 service_name：小写 + 去除非字母数字（与前端 logo.ts 一致）。"""
    return _NON_ALNUM.sub("", (name or "").lower())


def available_keys() -> list[str]:
    """所有可用默认 Logo 的归一化 key（供前端判断是否匹配）。"""
    return sorted(DEFAULT_LOGOS.keys())


def resolve(key: str) -> Path | None:
    """按归一化 key 解析 SVG 文件路径；未知或文件缺失返回 None。"""
    fname = DEFAULT_LOGOS.get(key)
    if not fname:
        return None
    path = _LOGO_DIR / fname
    return path if path.is_file() else None
