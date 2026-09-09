"""API 冒烟测试。"""

import os

import pytest
from fastapi.testclient import TestClient

# 确保测试用临时配置
os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_api_test_config"

from app.main import app  # noqa: E402


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


class TestNotes:
    """P1-1 端口备注端点。"""

    def test_upsert_and_list(self, client: TestClient):
        # 新建
        r = client.post("/api/notes", json={
            "port": 8080, "service_name": "http-svc", "protocol": "tcp", "remark": "web",
        })
        assert r.status_code == 200 and r.json()["success"] is True

        # upsert（修改 remark）
        r = client.post("/api/notes", json={
            "port": 8080, "service_name": "http-svc", "protocol": "tcp", "remark": "web v2",
        })
        assert r.json()["success"] is True

        # 列表应包含且只有一条 8080，remark 为 v2
        lst = client.get("/api/notes").json()["data"]
        mine = [n for n in lst if n["port"] == 8080]
        assert len(mine) == 1
        assert mine[0]["remark"] == "web v2"
        assert mine[0]["protocol"] == "tcp"

        # 清理
        assert client.delete("/api/notes/8080").json()["success"] is True

    def test_port_range_validation(self, client: TestClient):
        # pydantic Field(ge=0, le=65535) 在请求层直接拦 422
        r = client.post("/api/notes", json={"port": 99999, "service_name": "x"})
        assert r.status_code == 422

    def test_protocol_validation(self, client: TestClient):
        # Literal['', 'tcp', 'udp', 'both'] 也在请求层拦
        r = client.post("/api/notes", json={"port": 100, "protocol": "sctp"})
        assert r.status_code == 422

    def test_search(self, client: TestClient):
        client.post("/api/notes", json={"port": 5432, "service_name": "postgres", "protocol": "both", "remark": "db"})
        data = client.get("/api/notes", params={"search": "postgres"}).json()["data"]
        assert any(n["port"] == 5432 for n in data)
        client.delete("/api/notes/5432")


class TestPrefs:
    """P1-2 用户偏好端点。"""

    def test_get_defaults(self, client: TestClient):
        r = client.get("/api/prefs")
        assert r.status_code == 200 and r.json()["success"] is True
        d = r.json()["data"]
        assert d["theme"] in ("dark", "light")
        assert d["lang"] in ("zh", "en")

    def test_patch_and_readback(self, client: TestClient):
        r = client.patch("/api/prefs", json={"theme": "light", "accent": "rose"})
        assert r.json()["success"] is True
        d = client.get("/api/prefs").json()["data"]
        assert d["theme"] == "light" and d["accent"] == "rose"

    def test_bad_accent_rejected(self, client: TestClient):
        r = client.patch("/api/prefs", json={"accent": "magenta"})
        assert r.json()["success"] is False

    def test_reset(self, client: TestClient):
        client.patch("/api/prefs", json={"theme": "light", "lang": "en"})
        r = client.post("/api/prefs/reset")
        assert r.json()["success"] is True
        d = client.get("/api/prefs").json()["data"]
        assert d["theme"] == "dark" and d["accent"] == "indigo" and d["lang"] == "zh"
