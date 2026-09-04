"""认证路由 — 单用户+密码模式。

首次运行初始化默认密码 ``portview123``（用户可在首次登录后修改），
密码哈希存储在 SQLite：``/app/config/users.db``。

使用 JWT (python-jose) 实现 Token 认证。
前端在 localStorage 保存 Token，每次请求带 ``Authorization: Bearer <token>``。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.utils.errors import ErrorCodes, make_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# JWT 配置
_SECRET_KEY = os.environ.get("PORTVIEW_JWT_SECRET", "portview-jwt-secret-change-me")
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天

_bearer = HTTPBearer(auto_error=False)

# SQLite 数据库 — 使用 CONFIG_DIR 以便测试覆盖
_CONFIG_DIR = os.environ.get("PORTVIEW_CONFIG_DIR", "/app/config")
_DB_PATH = os.path.join(_CONFIG_DIR, "users.db")


def init_db() -> None:
    """初始化 SQLite 数据库 + 默认用户（调用于 lifespan）。"""
    import sqlite3

    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # 创建默认用户（如果不存在）
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", ("admin",)
    ).fetchone()
    if not existing:
        import bcrypt

        default_password = os.environ.get(
            "PORTVIEW_DEFAULT_PASSWORD", "portview123"
        )
        pw_hash = bcrypt.hashpw(
            default_password.encode(), bcrypt.gensalt()
        )
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            ("admin", pw_hash.decode(), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logger.info("默认用户 'admin' 创建成功，初始密码: %s", default_password)
    conn.close()


def _verify_password(stored_hash: str, password: str) -> bool:
    """校验密码。"""
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        return False


def _create_token(username: str) -> str:
    """生成 JWT。"""
    from jose import jwt

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode = {
        "sub": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(to_encode, _SECRET_KEY, algorithm=_ALGORITHM)


def _decode_token(token: str) -> str:
    """解析 JWT，返回用户名。失败抛出 make_error。"""
    from jose import jwt, JWTError

    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise make_error(ErrorCodes.AUTH_FAILED, "Token 解析失败")
        return username
    except JWTError:
        raise make_error(ErrorCodes.AUTH_FAILED, "Token 无效或过期")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI 依赖 — 获取当前用户。"""
    if not credentials:
        raise make_error(ErrorCodes.AUTH_REQUIRED, "请先登录")
    return _decode_token(credentials.credentials)


# ────────────────────────────────────────────────────────────── #
# 请求/响应模型
# ────────────────────────────────────────────────────────────── #
from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ────────────────────────────────────────────────────────────── #
# 路由
# ────────────────────────────────────────────────────────────── #
# DB init 由 lifespan 调用，避免 on_event 弃用警告


@router.post("/login", response_model=dict)
def login(req: LoginRequest):
    """Login endpoint. Request: {'password': 'xxx'}. Returns JWT token."""
    import sqlite3

    conn = sqlite3.connect(_DB_PATH)
    row = conn.execute(
        "SELECT username, password_hash FROM users WHERE username = 'admin'"
    ).fetchone()
    conn.close()

    if not row or not _verify_password(row[1], req.password):
        raise make_error(ErrorCodes.AUTH_FAILED, "密码错误")

    token = _create_token(row[0])
    return {
        "success": True,
        "data": {
            "token": token,
            "user": {"username": row[0]},
        },
    }


@router.post("/logout")
def logout():
    """Frontend deletes localStorage 即可. No backend token revocation needed."""
    return {"success": True, "message": "登出成功"}


@router.get("/me", response_model=dict)
def me(current_user: str = Depends(get_current_user)):
    """获取当前用户信息。"""
    return {"success": True, "data": {"username": current_user}}


@router.post("/change-password", response_model=dict)
def change_password(
    req: ChangePasswordRequest,
    current_user: str = Depends(get_current_user),
):
    """修改密码。"""
    import sqlite3
    import bcrypt

    conn = sqlite3.connect(_DB_PATH)
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ?", (current_user,)
    ).fetchone()
    if not row or not _verify_password(row[0], req.old_password):
        conn.close()
        raise make_error(ErrorCodes.AUTH_FAILED, "原密码错误")

    new_hash = bcrypt.hashpw(
        req.new_password.encode(), bcrypt.gensalt()
    )
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (new_hash.decode(), current_user),
    )
    conn.commit()
    conn.close()
    logger.info("用户 %s 修改密码成功", current_user)
    return {"success": True, "message": "密码修改成功"}
