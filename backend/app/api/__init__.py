"""
API 模块
统一导出所有 API 路由。
"""

from app.api.v1 import router as api_v1_router

__all__ = [
    "api_v1_router",
]
