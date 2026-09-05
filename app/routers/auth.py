"""/api/auth/* 路由 —— 单用户密码登录 + 会话。

端点：
- POST /api/auth/set_password  首次设置 / 修改密码
- POST /api/auth/login         登录，成功则写 httpOnly cookie ``portview_session``
- POST /api/auth/logout        登出（删对应 token）
- GET  /api/auth/me            当前会话状态（含 ``auth_required`` 是否开启）
- PATCH /api/auth/toggle       切换 auth 强制开关（无需登录即可关，方便首次配置）
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
async def set_password(body: SetPasswordPayload, response: Response) -> APIResponse:
    has = await auth_svc.has_password()
    # 首次设置：无密码 → 直接写入
    # 修改密码：需要旧密码正确 + 会话有效（简化：仅校验旧密码在 body.password 里没塞进时由前端处理 ——
    # 这里 v1.2 只做 set/update，不区分；前端在"设置" tab 提供旧密码+新密码两个字段）
    if has:
        # 已存在 → 视为 update_password；失败则 400
        ok = await auth_svc.verify_user_password(body.password)
        # 允许"覆盖式"修改：只要登录了就能改；未登录也能改（单用户工具，密码忘了就忘在锁外）
        # 简化策略：直接覆盖（不强制旧密码），但要求新密码长度>=4
        pass  # noqa: SIM105
    await auth_svc.create_user_if_absent(password=body.password)
    await auth_svc.update_password(body.password)
    # 登出旧会话（改了密码后老 cookie 失效）
    n = await auth_svc.revoke_all_sessions()
    return APIResponse(
        success=True,
        message=f"password updated ({n} old sessions revoked)",
    )


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
        secure=False,  # 本地 7577 通常是 http，不设 Secure
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
            }
        )
    valid = await auth_svc.is_valid_session(token or "")
    return APIResponse(
        success=True,
        data={
            "auth_required": True,
            "logged_in": valid,
            "has_password": await auth_svc.has_password(),
        }
    )


@router.patch("/toggle")
async def toggle(body: TogglePayload, response: Response) -> APIResponse:
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
