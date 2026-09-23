"""v1.6.12 统一存储迁移（幂等，lifespan 中执行一次）。

数据源与去向：

1. 旧 DB ``<project>/.data/portview.db`` → ``<config_dir>/portview.db``
   （复制 → PRAGMA integrity_check → 原子落位 → 删除旧库）
2. ``config.json`` → ``port_labels`` 表 + ``user_prefs.access_address`` → 删除文件
3. ``hidden_ports.json`` → ``hidden_ports`` 表 → 删除文件

源不存在则跳过；目标已存在视为已迁移。任何一步失败都抛异常且保留源文件。
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import time
from typing import Any

from app.services import db as db_service

logger = logging.getLogger(__name__)

# 旧 config.json 中全局访问地址的保留键
ACCESS_ADDRESS_KEY = "__access_address__"


def relocate_db(old_path: str, new_path: str) -> bool:
    """把旧 DB 搬到新路径。返回是否实际执行了搬家。

    - 新路径已存在 → 跳过（已迁移）
    - 旧路径不存在 → 跳过（全新安装）
    - 搬家时连 ``-wal`` 副文件一起复制（可能含未 checkpoint 的数据），
      在 tmp 副本上跑 integrity_check，验证通过才原子落位；
      验证失败抛异常且不动旧库。
    """
    if os.path.exists(new_path):
        return False
    if not os.path.exists(old_path):
        # 清理上次崩溃遗留的 tmp
        _remove_quietly(new_path + ".tmp")
        _remove_quietly(new_path + ".tmp-wal")
        return False

    tmp = new_path + ".tmp"
    shutil.copy2(old_path, tmp)
    old_wal = old_path + "-wal"
    if os.path.exists(old_wal):
        shutil.copy2(old_wal, tmp + "-wal")

    # 打开 tmp 副本（会重放 wal）并校验完整性。
    # 损坏文件可能让 integrity_check 抛 DatabaseError 而非返回错误串，需捕获。
    conn = sqlite3.connect(tmp)
    try:
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            integrity = row[0] if row else "unknown"
        except sqlite3.DatabaseError as e:
            integrity = f"error: {e}"
    finally:
        conn.close()
    if integrity != "ok":
        _remove_quietly(tmp)
        _remove_quietly(tmp + "-wal")
        raise RuntimeError(f"旧库完整性校验失败（{integrity}）: {old_path}")

    os.replace(tmp, new_path)
    logger.info("DB 已搬家: %s -> %s", old_path, new_path)

    # 删除旧库（含 WAL/SHM），避免两份库并存让人分不清哪份权威
    for suffix in ("", "-wal", "-shm"):
        _remove_quietly(old_path + suffix)
    return True


def _remove_quietly(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as e:
        logger.warning("删除 %s 失败: %s", path, e)


def _parse_legacy_entry(key: Any, value: Any) -> tuple[str, str, int | None]:
    """解析旧 config.json 单条记录，返回 (service_name, port_type, port)。

    兼容三种格式：
    - 新格式：``"服务名:docker|host" -> "端口:协议"``
    - 旧格式：``"服务名" -> "端口:协议"``
    - 遗留 int：``"服务名" -> 端口号``

    无法识别时 port 返回 None（调用方记日志跳过）。
    """
    if not isinstance(key, str):
        return (str(key), "host", None)
    if isinstance(value, bool):
        return (key, "host", None)
    if isinstance(value, int):
        return (key, "host", value if 1 <= value <= 65535 else None)
    if not isinstance(value, str):
        return (key, "host", None)
    parts = value.split(":")
    try:
        port = int(parts[0])
    except (ValueError, IndexError):
        return (key, "host", None)
    if not 1 <= port <= 65535:
        return (key, "host", None)
    if key.endswith(":docker") or key.endswith(":host"):
        name, ptype = key.rsplit(":", 1)
        return (name, ptype, port)
    return (key, "host", port)


async def migrate_json_files(config_dir: str, db: Any) -> None:
    """把 config.json / hidden_ports.json 迁入 DB 并删除源文件。

    顺序：读取 → 写入 → 回读校验 → 删除源文件。
    任何一步失败抛异常，源文件保留（可下次启动重试）。
    """
    config_file = os.path.join(config_dir, "config.json")
    hidden_file = os.path.join(config_dir, "hidden_ports.json")
    if not os.path.exists(config_file) and not os.path.exists(hidden_file):
        return

    labels: dict[int, tuple[str, str]] = {}
    access_address = ""
    # PortView 自身监听端口走统一逻辑（默认映射 8081 → PortView），
    # 旧 config.json 里的自身端口条目是陈旧默认值（如 "模式注册:host"），跳过以免重新污染标注。
    try:
        self_port = int(os.environ.get("PORTVIEW_PORT", "8081"))
    except ValueError:
        self_port = 8081
    if os.path.exists(config_file):
        with open(config_file, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise RuntimeError(f"config.json 格式异常（应为对象）: {config_file}")
        for key, value in raw.items():
            if key == ACCESS_ADDRESS_KEY:
                access_address = value if isinstance(value, str) else ""
                continue
            name, ptype, port = _parse_legacy_entry(key, value)
            if port is None:
                logger.warning("跳过无法识别的配置项: %s=%r", key, value)
                continue
            if port == self_port:
                logger.info("跳过 PortView 自身端口条目（统一逻辑处理）: %s=%r", key, value)
                continue
            if port in labels:
                logger.warning(
                    "端口 %s 在旧配置中被多个名字绑定（%s 与 %s），保留后者",
                    port,
                    labels[port][0],
                    name,
                )
            labels[port] = (name, ptype)

    hidden: list[int] = []
    if os.path.exists(hidden_file):
        with open(hidden_file, encoding="utf-8") as f:
            raw_hidden = json.load(f)
        if isinstance(raw_hidden, list):
            hidden = [p for p in raw_hidden if isinstance(p, int) and 1 <= p <= 65535]

    now = int(time.time())
    for port, (name, ptype) in sorted(labels.items()):
        await db.execute(
            "INSERT INTO port_labels (port, service_name, port_type, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(port) DO UPDATE SET "
            "service_name = excluded.service_name, "
            "port_type = excluded.port_type, "
            "updated_at = excluded.updated_at",
            (port, name, ptype, now, now),
        )
    if access_address:
        await db.execute("UPDATE user_prefs SET access_address = ? WHERE id = 1", (access_address,))
    for port in hidden:
        await db.execute("INSERT OR IGNORE INTO hidden_ports (port) VALUES (?)", (port,))
    await db.commit()

    # 回读校验（DB 中可能已有更多行，只校验下限）
    cur = await db.execute("SELECT COUNT(*) FROM port_labels")
    row = await cur.fetchone()
    db_labels = row[0] if row else 0
    if db_labels < len(labels):
        raise RuntimeError(f"port_labels 校验失败: 期望 >= {len(labels)}，实际 {db_labels}")
    cur = await db.execute("SELECT COUNT(*) FROM hidden_ports")
    row = await cur.fetchone()
    db_hidden = row[0] if row else 0
    if db_hidden < len(hidden):
        raise RuntimeError(f"hidden_ports 校验失败: 期望 >= {len(hidden)}，实际 {db_hidden}")

    # 校验通过，删除源文件（数据已在 DB 中）
    for path in (config_file, hidden_file):
        if os.path.exists(path):
            os.remove(path)
            logger.info("已删除迁移源文件: %s", path)
    logger.info(
        "JSON 迁移完成: port_labels %d 条, hidden_ports %d 条, access_address=%s",
        len(labels),
        len(hidden),
        access_address or "(空)",
    )


def relocate_legacy_db() -> None:
    """旧库搬家入口（lifespan 中 init_db 之前调用）。

    仅当未用 PORTVIEW_DB 显式指定路径时执行——显式指定视为用户自管位置，
    测试环境正是靠这个约定隔离真实本地库。
    """
    if os.environ.get("PORTVIEW_DB"):
        return
    relocate_db(db_service._OLD_DB_PATH, db_service._DB_PATH)


async def run_migrations() -> None:
    """v1.6.12 统一存储迁移入口（lifespan 中调用）。

    1. 旧库搬家（须在 init_db 之前，见 :func:`relocate_legacy_db`）
    2. JSON 文件迁移（init_db 之后，源不存在则跳过）
    """
    relocate_legacy_db()
    conn = db_service.get_db()
    if conn is not None:
        await migrate_json_files(db_service._DATA_DIR, conn)
