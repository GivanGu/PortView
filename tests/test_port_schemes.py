"""人工指定端口协议（port_schemes）端点测试。

覆盖：
- GET  /api/ports/schemes  列表（空 / 有值）
- POST /api/ports/scheme   设置 / 覆盖
- DELETE /api/ports/scheme/{port}  清除
- 非法 scheme / 越界端口 → 失败
"""

from __future__ import annotations

import os

os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_schemes_test"
os.environ["PORTVIEW_DB"] = "/tmp/portview_schemes_test/schemes.db"
os.environ.pop("PORTVIEW_REQUIRE_AUTH", None)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _reset(client: TestClient) -> None:
    """清掉 8080/8443 两个人工指定，避免用例间串扰。"""
    client.delete("/api/ports/scheme/8080")
    client.delete("/api/ports/scheme/8443")


class TestPortSchemes:
    def test_get_empty(self, client: TestClient):
        _reset(client)
        resp = client.get("/api/ports/schemes")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["data"] == {}

    def test_set_and_get(self, client: TestClient):
        _reset(client)
        resp = client.post("/api/ports/scheme", json={"port": 8080, "scheme": "https"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = client.get("/api/ports/schemes")
        assert resp.json()["data"] == {"8080": "https"}

    def test_set_overwrites(self, client: TestClient):
        _reset(client)
        client.post("/api/ports/scheme", json={"port": 8080, "scheme": "https"})
        resp = client.post("/api/ports/scheme", json={"port": 8080, "scheme": "http"})
        assert resp.json()["success"] is True
        assert client.get("/api/ports/schemes").json()["data"] == {"8080": "http"}

    def test_delete(self, client: TestClient):
        _reset(client)
        client.post("/api/ports/scheme", json={"port": 8443, "scheme": "https"})
        resp = client.delete("/api/ports/scheme/8443")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert client.get("/api/ports/schemes").json()["data"] == {}

    def test_multiple_ports(self, client: TestClient):
        _reset(client)
        client.post("/api/ports/scheme", json={"port": 80, "scheme": "http"})
        client.post("/api/ports/scheme", json={"port": 443, "scheme": "https"})
        data = client.get("/api/ports/schemes").json()["data"]
        assert data == {"80": "http", "443": "https"}

    def test_invalid_scheme_rejected(self, client: TestClient):
        _reset(client)
        resp = client.post("/api/ports/scheme", json={"port": 8080, "scheme": "ftp"})
        assert resp.status_code == 422

    def test_port_out_of_range_rejected(self, client: TestClient):
        _reset(client)
        resp = client.post("/api/ports/scheme", json={"port": 0, "scheme": "http"})
        assert resp.status_code == 422
