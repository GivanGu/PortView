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


class AccessAddressRequest(BaseModel):
    """全局访问地址保存请求（如 http://192.168.31.1）。空字符串表示清除。"""

    address: str = ""


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
    """读取用户偏好（主题 / 强调色 / 语言 / 刷新间隔）。"""

    theme: Literal["dark", "light"]
    accent: str
    lang: Literal["zh", "en"]
    refresh_interval: int = 0
    logo_scrim: Literal["none", "left", "overlay", "glass"] = "left"
    logo_display_mode: Literal["background", "box"] = "background"


class UserPrefsPatch(BaseModel):
    """局部更新用户偏好，未提供的字段不修改。"""

    theme: Literal["dark", "light"] | None = None
    accent: str | None = None
    lang: Literal["zh", "en"] | None = None
    refresh_interval: int | None = Field(default=None, ge=0, le=300)
    logo_scrim: Literal["none", "left", "overlay", "glass"] | None = None
    logo_display_mode: Literal["background", "box"] | None = None


# ── v1.5.0 应用 Logo ──────────────────────────────────────


class LogoMeta(BaseModel):
    """单个应用 Logo 的元信息（不含图片字节，用于列表 / 详情）。"""

    app_key: str
    status: Literal["found", "not_found"]
    mime: str | None = None
    created_at: int = 0
    updated_at: int = 0


class LogoRead(BaseModel):
    """单个应用 Logo 完整记录（含 base64 图片数据）。"""

    app_key: str
    status: Literal["found", "not_found"]
    mime: str | None = None
    data: str | None = Field(default=None, description="base64 编码的图片字节；not_found 时为 null")
    created_at: int = 0
    updated_at: int = 0


class DiscoverRequest(BaseModel):
    """自动识别 Logo 请求：给定 app_key 与端口，服务端抓取该服务自身的 favicon。"""

    app_key: str
    port: int = Field(default=0, ge=0, le=65535)
    path: str = "/"


class LogoUploadRequest(BaseModel):
    """手动上传 / 替换 Logo：``data`` 为 base64 编码的图片字节。"""

    mime: str
    data: str
