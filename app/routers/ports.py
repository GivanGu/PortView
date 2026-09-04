"""端口查询 / 刷新路由。

使用新的服务层（DockerScanner、HostScanner、PortAnalyzer）替换旧的
PortMonitor。支持分页、搜索、协议过滤、自定义区间。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from app.config import load_config, load_custom_ranges, load_hidden_ports
from app.dependencies import get_port_analyzer
from app.models import APIResponse
from app.services.port_analyzer import PortAnalyzer
from app.services.notification_bus import NotificationBus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["ports"])


@router.get("/ports", response_model=APIResponse)
def api_ports(
    monitor: PortAnalyzer = Depends(get_port_analyzer),
    protocol: str = Query("", description="协议过滤：TCP / UDP / 空"),
    start_port: int = Query(1, ge=0, le=65535),
    end_port: int = Query(65535, ge=0, le=65535),
    search: str = Query("", description="搜索端口 / 服务名 / 容器名"),
    cursor: str = Query(None, description="分页游标（端口号）"),
    limit: int = Query(200, ge=1, le=5000, description="分页大小"),
    range_id: str = Query(None, description="自定义区间 ID"),
) -> APIResponse:
    """获取端口信息（支持分页、搜索、自定义区间）。

    - 若 ``range_id`` 指定了合法的自定义区间，覆盖 start_port/end_port
    - ``cursor`` 为上页末尾端口号；为 null 返回第一页
    - 返回的 port_cards 已做分页处理，total_* 统计基于**全量数据**
    """
    try:
        # 自定义区间覆盖
        if range_id:
            ranges = load_custom_ranges()
            r = next((x for x in ranges if x.get("id") == range_id), None)
            if r:
                start_port, end_port = r["start_port"], r["end_port"]

        # 参数清洗
        protocol_filter = protocol.strip().upper()
        if protocol_filter not in ("TCP", "UDP", ""):
            protocol_filter = None
        if start_port < 1:
            start_port = 1
        if end_port > 65535:
            end_port = 65535
        if start_port > end_port:
            start_port, end_port = end_port, start_port

        config = load_config()
        hidden_ports = load_hidden_ports()
        port_data = monitor.analyze(
            config,
            start_port=start_port,
            end_port=end_port,
            protocol_filter=protocol_filter,
            hidden_ports=hidden_ports,
        )

        # 搜索过滤
        search_term = search.strip().lower()
        if search_term:
            port_data = _apply_search(port_data, search_term)

        # 分页
        if cursor is not None:
            cursor_port = int(cursor) if cursor.isdigit() else None
        else:
            cursor_port = None

        all_cards = port_data["port_cards"]
        if cursor_port is not None:
            # 跳过游标位置之前的卡片
            skip_indices = 0
            running = 0
            for idx, c in enumerate(all_cards):
                c_port = c.get("port") or c.get("start_port", 0)
                if c_port <= cursor_port:
                    skip_indices = idx + 1
                    running = c_port
            all_cards = all_cards[skip_indices:]

        page_cards = all_cards[:limit]
        has_more = len(all_cards) > limit

        # next_cursor
        last_card = page_cards[-1] if page_cards else None
        next_cursor = None
        if has_more and last_card:
            next_cursor = str(last_card.get("port") or last_card.get("start_port", 0))

        port_data["port_cards"] = page_cards
        port_data["next_cursor"] = next_cursor
        port_data["has_more"] = has_more

        return APIResponse(success=True, data=port_data)
    except Exception as e:  # noqa: BLE001
        logger.error("API 调用失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/refresh", response_model=APIResponse)
def api_refresh(monitor: PortAnalyzer = Depends(get_port_analyzer)) -> APIResponse:
    """刷新端口信息（重连 Docker + 重新分析）。"""
    try:
        # 重新连接 Docker 扫描器
        monitor.docker_scanner.reconnect()

        # 记录容器启停变化
        bus = NotificationBus.get()
        new_ports = monitor.analyze(
            config=load_config(),
            hidden_ports=load_hidden_ports(),
        )

        # 检查冲突通知
        for card in new_ports.get("port_cards", []):
            if card.get("type") == "used" and card.get("conflict"):
                bus.push(
                    "port_conflict",
                    "error",
                    f"端口冲突: {card['port']}",
                    " | ".join(card.get("conflict_sources", [])),
                )

        return APIResponse(
            success=True,
            data=new_ports,
            message="端口信息已刷新",
        )
    except Exception as e:  # noqa: BLE001
        logger.error("刷新失败: %s", e)
        return APIResponse(success=False, error=str(e))


def _apply_search(port_data: dict, search_term: str) -> dict:
    """按关键词过滤端口卡片。"""
    original_total_used = port_data["total_used"]
    filtered: list[dict] = []

    for card in port_data["port_cards"]:
        if card["type"] == "used":
            text = " ".join(
                [
                    str(card.get("port", "")),
                    card.get("process", "") or "",
                    card.get("service_name", "") or "",
                    card.get("container", "") or "",
                    card.get("protocol", "") or "",
                ]
            ).lower()
            if search_term in text:
                filtered.append(card)
        elif card["type"] in ("unknown_range", "gap"):
            text = " ".join(
                [
                    f"{card.get('start_port', '')}-{card.get('end_port', '')}",
                    str(card.get("start_port", "")),
                    str(card.get("end_port", "")),
                    card.get("service_name", "") or "",
                    card.get("container", "") or "",
                    card.get("protocol", "") or "",
                    "可用", "available", "unused",
                ]
            ).lower()
            is_match = search_term in text
            if not is_match and search_term.isdigit():
                sp = int(search_term)
                if card.get("start_port", 0) <= sp <= card.get("end_port", 0):
                    is_match = True
            if is_match:
                filtered.append(card)

    filtered.sort(key=lambda x: x.get("port", x.get("start_port", 0)))
    filtered_used = len([c for c in filtered if c["type"] in ("used", "unknown_range")])

    port_data["port_cards"] = filtered
    port_data["total_used"] = filtered_used
    port_data["total_available"] = max(0, 65535 - original_total_used)
    return port_data
