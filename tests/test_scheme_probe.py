"""scheme_probe 协议探测测试：三态判定 + 缓存命中/TTL + 端点。"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# 确保测试用临时配置
os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_api_test_config"

import app.services.scheme_probe as scheme_probe
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class FakeSocket:
    """模拟 socket：sendall 记录，recv 返回预设字节或抛异常。"""

    def __init__(self, response: bytes, exc: Exception | None = None):
        self._response = response
        self._exc = exc
        self.sent = b""

    def settimeout(self, t):
        pass

    def sendall(self, data):
        self.sent = data

    def recv(self, n):
        if self._exc is not None:
            raise self._exc
        return self._response[:n]

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _conn(sock: FakeSocket):
    return patch.object(scheme_probe.socket, "create_connection", return_value=sock)


class TestClassify:
    def test_tls_server_hello(self):
        with _conn(FakeSocket(b"\x16\x03\x03\x01\x02AB")):
            assert scheme_probe._classify("127.0.0.1", 443) == "https"

    def test_tls_alert(self):
        with _conn(FakeSocket(b"\x15\x03\x01\x00\x02")):
            assert scheme_probe._classify("127.0.0.1", 443) == "https"

    def test_http_response(self):
        with _conn(FakeSocket(b"HTTP/1.1 400 Bad Request\r\n\r\n")):
            assert scheme_probe._classify("127.0.0.1", 80) == "http"

    def test_timeout(self):
        with _conn(FakeSocket(b"", exc=TimeoutError())):
            assert scheme_probe._classify("127.0.0.1", 22) == "unknown"

    def test_connection_refused(self):
        with _conn(FakeSocket(b"", exc=ConnectionRefusedError())):
            assert scheme_probe._classify("127.0.0.1", 9999) == "unknown"

    def test_empty_response(self):
        with _conn(FakeSocket(b"")):
            assert scheme_probe._classify("127.0.0.1", 1234) == "unknown"


class TestClassifyTwoStage:
    """两段式探测：第一段 ClientHello 无响应时，第二段发真实 GET 再判。"""

    def test_stage2_http_after_silent_stage1(self):
        """第一段静默（部分 HTTP 服务对乱码不回应），第二段回 HTTP 状态行 → http"""
        sockets = iter([FakeSocket(b""), FakeSocket(b"HTTP/1.1 200 OK\r\n\r\n")])
        with patch.object(
            scheme_probe.socket, "create_connection", side_effect=lambda *a, **k: next(sockets)
        ):
            assert scheme_probe._classify("127.0.0.1", 8080) == "http"

    def test_stage2_non_http(self):
        """两段都非 HTTP（如数据库握手包）→ unknown"""
        sockets = iter([FakeSocket(b"\x0a\x00\x00\x00\x0a"), FakeSocket(b"\xff\xff")])
        with patch.object(
            scheme_probe.socket, "create_connection", side_effect=lambda *a, **k: next(sockets)
        ):
            assert scheme_probe._classify("127.0.0.1", 3306) == "unknown"

    def test_stage1_tls_short_circuits(self):
        """第一段判定 TLS 后不再开第二段连接"""
        sockets = iter([FakeSocket(b"\x16\x03\x03\x01\x02AB")])
        with patch.object(
            scheme_probe.socket, "create_connection", side_effect=lambda *a, **k: next(sockets)
        ):
            assert scheme_probe._classify("127.0.0.1", 443) == "https"


class TestPortSchemeFallback:
    def test_https_ports(self):
        assert scheme_probe.port_scheme_fallback(443) == "https"
        assert scheme_probe.port_scheme_fallback(8443) == "https"

    def test_http_port(self):
        assert scheme_probe.port_scheme_fallback(80) == "http"

    def test_unknown_port_returns_none(self):
        assert scheme_probe.port_scheme_fallback(22, 3306) is None

    def test_call_order_is_priority(self):
        # 容器端口在前 → 容器端口命中优先
        assert scheme_probe.port_scheme_fallback(443, 80) == "https"
        assert scheme_probe.port_scheme_fallback(None, 443) == "https"

    def test_all_none(self):
        assert scheme_probe.port_scheme_fallback(None, None) is None


class TestProbeSchemesBatch:
    def test_batch_returns_map(self):
        def fake_probe(host, port, container_id=None):
            return "https" if port == 443 else "unknown"

        with patch.object(scheme_probe, "probe_scheme", side_effect=fake_probe):
            result = scheme_probe.probe_schemes_batch(
                "127.0.0.1", [(443, "cid", None), (8080, None, None)]
            )
        assert result == {443: "https", 8080: "unknown"}

    def test_batch_applies_port_fallback(self):
        """探测 unknown 时按端口号兜底：容器端口 443 → https"""

        def fake_probe(host, port, container_id=None):
            return "unknown"

        with patch.object(scheme_probe, "probe_scheme", side_effect=fake_probe):
            result = scheme_probe.probe_schemes_batch("127.0.0.1", [(22500, "cid", 443)])
        assert result == {22500: "https"}

    def test_batch_empty(self):
        assert scheme_probe.probe_schemes_batch("127.0.0.1", []) == {}


class TestProbeCache:
    def test_cache_hit(self):
        scheme_probe.clear_cache()
        calls = []

        def fake_conn(*args, **kwargs):
            calls.append(1)
            return FakeSocket(b"\x16\x03\x03\x01\x02AB")

        with patch.object(scheme_probe.socket, "create_connection", side_effect=fake_conn):
            r1 = scheme_probe.probe_scheme("127.0.0.1", 443, "cid1")
            r2 = scheme_probe.probe_scheme("127.0.0.1", 443, "cid1")
        assert r1 == "https"
        assert r2 == "https"
        assert len(calls) == 1  # 第二次命中缓存，不再连接

    def test_different_container_id_miss(self):
        scheme_probe.clear_cache()
        calls = []

        def fake_conn(*args, **kwargs):
            calls.append(1)
            return FakeSocket(b"\x16\x03\x03\x01\x02AB")

        with patch.object(scheme_probe.socket, "create_connection", side_effect=fake_conn):
            scheme_probe.probe_scheme("127.0.0.1", 443, "cid1")
            scheme_probe.probe_scheme("127.0.0.1", 443, "cid2")  # 新容器 ID → 未命中
        assert len(calls) == 2

    def test_ttl_expiry(self):
        scheme_probe.clear_cache()
        calls = []

        def fake_conn(*args, **kwargs):
            calls.append(1)
            return FakeSocket(b"\x16\x03\x03\x01\x02AB")

        with patch.object(scheme_probe.socket, "create_connection", side_effect=fake_conn):
            scheme_probe.probe_scheme("127.0.0.1", 443, "cid1")
        # 手动把缓存时间戳改到过期 → 应重探
        key = (443, "cid1")
        val, ts = scheme_probe._CACHE[key]
        scheme_probe._CACHE[key] = (val, ts - scheme_probe._TTL - 1)
        with patch.object(scheme_probe.socket, "create_connection", side_effect=fake_conn):
            scheme_probe.probe_scheme("127.0.0.1", 443, "cid1")
        assert len(calls) == 2


class TestProbeEndpoint:
    def test_probe_endpoint_success(self, client: TestClient):
        with patch.object(scheme_probe, "probe_scheme", return_value="https"):
            resp = client.post("/api/ports/probe_scheme", json={"port": 443, "container_id": "abc"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["scheme"] == "https"
        assert "host" in data["data"]

    def test_probe_endpoint_validation(self, client: TestClient):
        # 端口越界 → 422
        resp = client.post("/api/ports/probe_scheme", json={"port": 0})
        assert resp.status_code == 422

    def test_probe_endpoint_fallback(self, client: TestClient):
        """探测 unknown 时按容器端口兜底：443 → https"""
        with patch.object(scheme_probe, "probe_scheme", return_value="unknown"):
            resp = client.post(
                "/api/ports/probe_scheme",
                json={"port": 22500, "container_id": "abc", "container_port": 443},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["scheme"] == "https"


class TestProbeSchemesEndpoint:
    def test_batch_endpoint_success(self, client: TestClient):
        with patch.object(
            scheme_probe, "probe_schemes_batch", return_value={80: "http", 443: "https"}
        ):
            resp = client.post(
                "/api/ports/probe_schemes",
                json={
                    "items": [
                        {"port": 80, "container_id": None, "container_port": None},
                        {"port": 443, "container_id": "abc", "container_port": 443},
                    ]
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["schemes"] == {"80": "http", "443": "https"}
        assert "host" in data["data"]

    def test_batch_endpoint_empty_items(self, client: TestClient):
        with patch.object(scheme_probe, "probe_schemes_batch", return_value={}):
            resp = client.post("/api/ports/probe_schemes", json={"items": []})
        assert resp.status_code == 200
        assert resp.json()["data"]["schemes"] == {}
