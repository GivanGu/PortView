"""服务链接协议探测：判定某端口对外提供的是 http 还是 https。

背景：访问地址是全局单一协议（默认 http），但同一台主机上可能同时跑 HTTP（80）
和 HTTPS（443）服务，单一协议无法同时适配。Docker 端口映射还会让主机端口与服务
实际端口解耦（如容器 443 → 主机 22500），仅凭端口号无法可靠推断。

方案：对目标端口发起最小 TLS ClientHello，按响应前缀三态判定：
- 收到 TLS 记录（0x16/0x15/0x14/0x17）→ https（对端是 TLS 服务）
- 收到明文 HTTP 状态行（``HTTP/``）→ http
- 超时 / 拒绝 / 其他（SSH、MySQL 等非 Web 服务）→ unknown（调用方回退默认协议）

「unknown 回退默认」保证探测的最坏情况 = 现状，绝不会比不探测更差。
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time

logger = logging.getLogger(__name__)

# 缓存：key=(port, container_id) → (scheme, timestamp)。
# 容器重部署（recreate）会产生新 container_id → key 变化 → 缓存未命中 → 立即重探。
# 宿主机 / 进程重启 → 内存缓存清空 → 无残留。
_TTL = 60.0
_CACHE: dict[tuple[int, str], tuple[str, float]] = {}
_LOCK = threading.Lock()


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
    """阻塞式探测：连 host:port，发 ClientHello，按响应前缀判定。

    返回 'https' / 'http' / 'unknown'。
    """
    try:
        with socket.create_connection((host, port), timeout=2.0) as sock:
            sock.settimeout(2.0)
            sock.sendall(_CLIENT_HELLO)
            data = sock.recv(5)
    except (TimeoutError, OSError):
        return "unknown"
    if not data:
        return "unknown"
    first = data[0]
    # TLS 记录类型：0x16 握手 / 0x15 alert / 0x14 change_cipher_spec / 0x17 application_data
    if first in (0x16, 0x15, 0x14, 0x17):
        return "https"
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


def clear_cache() -> None:
    """清空探测缓存（测试用）。"""
    with _LOCK:
        _CACHE.clear()
