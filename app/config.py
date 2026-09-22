"""配置读写（v1.6.12 统一存储：全部落 SQLite）。

- 端口标注：``port_labels`` 表（端口主键，服务名非唯一，同一名字可绑多端口）
- 全局访问地址：``user_prefs.access_address`` 列
- 隐藏端口：``hidden_ports`` 表

旧 ``config.json`` / ``hidden_ports.json`` 文件已由 :mod:`app.services.migrate`
在启动时迁入 DB 并删除，文件读写函数不再存在。
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from app.services import db as db_service

logger = logging.getLogger(__name__)


def normalize_access_address(address: str) -> str:
    """规范化访问地址：只保留主机部分（IP/域名），剥离协议前缀与端口。

    例如 ``http://192.168.31.1:8081`` → ``192.168.31.1``；
    ``192.168.31.1:8081``（旧数据手填 IP:端口）→ ``192.168.31.1``。
    http/https 不再随地址存储，由打开服务时的实时探测决定。
    """
    address = address.strip()
    if not address:
        return ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", address):
        # 无协议前缀（裸 IP / 域名 / IP:端口）：统一补 http:// 再按 URL 解析，
        # 保证端口号被剥离（否则 "IP:8081" 会被当作主机名导致探测全部失败）
        address = f"http://{address}"
    return urlparse(address).hostname or ""


async def load_config() -> dict[int, dict[str, str]]:
    """加载全部端口标注。

    返回形如 ``{port: {"service_name": str, "port_type": "docker"|"host"}}``。
    DB 未就绪时返回空字典。
    """
    conn = db_service.get_db()
    if conn is None:
        return {}
    try:
        cur = await conn.execute("SELECT port, service_name, port_type FROM port_labels")
        rows = await cur.fetchall()
        return {row[0]: {"service_name": row[1], "port_type": row[2]} for row in rows}
    except Exception as e:
        logger.warning("加载端口标注失败: %s", e)
        return {}


async def load_access_address() -> str:
    """读取全局访问地址（主机部分，如 192.168.31.1）。未设置时返回空字符串。"""
    conn = db_service.get_db()
    if conn is None:
        return ""
    try:
        cur = await conn.execute("SELECT access_address FROM user_prefs WHERE id = 1")
        row = await cur.fetchone()
        if row is None:
            return ""
        return normalize_access_address(row[0] or "")
    except Exception as e:
        logger.warning("读取访问地址失败: %s", e)
        return ""


async def load_access_host() -> str:
    """读取访问地址的主机部分（供协议探测连接使用）。未设置时返回空字符串。

    与 :func:`load_access_address` 等价（地址现在只存主机），
    单独抽出便于调用方表达意图。
    """
    return await load_access_address()


async def save_access_address(address: str) -> bool:
    """保存全局访问地址。空字符串表示清除。

    自动剥离协议前缀，只落盘主机部分（IP/域名）。
    """
    conn = db_service.get_db()
    if conn is None:
        return False
    try:
        address = normalize_access_address(address)
        await conn.execute("UPDATE user_prefs SET access_address = ? WHERE id = 1", (address,))
        await conn.commit()
        return True
    except Exception as e:
        logger.error("保存访问地址失败: %s", e)
        return False


async def load_hidden_ports() -> list[int]:
    """加载隐藏端口列表（升序）。"""
    conn = db_service.get_db()
    if conn is None:
        return []
    try:
        cur = await conn.execute("SELECT port FROM hidden_ports ORDER BY port")
        rows = await cur.fetchall()
        return [row[0] for row in rows]
    except Exception as e:
        logger.warning("加载隐藏端口失败: %s", e)
        return []


async def save_hidden_ports(hidden_ports: list[int]) -> bool:
    """全量保存隐藏端口列表。"""
    conn = db_service.get_db()
    if conn is None:
        return False
    try:
        await conn.execute("DELETE FROM hidden_ports")
        for port in hidden_ports:
            await conn.execute("INSERT OR IGNORE INTO hidden_ports (port) VALUES (?)", (port,))
        await conn.commit()
        return True
    except Exception as e:
        logger.error("保存隐藏端口失败: %s", e)
        return False
