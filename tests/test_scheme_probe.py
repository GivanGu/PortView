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
