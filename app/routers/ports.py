"""端口查询 / 刷新路由。"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Query

from app.config import load_access_host, load_config, load_hidden_ports
from app.dependencies import get_monitor
from app.models import APIResponse, PortSchemeRequest, ProbeSchemeRequest, ProbeSchemesRequest
from app.services import db as db_service
from app.services import scheme_probe
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


async def _filter_cards_by_ports(port_data: dict, ports: set[int] | None) -> dict:
    """把 port_cards 过滤到给定端口集合内。ports 为 None → 原样返回。"""
    if ports is None:
        return port_data
    filtered: list[dict] = []
    for card in port_data["port_cards"]:
        t = card.get("type")
        if t == "used":
            if card.get("port") in ports:
                filtered.append(card)
        elif t == "gap":
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
    port_data["total_used"] = len([c for c in filtered if c.get("type") == "used"])
    # v1.4.5：按区间收窄后，可用端口数也要跟着收窄（此前沿用全段值，
    # 导致选中区间时统计栏「可用端口」与「已用端口」口径不一致）。
    port_data["total_available"] = sum(
        c.get("available_count", 0) for c in filtered if c.get("type") == "gap"
    )
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
        notes_map = await _load_notes_map()
        # 阻塞的 Docker SDK + psutil 调用放到线程池，避免卡住事件循环
        port_data = await asyncio.to_thread(
            monitor.get_port_analysis,
            config,
            start_port=start_port,
            end_port=end_port,
            protocol_filter=protocol_filter,
            hidden_ports=hidden_ports,
            notes_map=notes_map,
        )

        # P1.1：按监控区间收窄
        port_data = await _filter_cards_by_ports(port_data, await _resolve_range_ids(range_ids))

        search_term = search.strip().lower()
        if search_term:
            port_data = _apply_search(port_data, search_term)

        return APIResponse(success=True, data=port_data)
    except Exception as e:
        logger.error("API 调用失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/refresh", response_model=APIResponse)
async def api_refresh(monitor: PortMonitor = Depends(get_monitor)) -> APIResponse:
    """刷新端口信息（重连 Docker + 重新分析）。"""
    try:
        # Docker 客户端重连是阻塞 I/O，放到线程池
        await asyncio.to_thread(monitor.reconnect)
        config = load_config()
        hidden_ports = load_hidden_ports()
        notes_map = await _load_notes_map()
        port_data = await asyncio.to_thread(
            monitor.get_port_analysis,
            config,
            hidden_ports=hidden_ports,
            notes_map=notes_map,
        )
        return APIResponse(success=True, data=port_data, message="端口信息已刷新")
    except Exception as e:
        logger.error("刷新失败: %s", e)
        return APIResponse(success=False, error=str(e))


def _probe_hosts() -> list[str]:
    """构造探测主机列表：访问地址优先（与浏览器访问目标一致），
    127.0.0.1 兜底（host 网络下即宿主机回环，覆盖只监听回环的服务）。"""
    hosts: list[str] = []
    access = load_access_host()
    if access:
        hosts.append(access)
    if "127.0.0.1" not in hosts:
        hosts.append("127.0.0.1")
    return hosts


@router.post("/ports/probe_scheme", response_model=APIResponse)
async def api_probe_scheme(req: ProbeSchemeRequest) -> APIResponse:
    """探测某主机端口对外提供的协议（http/https/unknown）。

    按「访问地址 → 127.0.0.1」顺序尝试，取第一个能判定的结果。
    阻塞 socket 通过 asyncio.to_thread 跑，避免卡事件循环。
    """
    try:
        hosts = _probe_hosts()
        scheme = await asyncio.to_thread(
            scheme_probe.probe_scheme, hosts, req.port, req.container_id
        )
        if scheme == "unknown":
            scheme = scheme_probe.port_scheme_fallback(req.container_port, req.port) or "unknown"
        return APIResponse(success=True, data={"scheme": scheme, "host": hosts[0]})
    except Exception as e:
        logger.error("协议探测失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/ports/probe_schemes", response_model=APIResponse)
async def api_probe_schemes(req: ProbeSchemesRequest) -> APIResponse:
    """批量探测多个主机端口的协议（卡片 http/https 徽章一次取回）。

    按「访问地址 → 127.0.0.1」顺序尝试；后端 16 并发并行探测；
    unknown 时按端口号兜底（容器端口优先）。
    """
    try:
        hosts = _probe_hosts()
        items = [(i.port, i.container_id, i.container_port) for i in req.items]
        schemes = await asyncio.to_thread(scheme_probe.probe_schemes_batch, hosts, items)
        return APIResponse(success=True, data={"schemes": schemes, "host": hosts[0]})
    except Exception as e:
        logger.error("批量协议探测失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.get("/ports/schemes", response_model=APIResponse)
async def api_get_schemes() -> APIResponse:
    """获取全部人工指定的端口协议（{port: scheme}）。

    人工指定优先级高于自动探测；前端据此覆盖徽章与打开链接。
    """
    try:
        conn = db_service.get_db()
        if conn is None:
            return APIResponse(success=True, data={})
        cur = await conn.execute("SELECT port, scheme FROM port_schemes ORDER BY port ASC")
        rows = await cur.fetchall()
        return APIResponse(success=True, data={str(r["port"]): r["scheme"] for r in rows})
    except Exception as e:
        logger.error("读取人工协议失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/ports/scheme", response_model=APIResponse)
async def api_set_scheme(req: PortSchemeRequest) -> APIResponse:
    """人工指定某端口的协议（http/https），覆盖自动探测结果。"""
    try:
        conn = db_service.get_db()
        if conn is None:
            return APIResponse(success=False, error="db not ready")
        import time

        now = int(time.time())
        await conn.execute(
            "INSERT INTO port_schemes (port, scheme, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(port) DO UPDATE SET scheme = excluded.scheme, updated_at = excluded.updated_at",
            (req.port, req.scheme, now),
        )
        await conn.commit()
        return APIResponse(success=True, message=f"端口 {req.port} 已指定为 {req.scheme}")
    except Exception as e:
        logger.error("保存人工协议失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.delete("/ports/scheme/{port}", response_model=APIResponse)
async def api_clear_scheme(port: int) -> APIResponse:
    """清除某端口的人工指定，恢复自动探测。"""
    try:
        conn = db_service.get_db()
        if conn is None:
            return APIResponse(success=False, error="db not ready")
        await conn.execute("DELETE FROM port_schemes WHERE port = ?", (port,))
        await conn.commit()
        return APIResponse(success=True, message=f"端口 {port} 已恢复自动检测")
    except Exception as e:
        logger.error("清除人工协议失败: %s", e)
        return APIResponse(success=False, error=str(e))


def _apply_search(port_data: dict, search_term: str) -> dict:
    """按关键词过滤端口卡片（移植自旧版前端/后端搜索逻辑）。"""
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
                    card.get("remark", "") or "",  # P1.1：备注也纳入搜索
                ]
            ).lower()
            if search_term in text:
                filtered.append(card)
        elif card["type"] == "gap":
            text = " ".join(
                [
                    f"{card.get('start_port', '')}-{card.get('end_port', '')}",
                    str(card.get("start_port", "")),
                    str(card.get("end_port", "")),
                    card.get("service_name", "") or "",
                    card.get("container", "") or "",
                    card.get("protocol", "") or "",
                    "可用",
                    "available",
                    "unused",
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
    filtered_used = len([c for c in filtered if c["type"] == "used"])

    port_data["port_cards"] = filtered
    port_data["total_used"] = filtered_used
    # total_available 是「区间内可用端口」，属于区间属性，不随搜索词变化；
    # 保留 get_port_analysis 计算出的原值（此前误用硬编码 65535 重算，
    # 在协议过滤 / 自定义区间下会与 total_used 口径不一致）。
    return port_data
