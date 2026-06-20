"""
日志配置模块
使用 loguru 配置统一的日志输出。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    """配置应用全局日志。

    配置 loguru 日志系统，支持控制台和文件两种输出方式。
    日志文件按天轮转，保留30天日志。
    """
    # 移除默认的日志处理器
    logger.remove()

    # 确保日志目录存在
    log_dir = Path(settings.LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # 控制台输出（带颜色）
    logger.add(
        sys.stdout,
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        colorize=True,
        enqueue=True,
    )

    # 文件输出（不带颜色，按天轮转）
    logger.add(
        settings.LOG_FILE,
        format=settings.LOG_FORMAT.replace("<level>", "").replace("</level>", "")
        .replace("<green>", "").replace("</green>", "")
        .replace("<cyan>", "").replace("</cyan>", ""),
        level=settings.LOG_LEVEL,
        rotation="1 day",
        retention="30 days",
        compression="gz",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    logger.info(f"日志系统已初始化，级别: {settings.LOG_LEVEL}")
