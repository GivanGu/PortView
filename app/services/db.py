"""SQLAlchemy 异步数据库会话。

P0 收尾 0.7：引入 SQLite 作为持久化后端。

模块职责：
1. 初始化 asyncio aiosqlite 连接（单连接 + 串行执行，避免 ``CHECK SAME THREAD``）
2. 提供 `init_db()` / `close_db()` 用于 FastAPI lifespan
3. 提供 `get_db()` 作为 Depends 注入点
4. DDL：5 张表 —— schema_version / port_notes / accent / range_rules / audit_log

表设计原则：
- `accent` 当前仅 1 行，用 INTEGER PRIMARY KEY 1；为将来多主题保留扩展
- `range_rules`：用户自定义监控区间（start_port / end_port / 备注名），无行数上限
- `audit_log`：轻量审计（login / hide / unhide / edit），可后裁剪
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

logger = logging.getLogger(__name__)

# 数据库文件：`<project>/.data/portview.db`（可由 PORTVIEW_DB 环境变量覆盖）
_DB_PATH = os.environ.get(
    "PORTVIEW_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 ".data", "portview.db"),
)

# 连接引用 —— FastAPI 单例
_db: aiosqlite.Connection | None = None

# 表 DDL（顺序敏感：schema_version 必须第一张，便于迁移判定）
_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS schema_version ("
    "  id INTEGER PRIMARY KEY CHECK (id = 1),"
    "  version INTEGER NOT NULL DEFAULT 1,"
    "  applied_at INTEGER NOT NULL DEFAULT 0,"
    "  note TEXT NOT NULL DEFAULT ''"
    ")",

    # 端口备注：用户可为任意端口附加备注（1 个端口 ≤ 1 行）
    "CREATE TABLE IF NOT EXISTS port_notes ("
    "  port INTEGER PRIMARY KEY,"  # 0-65535 或自定义
    "  service_name TEXT NOT NULL DEFAULT '',"
    "  protocol TEXT NOT NULL DEFAULT '' CHECK (protocol IN ('', 'tcp', 'udp','both')),"
    "  created_at INTEGER NOT NULL DEFAULT 0,"
    "  updated_at INTEGER NOT NULL DEFAULT 0"
    ")",

    # 强调色 + 主题：1 行持久化用户偏好
    "CREATE TABLE IF NOT EXISTS user_prefs ("
    "  id INTEGER PRIMARY KEY CHECK (id = 1),"
    "  theme TEXT NOT NULL DEFAULT 'dark',"
    "  accent TEXT NOT NULL DEFAULT 'indigo',"
    "  lang TEXT NOT NULL DEFAULT 'zh',"
    "  updated_at INTEGER NOT NULL DEFAULT 0"
    ")",

    # 自定义监控区间：无行数上限
    "CREATE TABLE IF NOT EXISTS range_rules ("
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "  name TEXT NOT NULL,"
    "  start_port INTEGER NOT NULL CHECK (start_port BETWEEN 0 AND 65535),"
    "  end_port INTEGER NOT NULL CHECK (end_port BETWEEN 0 AND 65535),"
    "  created_at INTEGER NOT NULL DEFAULT 0,"
    "  UNIQUE(name)"
    ")",

    # 审计 log（轻量；可后期删除或归档）
    "CREATE TABLE IF NOT EXISTS audit_log ("
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "  actor TEXT NOT NULL DEFAULT 'system',"
    "  action TEXT NOT NULL,"
    "  payload TEXT NOT NULL DEFAULT '{}',"
    "  created_at INTEGER NOT NULL DEFAULT 0"
    ")",

    # 单行用户表：portview 是单用户本地工具，只存一条
    # P1 阶段允许关闭 auth（env PORTVIEW_REQUIRE_AUTH=0 或 user_prefs.require_auth=0），
    # 若开启则用户第一次调用 POST /api/auth/set_password 初始化，之后 POST /api/auth/login 拿到 token
    "CREATE TABLE IF NOT EXISTS users ("
    "  id INTEGER PRIMARY KEY CHECK (id = 1),"
    "  username TEXT NOT NULL DEFAULT 'admin',"
    "  password_hash TEXT NOT NULL,"
    "  created_at INTEGER NOT NULL DEFAULT 0,"
    "  updated_at INTEGER NOT NULL DEFAULT 0"
    ")",

    # 会话 token（支持「登出」= 删行；多标签页并存 = 多行）
    "CREATE TABLE IF NOT EXISTS sessions ("
    "  token TEXT PRIMARY KEY,"
    "  user_id INTEGER NOT NULL REFERENCES users(id),"
    "  created_at INTEGER NOT NULL DEFAULT 0,"
    "  expires_at INTEGER NOT NULL DEFAULT 0,"
    "  last_seen_at INTEGER NOT NULL DEFAULT 0"
    ")",
]


@asynccontextmanager
async def init_db(path: str = _DB_PATH) -> AsyncIterator[aiosqlite.Connection]:
    """打开 aiosqlite 连接、建表、设置 PRAGMA，并暴露为模块级单例。

    用法::

        async with init_db() as db:
            await db.execute("SELECT 1")
    """
    global _db
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")

    # 依次执行 DDL（IF NOT EXISTS 幂等）
    for ddl in _SCHEMA:
        await conn.execute(ddl)

    # 首次启动种入 schema_version 行
    cur = await conn.execute("SELECT version FROM schema_version WHERE id = 1")
    if await cur.fetchone() is None:
        await conn.execute(
            "INSERT INTO schema_version (id, version, applied_at, note) VALUES (1, 1, ?, 'P0 initial')",
            (int(time.time()),),
        )

    # 首次启动种入 user_prefs 单行
    cur = await conn.execute("SELECT id FROM user_prefs WHERE id = 1")
    if await cur.fetchone() is None:
        await conn.execute(
            "INSERT INTO user_prefs (id, theme, accent, lang, updated_at) VALUES (1, 'dark', 'indigo', 'zh', 0)"
        )

    # P1 迁移：port_notes 表在 0.7 阶段定义时未含 `remark` 自由文本列，
    # 在此做幂等补列（老库也安全），避免旧库访问 /api/notes 时报 `no such column: remark`。
    cur = await conn.execute("PRAGMA table_info(port_notes)")
    cols = {row[1] for row in await cur.fetchall()}
    if "remark" not in cols:
        await conn.execute("ALTER TABLE port_notes ADD COLUMN remark TEXT NOT NULL DEFAULT ''")
        logger.info("migration: port_notes.remark added")

    # P1.1 迁移：user_prefs 加 require_auth 列（0=关闭登录，1=开启，默认 0 以不破坏现有部署）
    cur = await conn.execute("PRAGMA table_info(user_prefs)")
    pref_cols = {row[1] for row in await cur.fetchall()}
    if "require_auth" not in pref_cols:
        await conn.execute("ALTER TABLE user_prefs ADD COLUMN require_auth INTEGER NOT NULL DEFAULT 0")
        # 若 PORTVIEW_REQUIRE_AUTH=1 显式要求登录，则初始化时打开
        if os.environ.get("PORTVIEW_REQUIRE_AUTH", "0") == "1":
            await conn.execute("UPDATE user_prefs SET require_auth = 1 WHERE id = 1")
            logger.info("migration: user_prefs.require_auth = 1")
        else:
            logger.info("migration: user_prefs.require_auth added (default 0 = off)")

    await conn.commit()
    if _db is not None:
        await _db.close()
    _db = conn
    logger.info("SQLite @ %s (WAL, 5 tables) ready", path)
    yield conn
    await conn.close()
    logger.info("SQLite @ %s closed", path)


def get_db() -> aiosqlite.Connection | None:
    """Depends 注入点。返回 None 表示尚未初始化。"""
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# ----------------------- 便捷 helper -----------------------

async def ensure_schema_version_bump(version: int, note: str) -> None:
    """bump schema_version（用于迁移追踪）。"""
    if _db is None:
        return
    await _db.execute(
        "UPDATE schema_version SET version = MAX(version, ?), applied_at = ?, note || ? WHERE id = 1",
        (version, int(time.time()), " " + note),
    )
    await _db.commit()


# re-export for tests / callers
__all__ = [
    "_DB_PATH",
    "_db",
    "close_db",
    "ensure_schema_version_bump",
    "get_db",
    "init_db",
]
