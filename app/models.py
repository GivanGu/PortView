"""API 数据模型（Pydantic）。

端口卡片有两种形态，用一个带可选字段的统一模型表达，保持与旧版
Flask 版本完全一致的 JSON 契约，前端无需改动字段名：

- ``used``  单个已占用端口（含未知服务，逐端口独立展示）
- ``gap``   可用端口范围
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PortCard(BaseModel):
    """单个端口卡片。

    不同 ``type`` 使用不同字段子集，其余字段为 ``None``。
    """

    model_config = ConfigDict(extra="ignore")

    type: Literal["used", "gap"]

    # --- used ---
    port: int | None = None
    source: str | None = Field(default=None, description="docker / system")
    protocol: str | None = None
    container: str | None = None
    container_id: str | None = None
    service_name: str | None = None
    process: str | None = None
    image: str | None = None
    container_port: str | None = None
    is_running: bool | None = None
    container_status: str | None = None
    is_host_network: bool | None = None

    # --- gap ---
    start_port: int | None = None
    end_port: int | None = None
    available_count: int | None = None

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


class ProbeSchemeRequest(BaseModel):
    """服务链接协议探测请求：给定主机端口（+ 可选容器 ID / 容器端口），判定 http/https/unknown。"""

    port: int = Field(ge=1, le=65535)
    container_id: str | None = None
    container_port: int | None = Field(default=None, ge=0, le=65535)


class ProbeSchemeItem(BaseModel):
    """批量探测中的单个端口条目。"""

    port: int = Field(ge=1, le=65535)
    container_id: str | None = None
    container_port: int | None = Field(default=None, ge=0, le=65535)


class ProbeSchemesRequest(BaseModel):
    """批量协议探测请求：卡片徽章一次取回所有端口卡片的 http/https。"""

    items: list[ProbeSchemeItem]


class PortSchemeRequest(BaseModel):
    """人工指定端口协议请求（探测不准时手动覆盖，优先级高于自动探测）。"""

    port: int = Field(ge=1, le=65535)
    scheme: Literal["http", "https"]


class HiddenPortsBatchRequest(BaseModel):
    """批量隐藏 / 取消隐藏请求。"""

    ports: list[int]


# ── P1-2 用户偏好 ─────────────────────────────────────────


class UserPrefsRead(BaseModel):
    """读取用户偏好（主题 / 强调色 / 语言 / 刷新间隔）。"""

    theme: Literal["dark", "light"]
    accent: str
    lang: Literal["zh", "en"]
    refresh_interval: int = 0
    logo_scrim: Literal["none", "left", "overlay", "glass"] = "left"
    logo_display_mode: Literal["background", "box"] = "background"
    # 收藏网格（v1.6.5）：GridItem 数组（port/url 条目 + 文件夹），后端透传不解析
    favorites: list = []
    # 默认主页（v1.6.6）：启动时打开的标签页
    default_tab: str = "favorites"
    # 背景图作用域（v1.6.6）：favorites=仅收藏页 / all=全应用
    background_scope: str = "favorites"
    # 背景图模糊度（v1.6.6）：px，0-30，默认 10
    background_blur: int = 10


class UserPrefsPatch(BaseModel):
    """局部更新用户偏好，未提供的字段不修改。"""

    theme: Literal["dark", "light"] | None = None
    accent: str | None = None
    lang: Literal["zh", "en"] | None = None
    refresh_interval: int | None = Field(default=None, ge=0, le=300)
    logo_scrim: Literal["none", "left", "overlay", "glass"] | None = None
    logo_display_mode: Literal["background", "box"] | None = None
    # 收藏网格（v1.6.5）：GridItem 数组，后端透传不解析
    favorites: list | None = None
    # 默认主页 / 背景作用域（v1.6.6）：str + 路由内白名单校验（同 accent 惯例）
    default_tab: str | None = None
    background_scope: str | None = None
    # 背景图模糊度（v1.6.6）：px，0-30
    background_blur: int | None = Field(default=None, ge=0, le=30)


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


class LogoFetchRequest(BaseModel):
    """外部 URL favicon 抓取（v1.6.5）：服务端从 URL 的 origin 抓取 favicon，存为 ``app_key``。"""

    app_key: str
    url: str = Field(..., max_length=2048)
