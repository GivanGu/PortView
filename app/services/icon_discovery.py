"""应用 Logo 自动识别（v1.5.0）。

移植 dockfn ``internal/app/icon.go`` 的 ``DiscoverIcon`` 思路：
从「运行中服务自身」抓取 favicon，作为该应用的 logo。

算法：
1. 抓 ``http://{host}:{port}{path}`` 首页（``Range: bytes=0-65535`` 限流），
   解析 ``<link rel="icon|shortcut|apple-touch-icon">`` 的 ``href`` 作为首选候选（须同源）。
2. 兜底探测常见 favicon 路径（带 base path 前缀 + 不带，各试一遍）。
3. 逐个候选下载 → 魔数校验（PNG/JPEG/ICO/SVG/GIF/WebP，≤1MiB）→ 首个成功者返回。

不引入 Pillow：仅做魔数校验，浏览器原生渲染。
"""

from __future__ import annotations

import contextlib
import logging
import os
from html.parser import HTMLParser

import httpx

logger = logging.getLogger(__name__)

# 抓取目标主机：容器内访问宿主机端口。
# 默认 127.0.0.1（compose 用 network_mode: host，容器 loopback 即宿主机 loopback）；
# 若改用 bridge 网络，可设 PORTVIEW_DISCOVER_HOST=host.docker.internal（配合 extra_hosts）。
DISCOVER_HOST = os.environ.get("PORTVIEW_DISCOVER_HOST", "127.0.0.1")

MAX_SIZE = 1024 * 1024  # 1 MiB 上限（上传 / 抓取一致）
TIMEOUT = 3.0  # 单次请求超时（秒）
MAX_REDIRECTS = 3

# 兜底探测的常见 favicon 路径（相对站点根）
_FAVICON_PATHS = (
    "/favicon.ico",
    "/favicon.png",
    "/apple-touch-icon.png",
    "/logo.png",
    "/logo.svg",
    "/static/favicon.ico",
    "/assets/favicon.ico",
    "/img/favicon.ico",
)


def detect_mime(data: bytes) -> str | None:
    """按魔数识别图片类型，返回 mime；非图片返回 None。

    支持 PNG / JPEG / GIF / WebP / ICO / SVG。
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"\x00\x00\x01\x00":
        return "image/x-icon"
    # SVG 为文本：头部出现 <svg 或 <?xml ... svg
    head = data[:512].lstrip().lower()
    if b"<svg" in head or (head.startswith(b"<?xml") and b"svg" in head):
        return "image/svg+xml"
    return None


class _LinkIconParser(HTMLParser):
    """提取 ``<link rel="icon...">`` 的 href。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return
        d = {k.lower(): (v or "") for k, v in attrs}
        rel = d.get("rel", "").lower()
        if "icon" in rel:
            href = d.get("href", "").strip()
            if href:
                self.hrefs.append(href)


def _resolve_url(origin: str, href: str) -> str | None:
    """把 href 解析为绝对 URL；非同源（非 origin 前缀）返回 None。"""
    if href.startswith("http://") or href.startswith("https://"):
        return href if href.startswith(origin) else None
    if href.startswith("//"):
        url = "http:" + href
        return url if url.startswith(origin) else None
    if href.startswith("/"):
        return origin + href
    # 相对路径：拼到 origin 根下
    return origin + "/" + href.lstrip("/")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


async def discover_icon(host: str, port: int, base_path: str = "/") -> tuple[bytes, str] | None:
    """抓取 ``http://{host}:{port}`` 的 favicon，返回 ``(bytes, mime)`` 或 ``None``。

    任何网络错误 / 超时 / 无有效图片都静默返回 ``None``（由调用方落 ``not_found``）。
    """
    if not (1 <= port <= 65535):
        return None

    base_path = (base_path or "/").strip()
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    root = base_path.rstrip("/")
    origin = f"http://{host}:{port}"

    headers = {"User-Agent": "PortView/1.5 (+favicon-discovery)"}

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        verify=False,  # loopback / 自签证书跳过 TLS 校验
        headers=headers,
    ) as client:
        candidates: list[str] = []

        # 1. 抓首页，解析 <link rel=icon>
        try:
            r = await client.get(origin + root, headers={"Range": "bytes=0-65535"})
            if r.status_code < 400:
                body_head = r.content[:8192].lower()
                ctype = r.headers.get("content-type", "").lower()
                if "html" in ctype or b"<link" in body_head or b"<svg" in body_head:
                    parser = _LinkIconParser()
                    with contextlib.suppress(Exception):
                        parser.feed(r.text)
                    for href in parser.hrefs:
                        url = _resolve_url(origin, href)
                        if url:
                            candidates.append(url)
        except httpx.HTTPError:
            pass

        # 2. 兜底常见路径（带 base path 前缀 + 不带，各试一遍）
        for p in _FAVICON_PATHS:
            candidates.append(origin + root + p)
            candidates.append(origin + p)

        # 3. 逐个下载 → 魔数校验 → 首个成功者返回
        for url in _dedupe(candidates):
            try:
                r = await client.get(url)
            except httpx.HTTPError:
                continue
            if r.status_code not in (200, 206):
                continue
            data = r.content
            if not data or len(data) > MAX_SIZE:
                continue
            mime = detect_mime(data)
            if mime:
                logger.info(
                    "icon discovered for %s:%s -> %s (%d bytes)", host, port, mime, len(data)
                )
                return data, mime

    return None
