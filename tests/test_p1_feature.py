"""P1.1 测试：auth + ranges 打通。

覆盖：
- 设置密码 / 登录 / 登出 / 401 守卫
- 关闭 auth 时全放行
- range_rules CRUD
- /api/ports?range_ids=... 过滤

DB / 配置目录隔离由 tests/conftest.py 统一处理（临时路径 + 每用例全新 DB）。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    # 清理旧会话
    with TestClient(app) as c:
        yield c


# --------------------- auth ---------------------


class TestAuth:
    def test_disable_default(self, client: TestClient):
        """默认关闭 auth 时 /api/ports 不需 cookie。"""
        resp = client.get("/api/ports")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_set_password(self, client: TestClient):
        resp = client.post("/api/auth/set_password", json={"password": "portview-1234"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_login_ok(self, client: TestClient):
        client.post("/api/auth/set_password", json={"password": "portview-1234"})
        resp = client.post("/api/auth/login", json={"password": "portview-1234"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # cookie 种下
        assert "portview_session" in client.cookies

    def test_login_wrong_password(self, client: TestClient):
        client.post("/api/auth/set_password", json={"password": "correct"})
        resp = client.post("/api/auth/login", json={"password": "wrong_pass"})
        assert resp.status_code == 401

    def test_logout_cleans_cookie(self, client: TestClient):
        client.post("/api/auth/set_password", json={"password": "portview-1234"})
        client.post("/api/auth/login", json={"password": "portview-1234"})
        before = client.cookies.get("portview_session")
        assert before
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200

    def test_me(self, client: TestClient):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "auth_required" in data
        assert "logged_in" in data
        assert "has_password" in data

    def test_toggle_requires_password(self, client: TestClient):
        """未设置密码时开启登录保护应返回 400；有密码则可开启。"""
        # 全新 DB 无密码 → 开启保护应被拒绝
        resp = client.patch("/api/auth/toggle", json={"enabled": True})
        assert resp.status_code == 400
        # 设置密码后可开启
        client.post("/api/auth/set_password", json={"password": "portview-1234"})
        resp2 = client.patch("/api/auth/toggle", json={"enabled": True})
        assert resp2.status_code == 200
        # 收尾：登录后关闭（保护开启时关闭需有效会话）
        client.post("/api/auth/login", json={"password": "portview-1234"})
        client.patch("/api/auth/toggle", json={"enabled": False})

    def test_set_password_requires_session_when_enabled(self, client: TestClient):
        """保护开启且已有密码时，修改密码必须持有有效会话，否则可被未授权接管。"""
        client.post("/api/auth/set_password", json={"password": "first-pass"})
        client.patch("/api/auth/toggle", json={"enabled": True})
        # 未登录改密码 → 401
        resp = client.post("/api/auth/set_password", json={"password": "hacked-pass"})
        assert resp.status_code == 401
        # 原密码仍然有效
        ok = client.post("/api/auth/login", json={"password": "first-pass"})
        assert ok.status_code == 200
        # 登录后可以改密码
        changed = client.post("/api/auth/set_password", json={"password": "second-pass"})
        assert changed.status_code == 200
        # 改密后旧会话全部撤销 → 必须用新密码重新登录
        client.cookies.clear()
        again = client.post("/api/auth/login", json={"password": "second-pass"})
        assert again.status_code == 200
        # 收尾：关闭保护
        client.patch("/api/auth/toggle", json={"enabled": False})

    def test_toggle_off_requires_session_when_enabled(self, client: TestClient):
        """保护开启时，关闭保护必须持有有效会话，否则可未授权绕过全部鉴权。"""
        client.post("/api/auth/set_password", json={"password": "guard-pass"})
        client.patch("/api/auth/toggle", json={"enabled": True})
        # 未登录关闭 → 401
        resp = client.patch("/api/auth/toggle", json={"enabled": False})
        assert resp.status_code == 401
        # 保护仍然生效 → /api/ports 仍 401
        assert client.get("/api/ports").status_code == 401
        # 登录后可关闭
        client.post("/api/auth/login", json={"password": "guard-pass"})
        ok = client.patch("/api/auth/toggle", json={"enabled": False})
        assert ok.status_code == 200
        assert client.get("/api/ports").status_code == 200


# --------------------- ranges CRUD ---------------------


class TestRanges:
    def test_empty_start(self, client: TestClient):
        # 清空
        r = client.get("/api/ranges")
        for item in r.json()["data"]:
            client.delete(f"/api/ranges/{item['id']}")
        r2 = client.get("/api/ranges")
        assert r2.json()["data"] == []

    def test_crud(self, client: TestClient):
        resp = client.post(
            "/api/ranges", json={"name": "test-range", "start_port": 80, "end_port": 90}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "test-range"
        assert data["start_port"] == 80
        # update
        u = client.put(f"/api/ranges/{data['id']}", json={"end_port": 100})
        assert u.status_code == 200
        assert u.json()["data"]["end_port"] == 100
        # duplicate name
        dup = client.post(
            "/api/ranges", json={"name": "test-range", "start_port": 1, "end_port": 2}
        )
        assert dup.status_code == 409
        # delete
        d = client.delete(f"/api/ranges/{data['id']}")
        assert d.status_code == 200

    def test_invalid_order(self, client: TestClient):
        # start > end 应 422
        # 先造一个
        r = client.post("/api/ranges", json={"name": "bad", "start_port": 200, "end_port": 100})
        assert r.status_code == 422
        # 清理
        r2 = client.get("/api/ranges")
        for item in r2.json()["data"]:
            if item["name"] == "bad":
                client.delete(f"/api/ranges/{item['id']}")


# --------------------- A2: range_ids 过滤 ---------------------


class TestRangeFilter:
    def test_range_ids_narrow(self, client: TestClient):
        # 建两段
        r = client.get("/api/ranges")
        for item in r.json()["data"]:
            client.delete(f"/api/ranges/{item['id']}")
        a = client.post("/api/ranges", json={"name": "80s", "start_port": 80, "end_port": 85})
        b = client.post("/api/ranges", json={"name": "8000s", "start_port": 8000, "end_port": 8010})
        aids = [a.json()["data"]["id"], b.json()["data"]["id"]]
        # 带 range_ids=80s-only
        resp = client.get("/api/ports", params={"range_ids": [aids[0]]})
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 所有卡片都应落在 [80,85] 内
        for c in data["port_cards"]:
            if c["type"] == "used":
                assert 80 <= c["port"] <= 85, c
            else:
                assert 80 <= c["start_port"] <= c["end_port"] <= 85, c
        # 清理
        for aid in aids:
            client.delete(f"/api/ranges/{aid}")


# --------------------- A1: 登录守卫开启 ---------------------


class TestAuthGuard:
    def test_guard_blocks_when_enabled(self, client: TestClient):
        # 开启 auth
        client.post("/api/auth/set_password", json={"password": "guard-pass"})
        client.patch("/api/auth/toggle", json={"enabled": True})
        # 无 cookie 访问 /api/ports 应 401
        r = client.get("/api/ports")
        assert r.status_code == 401
        # /api/health、/api/auth/* 仍放行
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/auth/me").status_code == 200
        # 登录 → 有 cookie
        client.post("/api/auth/login", json={"password": "guard-pass"})
        r2 = client.get("/api/ports")
        assert r2.status_code == 200
        # 关闭 auth → 无 cookie 也放行
        client.patch("/api/auth/toggle", json={"enabled": False})
        client.cookies.clear()
        r3 = client.get("/api/ports")
        assert r3.status_code == 200
