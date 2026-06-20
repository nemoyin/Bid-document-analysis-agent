"""
数据库会话管理
配置 SQLAlchemy 2.0 异步引擎和会话工厂。
"""

from __future__ import annotations

from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _build_async_database_url() -> str:
    """构建异步数据库连接 URL。

    Returns:
        str: 异步 PostgreSQL 连接 URL
    """
    db_url = settings.DATABASE_URL
    if db_url:
        # 如果已设置 DATABASE_URL，确保使用异步驱动
        if db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return db_url

    return (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )


# 异步引擎
ASYNC_DATABASE_URL = _build_async_database_url()

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：获取数据库会话。

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
