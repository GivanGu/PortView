"""API 数据模型（Pydantic）。

端口卡片有三种形态，用一个带可选字段的统一模型表达，保持与旧版
Flask 版本完全一致的 JSON 契约，前端无需改动字段名：

- ``used``          单个已占用端口
- ``gap``           可用端口范围
- ``unknown_range`` 连续未知服务端口（合并展示）
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


# ── P1-1 端口备注 ─────────────────────────────────────────

class NoteCreateRequest(BaseModel):
    """新建 / 更新一条端口备注。``port`` 唯一，存在则 upsert。"""

    port: int = Field(ge=0, le=65535)
    service_name: str = ""
    protocol: Literal["", "tcp", "udp", "both"] = ""
    remark: str = Field(default="", max_length=1024, description="用户备注，自由文本")


class NoteRead(BaseModel):
    """返回给前端的备注记录。"""

    port: int
    service_name: str
    protocol: Literal["", "tcp", "udp", "both"]
    remark: str
    created_at: int
    updated_at: int


# ── P1-2 用户偏好 ─────────────────────────────────────────

class UserPrefsRead(BaseModel):
    """读取用户偏好（主题 / 强调色 / 语言）。"""

    theme: Literal["dark", "light"]
    accent: str
    lang: Literal["zh", "en"]


class UserPrefsPatch(BaseModel):
    """局部更新用户偏好，未提供的字段不修改。"""

    theme: Literal["dark", "light"] | None = None
    accent: str | None = None
    lang: Literal["zh", "en"] | None = None
