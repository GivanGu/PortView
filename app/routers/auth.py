"""/api/auth/* 路由 —— 单用户密码登录 + 会话。

端点：
- POST /api/auth/set_password  首次设置 / 修改密码（已开启保护且已有密码时需有效会话）
- POST /api/auth/login         登录，成功则写 httpOnly cookie ``portview_session``
- POST /api/auth/logout        登出（删对应 token）
- GET  /api/auth/me            当前会话状态（含 ``auth_required`` 是否开启）
- PATCH /api/auth/toggle       切换 auth 强制开关（关闭时若已开启需有效会话）
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field

from app.models import APIResponse
from app.services import auth as auth_svc

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "portview_session"
COOKIE_MAX_AGE = auth_svc.SESSION_TTL_SECONDS


class SetPasswordPayload(BaseModel):
    password: str = Field(min_length=4, max_length=128)


class LoginPayload(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class TogglePayload(BaseModel):
    enabled: bool


@router.post("/set_password")
async def set_password(
    body: SetPasswordPayload,
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> APIResponse:
    has = await auth_svc.has_password()
    # 已开启登录保护且已有密码时，修改密码必须持有有效会话，
    # 否则攻击者可未授权重置密码 → 接管账户
    if (
        has
        and await auth_svc.is_auth_required()
        and not await auth_svc.is_valid_session(token or "")
    ):
        raise HTTPException(status_code=401, detail="login required")
    if has:
        # 已有密码 → 覆盖式修改（不强制旧密码，单用户工具）；update_password 内部会撤销全部旧会话
        await auth_svc.update_password(body.password)
    else:
        # 首次设置：无密码 → 直接写入
        await auth_svc.create_user_if_absent(password=body.password)
    return APIResponse(success=True, message="password updated")


@router.post("/login")
async def login(body: LoginPayload, response: Response) -> APIResponse:
    ok = await auth_svc.verify_user_password(body.password)
    if not ok:
        raise HTTPException(status_code=401, detail="wrong password")
    token = await auth_svc.issue_session()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # 本地 8081 通常是 http，不设 Secure
        max_age=COOKIE_MAX_AGE,
        path="/",
    )
    return APIResponse(success=True, message="ok")


@router.post("/logout")
async def logout(
    response: Response,
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> APIResponse:
    n = 0
    if token:
        n = await auth_svc.revoke_session(token)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return APIResponse(success=True, message=f"logged out ({n} session revoked)")


@router.get("/me")
async def me(
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> APIResponse:
    required = await auth_svc.is_auth_required()
    if not required:
        return APIResponse(
            success=True,
            data={
                "auth_required": False,
                "logged_in": True,
                "has_password": await auth_svc.has_password(),
            },
        )
    valid = await auth_svc.is_valid_session(token or "")
    return APIResponse(
        success=True,
        data={
            "auth_required": True,
            "logged_in": valid,
            "has_password": await auth_svc.has_password(),
        },
    )


@router.patch("/toggle")
async def toggle(
    body: TogglePayload,
    response: Response,
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> APIResponse:
    # 开启登录保护前必须先设置密码，否则开启后无人能登录
    if body.enabled and not await auth_svc.has_password():
        raise HTTPException(status_code=400, detail="set password first")
    # 关闭登录保护时，若当前已开启保护则必须持有有效会话，
    # 否则攻击者可未授权关闭保护 → 绕过全部鉴权
    if (
        not body.enabled
        and await auth_svc.is_auth_required()
        and not await auth_svc.is_valid_session(token or "")
    ):
        raise HTTPException(status_code=401, detail="login required")
    await auth_svc.set_auth_required(body.enabled)
    if not body.enabled:
        # 关闭时清 cookie，保持前端体验一致
        response.delete_cookie(key=COOKIE_NAME, path="/")
    return APIResponse(
        success=True,
        message=f"auth {'enabled' if body.enabled else 'disabled'}",
    )


# ---------------------- 依赖：需登录（可关闭） ----------------------


async def require_login(
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> bool:
    """FastAPI 异步依赖。``app.add_middleware`` 或路由 Depends 均可用；
    关闭 auth 时直接放行（True）；开启且未登录则抛 401。"""
    if not await auth_svc.is_auth_required():
        return True
    if await auth_svc.is_valid_session(token or ""):
        return True
    raise HTTPException(status_code=401, detail="login required")
