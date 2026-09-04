"""结构化日志配置。

默认输出 JSON 格式（便于 ELK / Grafana Loki 采集），支持通过环境变量
切换为人类可读格式。

环境变量：
- PORTVIEW_LOG_LEVEL: 日志等级（默认 INFO）
- PORTVIEW_LOG_FORMAT: "json" | "human"（默认 json）
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 合并 extra 字段
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "lineno", "funcName", "created",
                "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "getMessage", "exc_info",
                "exc_text", "stack_info", "taskName",
            } and not key.startswith("_"):
                log_obj[key] = value

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    """初始化日志系统（幂等）。"""
    level = os.environ.get("PORTVIEW_LOG_LEVEL", "INFO").upper()
    fmt = os.environ.get("PORTVIEW_LOG_FORMAT", "json")

    handler = logging.StreamHandler(sys.stdout)
    if fmt.lower() == "human":
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    else:
        handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level, logging.INFO))
    # 避免重复 handler
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)

    # 调整第三方库日志等级
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("docker").setLevel(logging.WARNING)

    logger = logging.getLogger("portview")
    logger.info("日志初始化完成", extra={"log_format": fmt, "log_level": level})
    return logger
