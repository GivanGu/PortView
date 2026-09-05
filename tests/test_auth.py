"""认证模块测试 — 登录 / 登出 / 用户信息 / 修改密码。"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_auth_test_config"

from app.main import app  # noqa: E402
from app.routers.auth import get_current_user, init_db  # noqa: E402

# 跳过认证（测试环境）
app.dependency_overrides[get_current_user] = lambda: "admin"

# 初始化测试数据库
init_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestAuth:
    def test_login_success(self, client: TestClient):
        """正确密码 → 返回 JWT token。"""
        resp = client.post("/api/auth/login", json={"password": "portview123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "token" in data["data"]
        assert "user" in data["data"]
        assert data["data"]["user"]["username"] == "admin"

    def test_login_wrong_password(self, client: TestClient):
        """错误密码 → 401。"""
        resp = client.post("/api/auth/login", json={"password": "wrong"})
        assert resp.status_code == 401

    def test_me_with_override(self, client: TestClient):
        """跳过认证的 /me。"""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["data"]["username"] == "admin"

    def test_me_without_token(self):
        """无认证 → 受保护的路由。"""
        app.dependency_overrides.pop(get_current_user, None)
        with TestClient(app) as client:
            resp = client.get("/api/auth/me")
            assert resp.status_code == 401
        # 恢复覆盖
        app.dependency_overrides[get_current_user] = lambda: "admin"

    def test_logout(self, client: TestClient):
        """退出 → 返回成功。"""
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_change_password(self, client: TestClient):
        """修改密码 — 原密码错误时 401。"""
        resp = client.post(
            "/api/auth/change-password",
            json={"old_password": "wrong", "new_password": "newpass123"},
        )
        assert resp.status_code == 401
