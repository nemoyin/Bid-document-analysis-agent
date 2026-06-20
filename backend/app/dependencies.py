"""
FastAPI 依赖注入模块
提供全局共享的依赖函数。
"""

from __future__ import annotations

from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_factory


def get_settings() -> settings.__class__:
    """获取应用配置。

    Returns:
        Settings: 应用配置单例
    """
    return settings


async def verify_api_key(api_key: str | None = None) -> bool:
    """验证 API Key（预留接口）。

    当前 MVP 阶段不做 API Key 校验，后续版本实现。

    Args:
        api_key: 可选的 API Key

    Returns:
        bool: 验证结果
    """
    return True


def get_chroma_path() -> str:
    """获取 ChromaDB 持久化路径。

    Returns:
        str: ChromaDB 数据目录路径
    """
    return settings.CHROMA_DB_PATH


def get_upload_dir() -> str:
    """获取文件上传目录。

    Returns:
        str: 上传目录路径
    """
    return settings.UPLOAD_DIR


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（FastAPI 依赖）。

    每次请求自动获取一个异步数据库会话，
    请求完成后自动提交或回滚并关闭。

    Yields:
        AsyncSession: 异步数据库会话
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(f"数据库会话异常: {exc!s}")
            raise
        finally:
            await session.close()
