"""配置与隐藏端口路由（v1.6.12 起全部落 SQLite）。"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Depends

from app.config import (
    load_access_address,
    load_config,
    load_hidden_ports,
    save_access_address,
    save_hidden_ports,
)
from app.dependencies import get_monitor
from app.models import (
    AccessAddressRequest,
    APIResponse,
    HiddenPortRequest,
    HiddenPortsBatchRequest,
    PortEditRequest,
)
from app.services import db as db_service
from app.services.port_monitor import PortMonitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/access_address", response_model=APIResponse)
async def api_get_access_address() -> APIResponse:
    """获取全局访问地址（如 192.168.31.1）。"""
    try:
        return APIResponse(success=True, data={"address": await load_access_address()})
    except Exception as e:
        logger.error("获取访问地址失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/access_address", response_model=APIResponse)
async def api_save_access_address(req: AccessAddressRequest) -> APIResponse:
    """保存全局访问地址。空字符串表示清除。

    裸 IP / 域名（无协议前缀）会自动补 ``http://``，响应里回传规范化后的地址，
    供前端即时回填输入框。
    """
    try:
        if await save_access_address(req.address):
            return APIResponse(
                success=True,
                data={"address": await load_access_address()},
                message="访问地址已保存",
            )
        return APIResponse(success=False, error="保存失败")
    except Exception as e:
        logger.error("保存访问地址失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/edit", response_model=APIResponse)
async def api_edit_port(req: PortEditRequest) -> APIResponse:
    """编辑单个端口的服务名（卡片「编辑」按钮）。

    端口为主键 upsert：只影响该端口一行；服务名非唯一，
    同一名字可绑多端口（如一个应用的 http + https 共用名字）。
    """
    try:
        conn = db_service.get_db()
        if conn is None:
            return APIResponse(success=False, error="数据库未就绪")
        now = int(time.time())
        await conn.execute(
            "INSERT INTO port_labels (port, service_name, port_type, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(port) DO UPDATE SET "
            "service_name = excluded.service_name, "
            "port_type = excluded.port_type, "
            "updated_at = excluded.updated_at",
            (req.port, req.service_name, req.service_type, now, now),
        )
        await conn.commit()
        return APIResponse(success=True, message=f"端口 {req.port} 已更新为 {req.service_name}")
    except Exception as e:
        logger.error("编辑端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


# ------------------------------------------------------------------ #
# 隐藏端口
# ------------------------------------------------------------------ #
@router.get("/hidden", response_model=APIResponse)
async def api_get_hidden() -> APIResponse:
    """获取隐藏端口列表。"""
    try:
        hidden = await load_hidden_ports()
        return APIResponse(success=True, data=hidden)
    except Exception as e:
        logger.error("获取隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.get("/hidden/details", response_model=APIResponse)
async def api_get_hidden_details(monitor: PortMonitor = Depends(get_monitor)) -> APIResponse:
    """获取隐藏端口的详细信息（服务名 / 协议 / 来源 / 容器）。

    隐藏端口只存了端口号；这里重新跑一次分析（不过滤隐藏），
    把每个隐藏端口能还原出的字段都带出来。当前未监听的端口，
    仅能从标注 / 默认映射推断服务名。
    """
    try:
        hidden = await load_hidden_ports()
        if not hidden:
            return APIResponse(success=True, data=[])

        config = await load_config()
        # 阻塞的 Docker SDK + psutil 调用放到线程池
        port_data = await asyncio.to_thread(
            monitor.get_port_analysis,
            config,
            start_port=1,
            end_port=65535,
            hidden_ports=[],  # 不过滤，拿到全部卡片
        )

        card_by_port: dict[int, dict] = {}
        for card in port_data["port_cards"]:
            if card.get("type") == "used" and card.get("port"):
                card_by_port[card["port"]] = card

        details: list[dict] = []
        for port in sorted(hidden):
            card = card_by_port.get(port)
            if card:
                details.append(
                    {
                        "port": port,
                        "service_name": card.get("service_name"),
                        "protocol": card.get("protocol"),
                        "source": card.get("source"),
                        "container": card.get("container"),
                        "image": card.get("image"),
                        "is_running": card.get("is_running"),
                    }
                )
            else:
                details.append(
                    {
                        "port": port,
                        "service_name": monitor.get_service_name(port, config),
                        "protocol": None,
                        "source": None,
                        "container": None,
                        "image": None,
                        "is_running": False,
                    }
                )
        return APIResponse(success=True, data=details)
    except Exception as e:
        logger.error("获取隐藏端口详情失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/hidden", response_model=APIResponse)
async def api_hide_port(req: HiddenPortRequest) -> APIResponse:
    """隐藏单个端口。"""
    try:
        hidden = await load_hidden_ports()
        if req.port not in hidden:
            hidden.append(req.port)
            hidden.sort()
        if await save_hidden_ports(hidden):
            return APIResponse(success=True, message=f"端口 {req.port} 已隐藏")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:
        logger.error("隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.delete("/hidden/{port}", response_model=APIResponse)
async def api_unhide_port(port: int) -> APIResponse:
    """取消隐藏单个端口。"""
    try:
        hidden = await load_hidden_ports()
        hidden = [p for p in hidden if p != port]
        if await save_hidden_ports(hidden):
            return APIResponse(success=True, message=f"端口 {port} 已取消隐藏")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:
        logger.error("取消隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/hidden/batch", response_model=APIResponse)
async def api_batch_hide(req: HiddenPortsBatchRequest) -> APIResponse:
    """批量隐藏端口。"""
    try:
        hidden = set(await load_hidden_ports())
        hidden.update(req.ports)
        if await save_hidden_ports(sorted(hidden)):
            return APIResponse(success=True, message=f"已隐藏 {len(req.ports)} 个端口")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:
        logger.error("批量隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/hidden/unhide/batch", response_model=APIResponse)
async def api_batch_unhide(req: HiddenPortsBatchRequest) -> APIResponse:
    """批量取消隐藏端口。"""
    try:
        hidden = await load_hidden_ports()
        to_remove = set(req.ports)
        hidden = [p for p in hidden if p not in to_remove]
        if await save_hidden_ports(hidden):
            return APIResponse(success=True, message=f"已取消隐藏 {len(req.ports)} 个端口")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:
        logger.error("批量取消隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))
