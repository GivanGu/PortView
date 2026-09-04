"""统一错误码与业务异常。

使用 ErrorCodes 枚举保证错误码在前后端一致可查。
PortViewError 携带 (code, message, detail) 三段信息：
- code:   短码，用于前端条件判断与埋点
- message: 用户可见的简短描述
- detail:  可选，开发者排查用的详细信息（不会暴霣给非 debug API）
"""
from __future__ import annotations

import enum
from typing import Any, Optional


class ErrorCodes(str, enum.Enum):
    """ PortView 业务错误码。"""

    # 配置相关
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"        # 配置文件缺失
    CONFIG_PARSE_ERROR = "CONFIG_PARSE_ERROR"    # JSON 解析失败
    CONFIG_SAVE_ERROR = "CONFIG_SAVE_ERROR"      # 写回失败
    RANGE_INVALID = "RANGE_INVALID"              # 自定义区间参数非法
    RANGE_NOT_FOUND = "RANGE_NOT_FOUND"          # 区间 ID 不存在

    # Docker 相关
    DOCKER_UNAVAILABLE = "DOCKER_UNAVAILABLE"    # 客户端连接失败
    DOCKER_API_ERROR = "DOCKER_API_ERROR"        # API 调用异常

    # 端口/扫描相关
    PORT_SCAN_ERROR = "PORT_SCAN_ERROR"           # 主机端口扫描失败

    # 鉴权相关
    AUTH_REQUIRED = "AUTH_REQUIRED"               # 未登录/Token 失效
    AUTH_FAILED = "AUTH_FAILED"                   # 密码错误

    # 系统
    INTERNAL_ERROR = "INTERNAL_ERROR"             # 未分类异常


class PortViewError(Exception):
    """ PortView 业务异常。"""

    def __init__(
        self,
        code: ErrorCodes,
        message: str,
        detail: Optional[str] = None,
        status_code: int = 400,
    ) -> None:
        self.code = code
        self.message = message
        self.detail = detail
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """序列化为前端可用的字典结构。"""
        data: dict[str, Any] = {
            "success": False,
            "error": self.message,
            "code": self.code.value,
        }
        if self.detail:
            data["detail"] = self.detail
        return data


# 快捷构造函数（供业务代码调用）
def make_error(code: ErrorCodes, message: str, detail: str | None = None) -> PortViewError:
    """ 快捷创建 PortViewError，自动映射 HTTP 状态码。"""
    status_map = {
        ErrorCodes.AUTH_REQUIRED: 401,
        ErrorCodes.AUTH_FAILED: 401,
        ErrorCodes.CONFIG_NOT_FOUND: 404,
        ErrorCodes.RANGE_NOT_FOUND: 404,
    }
    return PortViewError(
        code=code,
        message=message,
        detail=detail,
        status_code=status_map.get(code, 400),
    )
