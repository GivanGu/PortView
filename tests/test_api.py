"""API 冒烟测试。"""

import os

import pytest
from fastapi.testclient import TestClient

# 确保测试用临时配置
os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_api_test_config"

from app.main import app  # noqa: E402
from app.routers.auth import get_current_user  # noqa: E402


def _skip_auth():
    """测试环境跳过认证 —— 返回虚拟用户。"""
    return "admin"


# 覆盖认证依赖（测试环境不需登录）
app.dependency_overrides[get_current_user] = _skip_auth


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestPorts:
    def test_ports_basic(self, client: TestClient):
        resp = client.get("/api/ports", params={"start_port": 1, "end_port": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "port_cards" in data["data"]
        assert "total_used" in data["data"]
        assert "total_available" in data["data"]

    def test_ports_protocol_filter(self, client: TestClient):
        resp = client.get("/api/ports", params={"protocol": "TCP", "start_port": 1, "end_port": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["protocol_filter"] == "TCP"

    def test_ports_search(self, client: TestClient):
        resp = client.get("/api/ports", params={"search": "80", "start_port": 1, "end_port": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_ports_range_validation(self, client: TestClient):
        resp = client.get("/api/ports", params={"start_port": 1, "end_port": 65535})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


class TestConfig:
    def test_get_config(self, client: TestClient):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], dict)

    def test_save_config(self, client: TestClient):
        payload = {"test_service:host": "1234:tcp"}
        resp = client.post("/api/config", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_save_config_invalid(self, client: TestClient):
        payload = {"bad_key": "no_colon"}
        resp = client.post("/api/config", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "error" in data

    def test_edit_port(self, client: TestClient):
        resp = client.post("/api/config/edit", json={"port": 8080, "service_name": "MyApp", "service_type": "docker"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_hidden_ports_crud(self, client: TestClient):
        # 隐藏
        resp = client.post("/api/config/hidden", json={"port": 9999})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 查询
        resp = client.get("/api/config/hidden")
        assert resp.status_code == 200
        assert 9999 in resp.json()["data"]

        # 取消隐藏
        resp = client.delete("/api/config/hidden/9999")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 验证已移除
        resp = client.get("/api/config/hidden")
        assert 9999 not in resp.json()["data"]

    def test_batch_hide(self, client: TestClient):
        resp = client.post("/api/config/hidden/batch", json={"ports": [1111, 2222, 3333]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = client.get("/api/config/hidden")
        data = resp.json()["data"]
        assert 1111 in data
        assert 2222 in data
        assert 3333 in data

        # 批量取消
        resp = client.post("/api/config/hidden/unhide/batch", json={"ports": [1111, 2222, 3333]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestRefresh:
    def test_refresh(self, client: TestClient):
        resp = client.post("/api/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "port_cards" in data["data"]


class TestAuth:
    def test_login_default(self, client: TestClient):
        resp = client.post("/api/auth/login", json={"password": "portview123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "token" in data["data"]
        assert data["data"]["user"]["username"] == "admin"

    def test_login_wrong_password(self, client: TestClient):
        resp = client.post("/api/auth/login", json={"password": "wrong"})
        assert resp.status_code == 401

    def test_me(self, client: TestClient):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["data"]["username"] == "admin"


class TestRanges:
    def test_ranges_crud(self, client: TestClient):
        # 查询 (返回数组)
        resp = client.get("/api/config/ranges")
        assert resp.status_code == 200
        initial = resp.json()
        assert isinstance(initial, list)

        # 创建
        resp = client.post(
            "/api/config/ranges",
            json={"name": "游戏服务器", "start_port": 22500, "end_port": 22600},
        )
        assert resp.status_code == 201

        # 查询
        resp = client.get("/api/config/ranges")
        ranges = resp.json()
        assert isinstance(ranges, list)
        assert any(r["name"] == "游戏服务器" for r in ranges)

        # 删除
        new_range = next(r for r in ranges if r["name"] == "游戏服务器")
        resp = client.delete(f"/api/config/ranges/{new_range['id']}")
        assert resp.status_code == 200
        assert not any(
            r["name"] == "游戏服务器"
            for r in resp.json()
        )


class TestNotifications:
    def test_notifications(self, client: TestClient):
        resp = client.get("/api/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert "notifications" in data["data"]
        assert "unread_count" in data["data"]


class TestPortsConflict:
    def test_ports_has_conflict_field(self, client: TestClient):
        resp = client.get("/api/ports", params={"start_port": 1, "end_port": 65535})
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 验证 port_cards 可能包含 conflict 字段（即使为 False / None）
        for card in data["port_cards"][:100]:
            assert "conflict" in card or card["type"] in ("gap", "unknown_range")
