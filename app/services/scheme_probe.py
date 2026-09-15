"""服务链接协议探测：判定某端口对外提供的是 http 还是 https。

背景：访问地址只存主机（IP/域名），不存协议；同一台主机上可能同时跑 HTTP（80）
和 HTTPS（443）服务，Docker 端口映射还会让主机端口与服务实际端口解耦
（如容器 443 → 主机 22500），仅凭端口号无法可靠推断。

方案：对目标端口两段式探测：
1. 发最小 TLS ClientHello：
   - 收到 TLS 记录（0x16/0x15/0x14/0x17）→ https（对端是 TLS 服务）
   - 收到明文 HTTP 状态行（``HTTP/``）→ http
2. 第一段未判定且端口可连时，新开连接发真实 ``GET / HTTP/1.0`` 请求：
   部分 HTTP 服务对乱码数据不响应，但对合法请求会回状态行 → http

仍 unknown 时（如容器已停止、端口未监听）按端口号兜底推断：
容器端口优先于主机端口，443/8443 → https，80 → http。

「unknown 回退默认」保证探测的最坏情况 = 现状，绝不会比不探测更差。
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# 缓存：key=(port, container_id) → (scheme, timestamp)。
# 容器重部署（recreate）会产生新 container_id → key 变化 → 缓存未命中 → 立即重探。
# 宿主机 / 进程重启 → 内存缓存清空 → 无残留。
_TTL = 60.0
_CACHE: dict[tuple[int, str], tuple[str, float]] = {}
_LOCK = threading.Lock()

# 端口号 → 协议 兜底推断表（探测 unknown 时使用，如已停止的容器无法探测）
_PORT_SCHEME_FALLBACK: dict[int, str] = {
    80: "http",
    443: "https",
    8443: "https",
}


def port_scheme_fallback(*ports: int | None) -> str | None:
    """按端口号推断协议（调用顺序即优先级，如容器端口在前、主机端口在后）。

    无匹配返回 ``None``。
    """
    for port in ports:
        if port is not None:
            scheme = _PORT_SCHEME_FALLBACK.get(port)
            if scheme:
                return scheme
    return None


def _build_client_hello() -> bytes:
    """构建最小 TLS 1.2 ClientHello（仅用于探测对端是否 TLS 服务）。"""
    random_bytes = os.urandom(32)
    ciphers = b"".join(
        bytes(c)
        for c in (
            (0x13, 0x01),
            (0x13, 0x02),
            (0x13, 0x03),
            (0xC0, 0x2F),
            (0xC0, 0x30),
            (0xC0, 0x13),
            (0xC0, 0x09),
            (0x00, 0x2F),
            (0x00, 0x35),
            (0x00, 0x9C),
            (0x00, 0x9E),
            (0x00, 0x33),
            (0x00, 0x39),
            (0xCC, 0xA8),
            (0xCC, 0xA9),
            (0xC0, 0x2B),
            (0xC0, 0x08),
            (0xC0, 0x12),
            (0xC0, 0x07),
            (0xC0, 0x11),
            (0xC0, 0x06),
            (0x00, 0x32),
            (0x00, 0x36),
        )
    )
    compression = b"\x01\x00"

    exts = b""
    # supported_versions (type 43)：TLS 1.3 + 1.2
    sv = b"\x03\x04\x03\x03"
    sv_data = bytes([0x00, len(sv)]) + sv
    exts += bytes([0x00, 0x2B, len(sv_data) >> 8, len(sv_data) & 0xFF]) + sv_data
    # supported_groups (type 10)
    grp = b"\x00\x1d\x00\x17\x00\x18"
    grp_data = bytes([0x00, len(grp)]) + grp
    exts += bytes([0x00, 0x0A, len(grp_data) >> 8, len(grp_data) & 0xFF]) + grp_data
    # signature_algorithms (type 13)
    sig = b"\x04\x03\x05\x01\x06\x01\x08\x04\x08\x05"
    sig_data = bytes([0x00, len(sig)]) + sig
    exts += bytes([0x00, 0x0D, len(sig_data) >> 8, len(sig_data) & 0xFF]) + sig_data
    ext_bytes = bytes([len(exts) >> 8, len(exts) & 0xFF]) + exts

    body = (
        b"\x03\x03"
        + random_bytes
        + b"\x00"  # session id 长度 0
        + bytes([len(ciphers) >> 8, len(ciphers) & 0xFF])
        + ciphers
        + compression
        + ext_bytes
    )
    handshake = (
        b"\x01"
        + bytes([(len(body) >> 16) & 0xFF, (len(body) >> 8) & 0xFF, len(body) & 0xFF])
        + body
    )
    record = (
        b"\x16\x03\x01" + bytes([(len(handshake) >> 8) & 0xFF, len(handshake) & 0xFF]) + handshake
    )
    return record


_CLIENT_HELLO = _build_client_hello()


def _classify(host: str, port: int) -> str:
    """阻塞式两段探测：连 host:port，先发 ClientHello，未判定再发真实 GET。

    返回 'https' / 'http' / 'unknown'。
    """
    # 第一段：TLS ClientHello
    try:
        with socket.create_connection((host, port), timeout=2.0) as sock:
            sock.settimeout(2.0)
            sock.sendall(_CLIENT_HELLO)
            data = sock.recv(5)
    except (TimeoutError, OSError):
        return "unknown"
    if data:
        first = data[0]
        # TLS 记录类型：0x16 握手 / 0x15 alert / 0x14 change_cipher_spec / 0x17 application_data
        if first in (0x16, 0x15, 0x14, 0x17):
            return "https"
        if data.startswith(b"HTTP/"):
            return "http"
    # 第二段：端口可连但第一段无响应（部分 HTTP 服务对乱码不回应），
    # 新开连接发合法 GET 请求再试一次
    try:
        with socket.create_connection((host, port), timeout=2.0) as sock:
            sock.settimeout(2.0)
            sock.sendall(b"GET / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
            data = sock.recv(5)
    except (TimeoutError, OSError):
        return "unknown"
    if data.startswith(b"HTTP/"):
        return "http"
    return "unknown"


def probe_scheme(host: str, port: int, container_id: str | None = None) -> str:
    """带缓存的协议探测。返回 'http' / 'https' / 'unknown'。

    缓存 key=(port, container_id)，TTL 60s。容器重部署产生新 container_id → 缓存未命中。
    """
    key = (port, container_id or "")
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[1] < _TTL:
            return cached[0]
        result = _classify(host, port)
        _CACHE[key] = (result, now)
        return result


def probe_schemes_batch(
    host: str,
    items: list[tuple[int, str | None, int | None]],
) -> dict[int, str]:
    """批量探测多个端口的协议（供卡片徽章一次取回全部结果）。

    :param host: 探测主机（访问地址的主机部分）
    :param items: ``[(port, container_id, container_port), ...]``
    :return: ``{port: 'http' | 'https' | 'unknown'}``

    16 并发并行探测；探测 unknown 时按端口号兜底推断（容器端口优先于主机端口）。
    """
    if not items:
        return {}

    def _one(item: tuple[int, str | None, int | None]) -> tuple[int, str]:
        port, container_id, container_port = item
        scheme = probe_scheme(host, port, container_id)
        if scheme == "unknown":
            scheme = port_scheme_fallback(container_port, port) or "unknown"
        return port, scheme

    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        for port, scheme in pool.map(_one, items):
            results[port] = scheme
    return results


def clear_cache() -> None:
    """清空探测缓存（测试用）。"""
    with _LOCK:
        _CACHE.clear()
