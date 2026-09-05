"""自定义监控区间 CRUD 测试。"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_ranges_test_config"

from app.main import app  # noqa: E402
from app.routers.auth import get_current_user, init_db  # noqa: E402

app.dependency_overrides[get_current_user] = lambda: "admin"
init_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


_RANGES_PATH = "/api/config/ranges"


class TestRanges:
    def test_list_ranges(self, client: TestClient):
        resp = client.get(_RANGES_PATH)
        assert resp.status_code == 200
        # 路由返回 list[PortRange] 直接
        data = resp.json()
        assert isinstance(data, list)

    def test_create_range(self, client: TestClient):
        payload = {
            "name": "Web端口",
            "start_port": 80,
            "end_port": 8080,
            "color": "#3b82f6",
        }
        resp = client.post(_RANGES_PATH, json=payload)
        assert resp.status_code == 201
        created = resp.json()
        assert isinstance(created, list)
        web = [r for r in created if r["name"] == "Web端口"]
        assert len(web) == 1
        assert web[0]["start_port"] == 80

    def test_create_range_invalid(self, client: TestClient):
        """起始 > 结束 → 验证失败 (422)。"""
        resp = client.post(
            _RANGES_PATH,
            json={"name": "Bad", "start_port": 9000, "end_port": 1000, "color": "#000000"},
        )
        assert resp.status_code == 422

    def test_update_range(self, client: TestClient):
        # 先创建
        create_resp = client.post(
            _RANGES_PATH,
            json={"name": "Test", "start_port": 5000, "end_port": 6000, "color": "#f59e0b"},
        )
        ranges = create_resp.json()
        test_range = [r for r in ranges if r["name"] == "Test"][0]
        range_id = test_range["id"]

        # 编辑
        resp = client.put(
            f"{_RANGES_PATH}/{range_id}",
            json={"name": "Test-Updated", "start_port": 5001, "end_port": 5999, "color": "#ef4444"},
        )
        assert resp.status_code == 200
        updated_list = resp.json()
        updated = [r for r in updated_list if r["id"] == range_id][0]
        assert updated["name"] == "Test-Updated"
        assert updated["start_port"] == 5001

    def test_delete_range(self, client: TestClient):
        # 创建
        create_resp = client.post(
            _RANGES_PATH,
            json={"name": "ToDelete", "start_port": 7000, "end_port": 7500, "color": "#8b5cf6"},
        )
        ranges = create_resp.json()
        to_delete = [r for r in ranges if r["name"] == "ToDelete"][0]
        range_id = to_delete["id"]

        # 删除
        resp = client.delete(f"{_RANGES_PATH}/{range_id}")
        assert resp.status_code == 200
        remaining = resp.json()
        ids = [r["id"] for r in remaining]
        assert range_id not in ids

    def test_delete_nonexistent(self, client: TestClient):
        resp = client.delete(f"{_RANGES_PATH}/nonexistent_id")
        assert resp.status_code == 404
