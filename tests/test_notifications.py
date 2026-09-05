"""通知 API 测试。"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_notification_test_config"

from app.main import app  # noqa: E402
from app.routers.auth import get_current_user, init_db  # noqa: E402

app.dependency_overrides[get_current_user] = lambda: "admin"
init_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestNotifications:
    def test_list_notifications(self, client: TestClient):
        resp = client.get("/api/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "notifications" in data["data"]
        assert "unread_count" in data["data"]

    def test_mark_all_read(self, client: TestClient):
        resp = client.post("/api/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_mark_single_read(self, client: TestClient):
        # 先获取一条通知
        list_resp = client.get("/api/notifications")
        items = list_resp.json()["data"]["notifications"]
        if items:
            nid = items[0]["id"]
            resp = client.post(f"/api/notifications/read/{nid}")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_clear_read(self, client: TestClient):
        resp = client.delete("/api/notifications/clear-read")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
