"""密码 + 会话 token（v1.2 新增）。

单用户本地工具，所以：
- ``users`` 表仅 1 行，用户名固定 ``admin``。
- ``sessions`` 表支持「多标签页并存 + 登出即删行」。
- 密码用 ``argon2id`` 哈希（``argon2-cffi``）。
- 关闭登录：``PORTVIEW_REQUIRE_AUTH=0`` env 或 ``user_prefs.require_auth=0``。

会话过期策略：7 天（滑动续期，每次请求把 ``last_seen_at`` 更新到当前，
若 ``expires_at < now`` 则视为过期）。
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.services import db as _db

logger = logging.getLogger(__name__)

# argon2id（默认）；memory 64MB / 1 迭代 / 4 线程，对本地工具足够安全
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
)

SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 天


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, stored: str) -> bool:
    if not stored or not plain:
        return False
    try:
        return _hasher.verify(stored, plain)
    except Argon2Error:
        return False


# --------------------- 密码管理 ---------------------

async def create_user_if_absent(username: str = "admin", password: str = "") -> bool:
    """若 ``users`` 表为空则写入第一行；若已有行则更新密码。返回 True 表示写入。"""
    db = _db.get_db()
    if db is None:
        return False
    now = int(time.time())
    if password:
        ph = hash_password(password)
    else:
        ph = ""
    await db.execute(
        "INSERT INTO users (id, username, password_hash, created_at, updated_at)"
        " VALUES (1, ?, ?, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET"
        "   username = excluded.username,"
        "   password_hash = CASE WHEN excluded.password_hash != '' THEN excluded.password_hash ELSE users.password_hash END,"
        "   updated_at = excluded.updated_at",
        (username, ph, now, now),
    )
    await db.commit()
    return True


async def update_password(password: str) -> None:
    db = _db.get_db()
    if db is None:
        return
    ph = hash_password(password)
    now = int(time.time())
    await db.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = 1",
        (ph, now),
    )
    await db.commit()
    # 登出所有旧会话
    await db.execute("DELETE FROM sessions")
    await db.commit()


async def has_password() -> bool:
    db = _db.get_db()
    if db is None:
        return False
    cur = await db.execute("SELECT password_hash FROM users WHERE id = 1")
    row = await cur.fetchone()
    return bool(row and row[0])


async def verify_user_password(plain: str) -> bool:
    db = _db.get_db()
    if db is None:
        return False
    cur = await db.execute("SELECT password_hash FROM users WHERE id = 1")
    row = await cur.fetchone()
    if not row or not row[0]:
        return False
    return verify_password(plain, row[0])


# --------------------- 会话管理 ---------------------

TOKEN_BYTES = 32  # → 64 字符 hex


def _new_token() -> str:
    return secrets.token_hex(TOKEN_BYTES)


async def issue_session() -> str:
    db = _db.get_db()
    if db is None:
        raise RuntimeError("db not initialized")
    token = _new_token()
    now = int(time.time())
    expires = now + SESSION_TTL_SECONDS
    await db.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at, last_seen_at)"
        " VALUES (?, 1, ?, ?, ?)",
        (token, now, expires, now),
    )
    await db.commit()
    logger.info("session issued (expires in %ds)", SESSION_TTL_SECONDS)
    return token


async def revoke_session(token: str) -> int:
    db = _db.get_db()
    if db is None:
        return 0
    cur = await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    await db.commit()
    return cur.rowcount or 0


async def revoke_all_sessions() -> int:
    db = _db.get_db()
    if db is None:
        return 0
    cur = await db.execute("DELETE FROM sessions")
    await db.commit()
    return cur.rowcount or 0


async def is_valid_session(token: str) -> bool:
    """True=有效且未过期；同时顺带刷新 ``last_seen_at``。"""
    if not token:
        return False
    db = _db.get_db()
    if db is None:
        return False
    now = int(time.time())
    cur = await db.execute(
        "SELECT expires_at FROM sessions WHERE token = ?", (token,)
    )
    row = await cur.fetchone()
    if row is None:
        return False
    if row[0] < now:
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()
        return False
    # 刷新 last_seen（不动 expires：TTL 固定从颁发开始算，简化理解）
    await db.execute(
        "UPDATE sessions SET last_seen_at = ? WHERE token = ?",
        (now, token),
    )
    await db.commit()
    return True


# --------------------- 关闭开关 ---------------------

async def is_auth_required() -> bool:
    """优先级：env > user_prefs 行。

    env=0 → 强制关；env=1 → 强制开；未设 → 读 user_prefs。
    """
    env = os.environ.get("PORTVIEW_REQUIRE_AUTH")
    if env is not None:
        return env.strip() not in ("0", "false", "off", "")
    db = _db.get_db()
    if db is None:
        return False
    cur = await db.execute("SELECT require_auth FROM user_prefs WHERE id = 1")
    row = await cur.fetchone()
    if row is None:
        return False
    return bool(row[0])


async def set_auth_required(enabled: bool) -> None:
    db = _db.get_db()
    if db is None:
        return
    await db.execute(
        "UPDATE user_prefs SET require_auth = ?, updated_at = ? WHERE id = 1",
        (1 if enabled else 0, int(time.time())),
    )
    await db.commit()


# 惰性 import os（避免循环依赖；db 里已经 import 过）
import os  # noqa: E402


__all__: list[str] = [
    "hash_password",
    "verify_password",
    "create_user_if_absent",
    "update_password",
    "has_password",
    "verify_user_password",
    "issue_session",
    "revoke_session",
    "revoke_all_sessions",
    "is_valid_session",
    "is_auth_required",
    "set_auth_required",
    "SESSION_TTL_SECONDS",
]
