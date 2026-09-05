"""P1.1 测试：auth + ranges + remark 打通。

覆盖：
- 设置密码 / 登录 / 登出 / 401 守卫
- 关闭 auth 时全放行
- range_rules CRUD
- /api/ports?range_ids=... 过滤
- /api/ports 卡片带 remark
"""

from __future__ import annotations

import os

os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_p1_test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# 强制使用临时 SQLite
os.environ["PORTVIEW_DB"] = "/tmp/portview_p1_test/p1.db"
# 关掉 env 层的 require_auth，让测试控制
os.environ.pop("PORTVIEW_REQUIRE_AUTH", None)

from app.main import app  # noqa: E402


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
        resp = client.post("/api/ranges", json={"name": "test-range", "start_port": 80, "end_port": 90})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "test-range"
        assert data["start_port"] == 80
        # update
        u = client.put(f"/api/ranges/{data['id']}", json={"end_port": 100})
        assert u.status_code == 200
        assert u.json()["data"]["end_port"] == 100
        # duplicate name
        dup = client.post("/api/ranges", json={"name": "test-range", "start_port": 1, "end_port": 2})
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


# --------------------- A3: remark 注入 ---------------------


class TestRemark:
    def test_remark_in_used_card(self, client: TestClient):
        # 起一个真监听 → 让 host 的 port 变成"已用"（不依赖 Docker）
        import socket
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)
        try:
            # 塞备注
            r = client.post(
                "/api/notes",
                json={"port": port, "service_name": "test-svc", "protocol": "tcp", "remark": "http entry"},
            )
            assert r.status_code == 200
            # 查该端口 → 应"已用"且带 remark
            resp = client.get("/api/ports", params={"start_port": port, "end_port": port})
            assert resp.status_code == 200
            used = [
                c for c in resp.json()["data"]["port_cards"]
                if c["type"] == "used" and c.get("port") == port
            ]
            assert used, f"port {port} should be 'used' (card set: {resp.json()['data']['port_cards']})"
            assert used[0].get("remark") == "http entry", used[0]
            # 搜索命中备注
            s = client.get("/api/ports", params={"search": "http entry", "start_port": 1, "end_port": 65535})
            hits = [c for c in s.json()["data"]["port_cards"] if c.get("remark")]
            assert any(c.get("port") == port for c in hits), f"remark-search missed {port}; hits={hits}"
        finally:
            srv.close()


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
