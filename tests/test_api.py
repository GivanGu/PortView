"""API 冒烟测试。"""

import os

import pytest
from fastapi.testclient import TestClient

# 确保测试用临时配置
os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_api_test_config"

from app.main import app


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
        resp = client.get(
            "/api/ports", params={"protocol": "TCP", "start_port": 1, "end_port": 100}
        )
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
        resp = client.post(
            "/api/config/edit",
            json={"port": 8080, "service_name": "MyApp", "service_type": "docker"},
        )
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
        r = client.post(
            "/api/notes",
            json={
                "port": 8080,
                "service_name": "http-svc",
                "protocol": "tcp",
                "remark": "web",
            },
        )
        assert r.status_code == 200 and r.json()["success"] is True

        # upsert（修改 remark）
        r = client.post(
            "/api/notes",
            json={
                "port": 8080,
                "service_name": "http-svc",
                "protocol": "tcp",
                "remark": "web v2",
            },
        )
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
        client.post(
            "/api/notes",
            json={"port": 5432, "service_name": "postgres", "protocol": "both", "remark": "db"},
        )
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

    def test_favorites_roundtrip(self, client: TestClient):
        assert client.get("/api/prefs").json()["data"]["favorites"] == []
        r = client.patch("/api/prefs", json={"favorites": [80, 443, 22]})
        assert r.json()["success"] is True
        d = client.get("/api/prefs").json()["data"]
        assert d["favorites"] == [80, 443, 22]
        # 其他字段不受影响
        assert d["theme"] in ("dark", "light")
        # 重置清空收藏
        client.post("/api/prefs/reset")
        assert client.get("/api/prefs").json()["data"]["favorites"] == []

    def test_favorites_grid_roundtrip(self, client: TestClient):
        # v1.6.5：GridItem 数组（port/url 条目 + 文件夹）后端透传不解析
        grid = [
            {"id": "port-80", "kind": "port", "port": 80},
            {
                "id": "url-1",
                "kind": "url",
                "url": "https://example.com",
                "title": "Example",
                "logoKey": "url:example.com",
            },
            {
                "id": "folder-1",
                "kind": "folder",
                "name": "Dev",
                "items": [{"id": "port-3000", "kind": "port", "port": 3000}],
            },
        ]
        r = client.patch("/api/prefs", json={"favorites": grid})
        assert r.json()["success"] is True
        d = client.get("/api/prefs").json()["data"]
        assert d["favorites"] == grid

    def test_default_tab_and_scope_roundtrip(self, client: TestClient):
        # v1.6.6：默认主页 + 背景作用域，PATCH 局部更新 + 读回
        d = client.get("/api/prefs").json()["data"]
        assert d["default_tab"] == "favorites"
        assert d["background_scope"] == "favorites"

        r = client.patch("/api/prefs", json={"default_tab": "overview", "background_scope": "all"})
        assert r.json()["success"] is True
        d = client.get("/api/prefs").json()["data"]
        assert d["default_tab"] == "overview"
        assert d["background_scope"] == "all"

    def test_bad_default_tab_rejected(self, client: TestClient):
        r = client.patch("/api/prefs", json={"default_tab": "ports"})
        assert r.json()["success"] is False

    def test_bad_background_scope_rejected(self, client: TestClient):
        r = client.patch("/api/prefs", json={"background_scope": "everywhere"})
        assert r.json()["success"] is False

    def test_reset_restores_home_and_scope(self, client: TestClient):
        client.patch("/api/prefs", json={"default_tab": "overview", "background_scope": "all"})
        r = client.post("/api/prefs/reset")
        assert r.json()["success"] is True
        d = client.get("/api/prefs").json()["data"]
        assert d["default_tab"] == "favorites"
        assert d["background_scope"] == "favorites"


