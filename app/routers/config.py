"""配置与隐藏端口路由。"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.config import (
    load_config,
    load_hidden_ports,
    load_raw_config,
    save_config,
    save_hidden_ports,
    save_raw_config,
)
from app.models import APIResponse, HiddenPortRequest, HiddenPortsBatchRequest, PortEditRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=APIResponse)
def api_get_config() -> APIResponse:
    """获取当前配置（原始 JSON 格式）。"""
    try:
        raw = load_raw_config()
        return APIResponse(success=True, data=raw)
    except Exception as e:  # noqa: BLE001
        logger.error("获取配置失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("", response_model=APIResponse)
def api_save_config(payload: dict) -> APIResponse:
    """整份保存配置（设置界面「保存」按钮）。"""
    try:
        if not isinstance(payload, dict):
            return APIResponse(success=False, error="配置必须是 JSON 对象")

        # 校验每个条目
        for key, value in payload.items():
            if not isinstance(value, str):
                return APIResponse(success=False, error=f"配置项 {key} 的值必须是字符串")
            if ":" not in key:
                return APIResponse(success=False, error=f"配置项 {key} 格式错误，应为「服务名:docker/host」")
            service_type = key.rsplit(":", 1)[-1]
            if service_type not in ("docker", "host"):
                return APIResponse(success=False, error=f"配置项 {key} 的服务类型必须是 docker 或 host")
            parts = value.split(":")
            if len(parts) < 2:
                return APIResponse(success=False, error=f"配置项 {key} 的值格式错误，应为「端口:协议」")
            try:
                port = int(parts[0])
            except ValueError:
                return APIResponse(success=False, error=f"配置项 {key} 的端口号必须是数字")
            if not 1 <= port <= 65535:
                return APIResponse(success=False, error=f"配置项 {key} 的端口号超出范围 (1-65535)")
            if parts[1].upper() not in ("TCP", "UDP"):
                return APIResponse(success=False, error=f"配置项 {key} 的协议必须是 TCP 或 UDP")

        if save_raw_config(payload):
            return APIResponse(success=True, message="配置已保存")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:  # noqa: BLE001
        logger.error("保存配置失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/edit", response_model=APIResponse)
def api_edit_port(req: PortEditRequest) -> APIResponse:
    """编辑单个端口的服务名（卡片「编辑」按钮）。"""
    try:
        raw = load_raw_config()

        # 找到对应端口的条目并更新
        found = False
        for key in list(raw.keys()):
            parts = str(raw[key]).split(":")
            if parts and parts[0] == str(req.port):
                service_type = key.rsplit(":", 1)[-1] if ":" in key else req.service_type
                raw[f"{req.service_name}:{service_type}"] = f"{req.port}:{parts[1] if len(parts) > 1 else 'tcp'}"
                # 如果 key 变了，删掉旧 key
                if key != f"{req.service_name}:{service_type}":
                    del raw[key]
                found = True
                break

        if not found:
            # 端口不存在，新增
            raw[f"{req.service_name}:{req.service_type}"] = f"{req.port}:tcp"

        if save_raw_config(raw):
            return APIResponse(success=True, message=f"端口 {req.port} 已更新为 {req.service_name}")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:  # noqa: BLE001
        logger.error("编辑端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


# ------------------------------------------------------------------ #
# 隐藏端口
# ------------------------------------------------------------------ #
@router.get("/hidden", response_model=APIResponse)
def api_get_hidden() -> APIResponse:
    """获取隐藏端口列表。"""
    try:
        hidden = load_hidden_ports()
        return APIResponse(success=True, data=hidden)
    except Exception as e:  # noqa: BLE001
        logger.error("获取隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/hidden", response_model=APIResponse)
def api_hide_port(req: HiddenPortRequest) -> APIResponse:
    """隐藏单个端口。"""
    try:
        hidden = load_hidden_ports()
        if req.port not in hidden:
            hidden.append(req.port)
            hidden.sort()
        if save_hidden_ports(hidden):
            return APIResponse(success=True, message=f"端口 {req.port} 已隐藏")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:  # noqa: BLE001
        logger.error("隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.delete("/hidden/{port}", response_model=APIResponse)
def api_unhide_port(port: int) -> APIResponse:
    """取消隐藏单个端口。"""
    try:
        hidden = load_hidden_ports()
        hidden = [p for p in hidden if p != port]
        if save_hidden_ports(hidden):
            return APIResponse(success=True, message=f"端口 {port} 已取消隐藏")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:  # noqa: BLE001
        logger.error("取消隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/hidden/batch", response_model=APIResponse)
def api_batch_hide(req: HiddenPortsBatchRequest) -> APIResponse:
    """批量隐藏端口。"""
    try:
        hidden = set(load_hidden_ports())
        hidden.update(req.ports)
        hidden_list = sorted(hidden)
        if save_hidden_ports(hidden_list):
            return APIResponse(success=True, message=f"已隐藏 {len(req.ports)} 个端口")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:  # noqa: BLE001
        logger.error("批量隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))


@router.post("/hidden/unhide/batch", response_model=APIResponse)
def api_batch_unhide(req: HiddenPortsBatchRequest) -> APIResponse:
    """批量取消隐藏端口。"""
    try:
        hidden = load_hidden_ports()
        to_remove = set(req.ports)
        hidden = [p for p in hidden if p not in to_remove]
        if save_hidden_ports(hidden):
            return APIResponse(success=True, message=f"已取消隐藏 {len(req.ports)} 个端口")
        return APIResponse(success=False, error="保存失败")
    except Exception as e:  # noqa: BLE001
        logger.error("批量取消隐藏端口失败: %s", e)
        return APIResponse(success=False, error=str(e))
