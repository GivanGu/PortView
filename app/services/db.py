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
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".data",
        "portview.db",
    ),
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
    "  refresh_interval INTEGER NOT NULL DEFAULT 0,"
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
    # 应用 Logo（v1.5.0）：按 app_key 共享，三态（found / not_found），
    # BLOB 存图片字节，随 portview-data 卷备份。
    "CREATE TABLE IF NOT EXISTS service_logos ("
    "  app_key    TEXT PRIMARY KEY,"
    "  status     TEXT NOT NULL DEFAULT 'found' CHECK (status IN ('found', 'not_found')),"
    "  mime       TEXT,"
    "  data       BLOB,"
    "  created_at INTEGER NOT NULL DEFAULT 0,"
    "  updated_at INTEGER NOT NULL DEFAULT 0"
    ")",
    # 人工指定的服务协议（v1.5.21）：探测不准时用户手动指定 http/https，
    # 优先级高于自动探测。1 个端口 ≤ 1 行，删行 = 恢复自动检测。
    "CREATE TABLE IF NOT EXISTS port_schemes ("
    "  port       INTEGER PRIMARY KEY CHECK (port BETWEEN 0 AND 65535),"
    "  scheme     TEXT NOT NULL CHECK (scheme IN ('http', 'https')),"
    "  updated_at INTEGER NOT NULL DEFAULT 0"
    ")",
    # 自定义背景图（v1.6.6）：单行 id=1，BLOB 存图片字节。
    # 不进 user_prefs——prefs 每次全量读取，4MiB 图片会拖垮 GET /api/prefs。
    "CREATE TABLE IF NOT EXISTS backgrounds ("
    "  id         INTEGER PRIMARY KEY CHECK (id = 1),"
    "  mime       TEXT NOT NULL,"
    "  data       BLOB NOT NULL,"
    "  updated_at INTEGER NOT NULL DEFAULT 0"
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

    # P1.1 迁移：user_prefs 加 require_auth 列（0=关闭登录，1=开启，默认 0 以不破坏现有部署）
    cur = await conn.execute("PRAGMA table_info(user_prefs)")
    pref_cols = {row[1] for row in await cur.fetchall()}
    if "require_auth" not in pref_cols:
        await conn.execute(
            "ALTER TABLE user_prefs ADD COLUMN require_auth INTEGER NOT NULL DEFAULT 0"
        )
        # 若 PORTVIEW_REQUIRE_AUTH=1 显式要求登录，则初始化时打开
        if os.environ.get("PORTVIEW_REQUIRE_AUTH", "0") == "1":
            await conn.execute("UPDATE user_prefs SET require_auth = 1 WHERE id = 1")
            logger.info("migration: user_prefs.require_auth = 1")
        else:
            logger.info("migration: user_prefs.require_auth added (default 0 = off)")

    # P1.2 迁移：user_prefs 加 refresh_interval 列（0=手动，10/15/30=自动刷新秒数）
    cur = await conn.execute("PRAGMA table_info(user_prefs)")
    pref_cols2 = {row[1] for row in await cur.fetchall()}
    if "refresh_interval" not in pref_cols2:
        await conn.execute(
            "ALTER TABLE user_prefs ADD COLUMN refresh_interval INTEGER NOT NULL DEFAULT 0"
        )
        logger.info("migration: user_prefs.refresh_interval added (default 0 = manual)")

    # v1.5.2 迁移：user_prefs 加 logo_scrim 列（卡片 Logo 背景的可读性遮罩档位）。
    # 取值 none / left / overlay / glass，默认 left（左侧渐变，信息类卡片最协调）。
    cur = await conn.execute("PRAGMA table_info(user_prefs)")
    pref_cols3 = {row[1] for row in await cur.fetchall()}
    if "logo_scrim" not in pref_cols3:
        await conn.execute(
            "ALTER TABLE user_prefs ADD COLUMN logo_scrim TEXT NOT NULL DEFAULT 'left'"
        )
        logger.info("migration: user_prefs.logo_scrim added (default 'left')")

    # v1.5.11 迁移：user_prefs 加 logo_display_mode 列（卡片 Logo 展示模式）。
    # 取值 background（Logo 铺满整卡作背景）/ box（64px Logo 框 + 信息列），默认 background。
    # logo_scrim 仅在 background 模式下生效。
    cur = await conn.execute("PRAGMA table_info(user_prefs)")
    pref_cols4 = {row[1] for row in await cur.fetchall()}
    if "logo_display_mode" not in pref_cols4:
        await conn.execute(
            "ALTER TABLE user_prefs ADD COLUMN logo_display_mode TEXT NOT NULL DEFAULT 'background'"
        )
        logger.info("migration: user_prefs.logo_display_mode added (default 'background')")

    # v1.5.0 迁移：新增 service_logos 表（应用 Logo 持久化）。
    # 表由上方 _SCHEMA 的 CREATE TABLE IF NOT EXISTS 幂等创建；
    # 这里仅对「老库」bump schema_version 以追踪迁移（新库首次种入即为 1，随后升到 2）。
    cur = await conn.execute("SELECT version FROM schema_version WHERE id = 1")
    row = await cur.fetchone()
    if row is not None and row["version"] < 2:
        await conn.execute(
            "UPDATE schema_version SET version = 2, applied_at = ?, note = note || ? WHERE id = 1",
            (int(time.time()), " v1.5.0 service_logos"),
        )
        logger.info("migration: schema_version -> 2 (service_logos)")

    # v1.5.21 迁移：新增 port_schemes 表（人工指定端口协议）。
    # 表由上方 _SCHEMA 幂等创建；老库 bump schema_version 追踪迁移。
    cur = await conn.execute("SELECT version FROM schema_version WHERE id = 1")
    row = await cur.fetchone()
    if row is not None and row["version"] < 3:
        await conn.execute(
            "UPDATE schema_version SET version = 3, applied_at = ?, note = note || ? WHERE id = 1",
            (int(time.time()), " v1.5.21 port_schemes"),
        )
        logger.info("migration: schema_version -> 3 (port_schemes)")

    # v1.5.5 迁移：user_prefs 加 favorites 列（收藏端口号 JSON 数组，顺序 = 展示顺序）。
    # 无新表，沿用列迁移模式，不 bump schema_version。
    cur = await conn.execute("PRAGMA table_info(user_prefs)")
    pref_cols5 = {row[1] for row in await cur.fetchall()}
    if "favorites" not in pref_cols5:
        await conn.execute("ALTER TABLE user_prefs ADD COLUMN favorites TEXT NOT NULL DEFAULT '[]'")
        logger.info("migration: user_prefs.favorites added (default '[]')")

    # v1.6.6 迁移：user_prefs 加 default_tab 列（默认主页：overview / favorites）。
    # 默认 favorites 保持 v1.6.5 现状（收藏页为默认首页）。
    cur = await conn.execute("PRAGMA table_info(user_prefs)")
    pref_cols6 = {row[1] for row in await cur.fetchall()}
    if "default_tab" not in pref_cols6:
        await conn.execute(
            "ALTER TABLE user_prefs ADD COLUMN default_tab TEXT NOT NULL DEFAULT 'favorites'"
        )
        logger.info("migration: user_prefs.default_tab added (default 'favorites')")

    # v1.6.6 迁移：user_prefs 加 background_scope 列（背景图作用域：favorites / all）。
    cur = await conn.execute("PRAGMA table_info(user_prefs)")
    pref_cols7 = {row[1] for row in await cur.fetchall()}
    if "background_scope" not in pref_cols7:
        await conn.execute(
            "ALTER TABLE user_prefs ADD COLUMN background_scope TEXT NOT NULL DEFAULT 'favorites'"
        )
        logger.info("migration: user_prefs.background_scope added (default 'favorites')")

    # v1.6.6 迁移：user_prefs 加 background_blur 列（背景图模糊度 px，0-30，默认 10）。
    cur = await conn.execute("PRAGMA table_info(user_prefs)")
    pref_cols8 = {row[1] for row in await cur.fetchall()}
    if "background_blur" not in pref_cols8:
        await conn.execute(
            "ALTER TABLE user_prefs ADD COLUMN background_blur INTEGER NOT NULL DEFAULT 10"
        )
        logger.info("migration: user_prefs.background_blur added (default 10)")

    # v1.6.9 迁移：清空 port_notes 表（一次性，schema_version < 4 时执行）。
    # 旧「未备注端口」命名流程产生的备注已废弃 —— 备注的 service_name 从不应用到
    # 端口卡片（只有 remark 会），服务名统一改走 config.json 的「编辑服务名」。
    cur = await conn.execute("SELECT version FROM schema_version WHERE id = 1")
    row = await cur.fetchone()
    if row is not None and row["version"] < 4:
        await conn.execute("DELETE FROM port_notes")
        await conn.execute(
            "UPDATE schema_version SET version = 4, applied_at = ?, note = note || ? WHERE id = 1",
            (int(time.time()), " v1.6.9 clear port_notes"),
        )
        logger.info("migration: schema_version -> 4 (clear port_notes)")

    # v1.6.11 迁移：删除 port_notes 表（备注功能整体移除，schema_version < 5 时执行）。
    # 备注页、卡片 remark 展示、收藏页备注编辑、隐藏端口 remark 均已一并拆除。
    # DDL 保留 CREATE TABLE：新库建表后由本迁移 DROP，保证 v1.6.9 历史迁移在新库可执行。
    cur = await conn.execute("SELECT version FROM schema_version WHERE id = 1")
    row = await cur.fetchone()
    if row is not None and row["version"] < 5:
        await conn.execute("DROP TABLE IF EXISTS port_notes")
        await conn.execute(
            "UPDATE schema_version SET version = 5, applied_at = ?, note = note || ? WHERE id = 1",
            (int(time.time()), " v1.6.11 drop port_notes"),
        )
        logger.info("migration: schema_version -> 5 (drop port_notes)")

    await conn.commit()
    if _db is not None:
        await _db.close()
    _db = conn
    logger.info("SQLite @ %s (WAL, 9 tables) ready", path)
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
        "UPDATE schema_version SET version = MAX(version, ?), applied_at = ?, note = note || ? WHERE id = 1",
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