class TestBackground:
    """v1.6.6 自定义背景图端点。"""

    def _png_1x1(self) -> str:
        import base64

        return base64.b64encode(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
            )
        ).decode()

    def test_get_unset_404(self, client: TestClient):
        client.delete("/api/background")
        r = client.get("/api/background")
        assert r.status_code == 404

    def test_upload_get_delete_roundtrip(self, client: TestClient):
        data = self._png_1x1()
        r = client.put("/api/background", json={"mime": "image/png", "data": data})
        assert r.status_code == 200
        assert r.json()["success"] is True

        r = client.get("/api/background")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 0

        r = client.delete("/api/background")
        assert r.json()["success"] is True
        assert client.get("/api/background").status_code == 404

    def test_upload_invalid_mime(self, client: TestClient):
        import base64

        data = base64.b64encode(b"hello").decode()
        r = client.put("/api/background", json={"mime": "text/plain", "data": data})
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_upload_too_large_rejected(self, client: TestClient):
        # 4MiB + 1 字节 → 拒绝
        import base64

        big = base64.b64encode(b"\x00" * (4 * 1024 * 1024 + 1)).decode()
        r = client.put("/api/background", json={"mime": "image/png", "data": big})
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_delete_idempotent(self, client: TestClient):
        r = client.delete("/api/background")
        assert r.status_code == 200
        assert r.json()["success"] is True


