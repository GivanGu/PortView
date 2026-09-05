"""端口查询 / 刷新路由。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from app.config import load_config, load_hidden_ports
from app.dependencies import get_monitor
from app.models import APIResponse
from app.services import db as db_service
from app.services.port_monitor import PortMonitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["ports"])


async def _load_notes_map() -> dict[int, str]:
    """从 port_notes 表读 {port: remark}。P1.1 起用于给卡片打 remark。"""
    conn = db_service.get_db()
    if conn is None:
        return {}
    cur = await conn.execute("SELECT port, remark FROM port_notes")
    rows = await cur.fetchall()
    return {r["port"]: (r["remark"] or "") for r in rows if r["remark"]}


async def _resolve_range_ids(range_ids: list[int]) -> set[int] | None:
    """把 range_rules.id 列表展平为端口集合。空/无效 → None（表示不限制）。"""
    if not range_ids:
        return None
    conn = db_service.get_db()
    if conn is None:
        return None
    cur = await conn.execute(
        "SELECT start_port, end_port FROM range_rules WHERE id IN ({})".format(
            ",".join("?" * len(range_ids))
        ),
        range_ids,
    )
    rows = await cur.fetchall()
    if not rows:
        return set()  # 显式空集合 → 过滤掉所有卡片
    union: set[int] = set()
    for r in rows:
        union.update(range(r["start_port"], r["end_port"] + 1))
    return union


async def _filter_cards_by_ports(
    port_data: dict, ports: set[int] | None
) -> dict:
    """把 port_cards 过滤到给定端口集合内。ports 为 None → 原样返回。"""
    if ports is None:
        return port_data
    filtered: list[dict] = []
    for card in port_data["port_cards"]:
        t = card.get("type")
        if t == "used":
            if card.get("port") in ports:
                filtered.append(card)
        elif t in ("unknown_range", "gap"):
            sp = card.get("start_port", 0)
            ep = card.get("end_port", 0)
            # 区间与 ports 集合有交集 → 收窄到交集区间
            hit_ports = sorted({p for p in ports if sp <= p <= ep})
            if not hit_ports:
                continue
            new_card = dict(card)
            new_card["start_port"] = hit_ports[0]
            new_card["end_port"] = hit_ports[-1]
            if "available_count" in new_card:
                new_card["available_count"] = new_card["end_port"] - new_card["start_port"] + 1
            filtered.append(new_card)
    filtered.sort(key=lambda c: c.get("port", c.get("start_port", 0)))
    port_data["port_cards"] = filtered
    port_data["total_used"] = len([c for c in filtered if c.get("type") in ("used", "unknown_range")])
    return port_data



@router.get("/ports", response_model=APIResponse)
async def api_ports(
    monitor: PortMonitor = Depends(get_monitor),
    protocol: str = Query("", description="协议过滤：TCP / UDP / 空"),
    start_port: int = Query(1, ge=0, le=65535),
    end_port: int = Query(65535, ge=0, le=65535),
    search: str = Query("", description="搜索端口 / 服务名 / 容器名 / 备注"),
    range_ids: list[int] = Query([], description="监控区间 id 列表；空=全段，非空=仅这些区间"),
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
            notes_map=await _load_notes_map(),
        )

        # P1.1：按监控区间收窄
        port_data = await _filter_cards_by_ports(
            port_data, await _resolve_range_ids(range_ids)
        )

        search_term = search.strip().lower()
        if search_term:
            port_data = _apply_search(port_data, search_term)

        return APIResponse(success=True, data=port_data)
    except Exception as e:  # noqa: BLE001
        logger.error("API 调用失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/refresh", response_model=APIResponse)
async def api_refresh(monitor: PortMonitor = Depends(get_monitor)) -> APIResponse:
    """刷新端口信息（重连 Docker + 重新分析）。"""
    try:
        monitor.reconnect()
        config = load_config()
        hidden_ports = load_hidden_ports()
        port_data = monitor.get_port_analysis(
            config=config,
            hidden_ports=hidden_ports,
            notes_map=await _load_notes_map(),
        )
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
                    card.get("remark", "") or "",   # P1.1：备注也纳入搜索
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
