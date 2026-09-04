"""配置与隐藏端口的读写。

配置文件采用「服务名:docker/host -> 端口:tcp/udp」的新格式，同时兼容
旧格式（纯数字、"端口:协议" 字符串）。本模块提供：

- :func:`init_config`  首次启动时初始化配置目录与文件
- :func:`load_config`  读取并解析为结构化字典
- :func:`load_raw_config` 读取原始 JSON（供设置界面编辑）
- :func:`save_config`  把结构化字典写回原始格式
- :func:`save_raw_config` 直接写入原始 JSON
- :func:`load_hidden_ports` / :func:`save_hidden_ports` 隐藏端口列表
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

# 配置文件路径（运行时目录，Docker 中通过卷挂载持久化）
CONFIG_DIR = os.environ.get("PORTVIEW_CONFIG_DIR", "/app/config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
HIDDEN_PORTS_FILE = os.path.join(CONFIG_DIR, "hidden_ports.json")

# 仓库内自带的示例配置（首次启动时复制）
_EXAMPLE_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "config.json.example",
)

# 兜底默认配置（示例文件缺失时使用，保持向后兼容）
_DEFAULT_CONFIG: dict[str, str] = {
    "远程登录:host": "22:tcp",
    "HTTP:host": "80:tcp",
    "HTTPS:host": "443:tcp",
    "MySQL数据库:host": "3306:tcp",
    "PostgreSQL数据库:host": "5432:tcp",
    "Redis缓存:host": "6379:tcp",
    "MongoDB数据库:host": "27017:tcp",
    "搜索分析:host": "9200:tcp",
    "PortView:docker": "7575:tcp",
}


def init_config() -> None:
    """初始化配置目录与文件（幂等）。"""
    os.makedirs(CONFIG_DIR, exist_ok=True)

    # 主配置文件
    if not os.path.exists(CONFIG_FILE):
        if os.path.exists(_EXAMPLE_CONFIG_FILE):
            shutil.copy2(_EXAMPLE_CONFIG_FILE, CONFIG_FILE)
            logger.info("配置文件已从示例文件复制: %s", CONFIG_FILE)
        else:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(_DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            logger.info("配置文件已创建（默认配置）: %s", CONFIG_FILE)
    else:
        logger.info("配置文件已存在: %s", CONFIG_FILE)

    # 隐藏端口配置文件
    if not os.path.exists(HIDDEN_PORTS_FILE):
        with open(HIDDEN_PORTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        logger.info("隐藏端口配置文件已创建: %s", HIDDEN_PORTS_FILE)
    else:
        logger.info("隐藏端口配置文件已存在: %s", HIDDEN_PORTS_FILE)


def load_config() -> dict[str, Any]:
    """加载配置并解析为结构化字典。

    返回形如 ``{服务名: {"port": int, "protocol": str, "service_type": str}}``。
    解析失败时返回一套内置默认配置，保证服务可用。
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            raw_config = json.load(f)
    except Exception as e:  # noqa: BLE001 - 解析失败时返回默认配置
        logger.warning("加载配置文件失败: %s", e)
        return _fallback_config()

    processed: dict[str, Any] = {}
    for key, value in raw_config.items():
        if isinstance(value, str) and ":" in value:
            if ":" in key and (key.endswith(":docker") or key.endswith(":host")):
                # 新格式：服务名:docker/host
                service_name, service_type = key.rsplit(":", 1)
                value_parts = value.split(":")
                if len(value_parts) >= 2:
                    try:
                        port = int(value_parts[0])
                    except ValueError:
                        processed[key] = value
                        continue
                    processed[service_name] = {
                        "port": port,
                        "protocol": value_parts[1].upper(),
                        "service_type": service_type,
                    }
                else:
                    processed[key] = value
            else:
                # 旧格式："服务名": "端口:协议"
                parts = value.split(":")
                if len(parts) >= 2:
                    try:
                        port = int(parts[0])
                    except ValueError:
                        processed[key] = value
                        continue
                    protocol = parts[1].upper() if parts[1].upper() in ("TCP", "UDP") else "TCP"
                    processed[key] = {"port": port, "protocol": protocol}
                else:
                    processed[key] = value
        elif isinstance(value, int):
            processed[key] = {"port": value, "protocol": "TCP"}
        else:
            processed[key] = value

    return processed


def load_raw_config() -> dict[str, Any]:
    """读取原始配置 JSON（未经结构化处理，供设置界面编辑）。"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: Mapping[str, Any]) -> bool:
    """把结构化配置写回原始「服务名:docker/host -> 端口:协议」格式。"""
    raw_config: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, dict) and "port" in value and "protocol" in value:
            service_type = value.get("service_type", "host")
            raw_config[f"{key}:{service_type}"] = f"{value['port']}:{value['protocol'].lower()}"
        else:
            raw_config[key] = value
    return _write_json(CONFIG_FILE, raw_config)


def save_raw_config(raw: Mapping[str, Any]) -> bool:
    """直接写入原始 JSON 配置。"""
    return _write_json(CONFIG_FILE, dict(raw))


def load_hidden_ports() -> list[int]:
    """加载隐藏端口列表。"""
    try:
        if os.path.exists(HIDDEN_PORTS_FILE):
            with open(HIDDEN_PORTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:  # noqa: BLE001
        logger.warning("加载隐藏端口配置失败: %s", e)
    return []


def save_hidden_ports(hidden_ports: list[int]) -> bool:
    """保存隐藏端口列表。"""
    return _write_json(HIDDEN_PORTS_FILE, hidden_ports)


def _write_json(path: str, data: Any) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("写入 %s 失败: %s", path, e)
        return False


def _fallback_config() -> dict[str, Any]:
    return {
        "ssh": {"port": 22, "protocol": "TCP"},
        "http": {"port": 80, "protocol": "TCP"},
        "https": {"port": 443, "protocol": "TCP"},
        "mysql": {"port": 3306, "protocol": "TCP"},
        "postgresql": {"port": 5432, "protocol": "TCP"},
        "redis": {"port": 6379, "protocol": "TCP"},
        "mongodb": {"port": 27017, "protocol": "TCP"},
        "elasticsearch": {"port": 9200, "protocol": "TCP"},
        "app_settings": {"host": "0.0.0.0", "port": 7577, "debug": False},
    }