class TestLogos:
    """v1.5.0 应用 Logo 端点。"""

    def test_list_empty(self, client: TestClient):
        r = client.get("/api/logos")
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert isinstance(r.json()["data"], list)

    def test_upload_and_get(self, client: TestClient):
        # 上传一张 1x1 PNG
        import base64

        png_1x1 = base64.b64encode(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
            )
        ).decode()
        r = client.put("/api/logos/test-app", json={"mime": "image/png", "data": png_1x1})
        assert r.status_code == 200
        assert r.json()["success"] is True

        # GET 应返回图片字节
        r = client.get("/api/logos/test-app")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 0

        # 列表应包含
        lst = client.get("/api/logos").json()["data"]
        assert any(m["app_key"] == "test-app" and m["status"] == "found" for m in lst)

        # 清理
        assert client.delete("/api/logos/test-app").json()["success"] is True

    def test_upload_invalid_mime(self, client: TestClient):
        import base64

        data = base64.b64encode(b"hello").decode()
        r = client.put("/api/logos/bad-mime", json={"mime": "text/plain", "data": data})
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_upload_invalid_base64(self, client: TestClient):
        r = client.put("/api/logos/bad-b64", json={"mime": "image/png", "data": "!!!"})
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_delete_idempotent(self, client: TestClient):
        # 删除不存在的 key 也应成功
        r = client.delete("/api/logos/nonexistent")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_get_not_found(self, client: TestClient):
        r = client.get("/api/logos/ghost-app")
        assert r.status_code == 404

    def test_invalid_app_key(self, client: TestClient):
        r = client.get("/api/logos/UPPER_CASE!")
        assert r.status_code == 400

    def test_discover_no_port(self, client: TestClient):
        # port=0 应直接落 not_found
        r = client.post("/api/logos/discover", json={"app_key": "no-port", "port": 0})
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["data"]["status"] == "not_found"

        # 清理
        client.delete("/api/logos/no-port")

    def test_discover_idempotent(self, client: TestClient):
        # 先上传一个 logo
        import base64

        png_1x1 = base64.b64encode(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
            )
        ).decode()
        client.put("/api/logos/idem-app", json={"mime": "image/png", "data": png_1x1})

        # 再次 discover 应返回 cached
        r = client.post("/api/logos/discover", json={"app_key": "idem-app", "port": 8080})
        assert r.json()["success"] is True
        assert r.json()["message"] == "cached"

        # 清理
        client.delete("/api/logos/idem-app")

    def test_fetch_invalid_url(self, client: TestClient):
        # 非 http(s) 或无 host → 拒绝
        r = client.post("/api/logos/fetch", json={"app_key": "bad-url", "url": "ftp://example.com"})
        assert r.status_code == 200
        assert r.json()["success"] is False
        r = client.post("/api/logos/fetch", json={"app_key": "bad-url2", "url": "https://"})
        assert r.json()["success"] is False

    def test_fetch_idempotent(self, client: TestClient):
        # 已有终态记录 → cached，不重复抓取
        import base64

        png_1x1 = base64.b64encode(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
            )
        ).decode()
        client.put("/api/logos/fetch-idem", json={"mime": "image/png", "data": png_1x1})
        r = client.post(
            "/api/logos/fetch", json={"app_key": "fetch-idem", "url": "https://example.com"}
        )
        assert r.json()["success"] is True
        assert r.json()["message"] == "cached"
        client.delete("/api/logos/fetch-idem")

    def test_fetch_unreachable_not_found(self, client: TestClient):
        # 127.0.0.1:1 连接被拒 → 落 not_found
        r = client.post(
            "/api/logos/fetch", json={"app_key": "fetch-miss", "url": "http://127.0.0.1:1/"}
        )
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["data"]["status"] == "not_found"
        client.delete("/api/logos/fetch-miss")

    def test_fetch_found_local_server(self, client: TestClient):
        # 本地起一个 HTTP 服务提供 /favicon.ico → 抓取成功落 found
        import http.server
        import socketserver
        import threading

        png_1x1 = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
        )

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/favicon.ico":
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.end_headers()
                    self.wfile.write(png_1x1)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                pass

        with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
            port = httpd.server_address[1]
            th = threading.Thread(target=httpd.serve_forever, daemon=True)
            th.start()
            try:
                # URL 带路径：抓取应只取 origin（scheme://host[:port]）
                r = client.post(
                    "/api/logos/fetch",
                    json={"app_key": "fetch-ok", "url": f"http://127.0.0.1:{port}/some/path"},
                )
                assert r.json()["success"] is True
                assert r.json()["data"]["status"] == "found"
                assert r.json()["data"]["mime"] == "image/png"
                img = client.get("/api/logos/fetch-ok")
                assert img.status_code == 200
                assert img.content == png_1x1
            finally:
                httpd.shutdown()
                th.join(timeout=2)
            client.delete("/api/logos/fetch-ok")

    def test_fetch_url_too_long(self, client: TestClient):
        # url 超过 2048 → Pydantic 校验拒绝（422）
        r = client.post(
            "/api/logos/fetch",
            json={"app_key": "long-url", "url": "https://example.com/" + "a" * 3000},
        )
        assert r.status_code == 422

    def test_fetch_userinfo_stripped(self, client: TestClient):
        # URL 内嵌 user:pass → 抓取时不得附加 Authorization 头
        import http.server
        import socketserver
        import threading

        png_1x1 = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
        )
        seen_auth: list[str | None] = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen_auth.append(self.headers.get("Authorization"))
                if self.path == "/favicon.ico":
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.end_headers()
                    self.wfile.write(png_1x1)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                pass

        with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
            port = httpd.server_address[1]
            th = threading.Thread(target=httpd.serve_forever, daemon=True)
            th.start()
            try:
                r = client.post(
                    "/api/logos/fetch",
                    json={
                        "app_key": "fetch-auth",
                        "url": f"http://user:pass@127.0.0.1:{port}/",
                    },
                )
                assert r.json()["success"] is True
                assert r.json()["data"]["status"] == "found"
            finally:
                httpd.shutdown()
                th.join(timeout=2)
            client.delete("/api/logos/fetch-auth")
        # 目标站收到的所有请求都不应带 Authorization 头
        assert seen_auth, "local server received no request"
        assert all(a is None for a in seen_auth), f"Authorization leaked: {seen_auth}"

    def test_default_logos_list(self, client: TestClient):
        # v1.5.13：内置默认 Logo 匹配表应含 names + ports
        r = client.get("/api/logos/defaults")
        assert r.status_code == 200
        assert r.json()["success"] is True
        data = r.json()["data"]
        assert "mysql" in data["names"] and "redis" in data["names"]
        # 知名端口映射：3306 → mysql，443 → https
        assert data["ports"]["3306"] == "mysql"
        assert data["ports"]["443"] == "https"

    def test_default_logo_get(self, client: TestClient):
        # v1.5.13：内置默认 Logo 应返回 SVG 字节
        r = client.get("/api/logos/default/mysql")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/svg+xml")
        assert b"<svg" in r.content

    def test_default_logo_not_found(self, client: TestClient):
        # v1.5.13：未知 key 应 404
        r = client.get("/api/logos/default/unknown-service")
        assert r.status_code == 404
