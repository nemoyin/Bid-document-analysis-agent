"""
应用级配置（便捷入口）
将基础配置与应用配置合并导出，方便各模块引用。
"""

from __future__ import annotations

from app.core.config import settings

__all__ = ["settings"]
