"""端口查询 / 刷新路由。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from app.config import load_config, load_hidden_ports
from app.dependencies import get_monitor
from app.models import APIResponse
from app.services.port_monitor import PortMonitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["ports"])


@router.get("/ports", response_model=APIResponse)
def api_ports(
    monitor: PortMonitor = Depends(get_monitor),
    protocol: str = Query("", description="协议过滤：TCP / UDP / 空"),
    start_port: int = Query(1, ge=0, le=65535),
    end_port: int = Query(65535, ge=0, le=65535),
    search: str = Query("", description="搜索端口 / 服务名 / 容器名"),
) -> APIResponse:
    """获取端口信息。"""
    try:
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
        port_data = monitor.get_port_analysis(
            config,
            start_port=start_port,
            end_port=end_port,
            protocol_filter=protocol_filter,
            hidden_ports=hidden_ports,
        )

        search_term = search.strip().lower()
        if search_term:
            port_data = _apply_search(port_data, search_term)

        return APIResponse(success=True, data=port_data)
    except Exception as e:  # noqa: BLE001
        logger.error("API 调用失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/refresh", response_model=APIResponse)
def api_refresh(monitor: PortMonitor = Depends(get_monitor)) -> APIResponse:
    """刷新端口信息（重连 Docker + 重新分析）。"""
    try:
        monitor.reconnect()
        config = load_config()
        hidden_ports = load_hidden_ports()
        port_data = monitor.get_port_analysis(config=config, hidden_ports=hidden_ports)
        return APIResponse(success=True, data=port_data, message="端口信息已刷新")
    except Exception as e:  # noqa: BLE001
        logger.error("刷新失败: %s", e)
        return APIResponse(success=False, error=str(e))


def _apply_search(port_data: dict, search_term: str) -> dict:
    """按关键词过滤端口卡片（移植自旧版前端/后端搜索逻辑）。"""
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
