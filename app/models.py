"""API 数据模型（Pydantic）。

端口卡片有三种形态，用一个带可选字段的统一模型表达，保持与旧版
Flask 版本完全一致的 JSON 契约，前端无需改动字段名：

- ``used``          单个已占用端口
- ``gap``           可用端口范围
- ``unknown_range`` 连续未知服务端口（合并展示）
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PortCard(BaseModel):
    """单个端口卡片。"""
    model_config = ConfigDict(extra="ignore")

    type: Literal["used", "gap", "unknown_range"]

    # --- used ---
    port: int | None = None
    source: str | None = Field(default=None, description="docker / system")
    protocol: str | None = None
    container: str | None = None
    service_name: str | None = None
    process: str | None = None
    image: str | None = None
    container_port: str | None = None
    is_running: bool | None = None
    container_status: str | None = None
    is_host_network: bool | None = None

    # --- gap / unknown_range ---
    start_port: int | None = None
    end_port: int | None = None
    available_count: int | None = None
    port_count: int | None = None

    # --- 新增 ---
    conflict: bool | None = None
    conflict_sources: list[str] | None = None
    is_virtual: bool | None = None


class PortAnalysis(BaseModel):
    """一次端口分析的完整结果。"""
    port_cards: list[PortCard]
    total_used: int
    total_available: int
    tcp_used: int
    udp_used: int
    docker_containers: int
    hidden_ports: list[int]
    protocol_filter: str | None = None
    start_port: int = 1
    end_port: int = 65535
    next_cursor: str | None = None
    has_more: bool = False


class PortCard(BaseModel):
    """单个端口卡片。

    不同 ``type`` 使用不同字段子集，其余字段为 ``None``。
    """

    model_config = ConfigDict(extra="ignore")

    type: Literal["used", "gap", "unknown_range"]

    # --- used ---
    port: int | None = None
    source: str | None = Field(default=None, description="docker / system")
    protocol: str | None = None
    container: str | None = None
    service_name: str | None = None
    process: str | None = None
    image: str | None = None
    container_port: str | None = None
    is_running: bool | None = None
    container_status: str | None = None
    is_host_network: bool | None = None

    # --- gap / unknown_range ---
    start_port: int | None = None
    end_port: int | None = None
    available_count: int | None = None
    port_count: int | None = None

    # --- 前端虚拟卡片（已隐藏但当前不在数据中）---
    is_virtual: bool | None = None


class PortAnalysis(BaseModel):
    """一次端口分析的完整结果。"""

    port_cards: list[PortCard]
    total_used: int
    total_available: int
    tcp_used: int
    udp_used: int
    docker_containers: int
    hidden_ports: list[int]
    protocol_filter: str | None = None


class APIResponse(BaseModel):
    """统一 API 响应包裹。"""

    success: bool
    data: Any | None = None
    error: str | None = None
    message: str | None = None


class PortEditRequest(BaseModel):
    """单个端口的服务名编辑请求。"""

    port: int
    service_name: str
    service_type: Literal["docker", "host"] = "host"


class HiddenPortRequest(BaseModel):
    """单个端口隐藏 / 取消隐藏请求。"""

    port: int


class HiddenPortsBatchRequest(BaseModel):
    """批量隐藏 / 取消隐藏请求。"""
    ports: list[int]


# ------------------------------------------------------------------ #
# 自定义监控区间
# ------------------------------------------------------------------ #
class PortRangeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=32, description="区间名称")
    start_port: int = Field(..., ge=1, le=65535)
    end_port: int = Field(..., ge=1, le=65535)
    color: str = Field(default="#00b4d8", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("end_port")
    @classmethod
    def _end_ge_start(cls, v: int, info) -> int:
        start = info.data.get("start_port")
        if start is not None and v < start:
            raise ValueError("end_port 必须 >= start_port")
        return v


class PortRangeCreate(PortRangeBase):
    pass


class PortRangeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=32)
    start_port: Optional[int] = Field(None, ge=1, le=65535)
    end_port: Optional[int] = Field(None, ge=1, le=65535)
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class PortRange(PortRangeBase):
    """自定义监控区间（持久化）。"""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
