"""
数据库初始化模块
提供首次运行时创建所有表的函数。
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine


async def create_all_tables() -> None:
    """创建所有未存在的数据库表。

    使用 SQLAlchemy ORM 的 metadata.create_all 方法创建表。
    幂等操作，重复调用不会重复创建已存在的表。
    """
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("数据库表结构创建/同步完成")


async def check_database_connection() -> bool:
    """检查数据库连接是否正常。

    Returns:
        bool: 连接是否正常
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
            logger.info("数据库连接正常")
            return True
    except Exception as exc:
        logger.error(f"数据库连接失败: {exc!s}")
        return False


async def run_migrations() -> None:
    """执行数据库迁移（新增列等）。"""
    migrations = [
        # (表名, 列名, 类型)
        ("image_similarity_results", "similar_image_path", "VARCHAR(500)"),
        ("bid_documents", "extracted_tables", "JSON"),
        # 进度追踪新字段
        ("analysis_tasks", "progress_detail", "JSON"),
        ("analysis_tasks", "total_comparisons", "INTEGER DEFAULT 0"),
        ("analysis_tasks", "completed_comparisons", "INTEGER DEFAULT 0"),
        ("analysis_tasks", "issues_found", "INTEGER DEFAULT 0"),
        ("analysis_tasks", "estimated_seconds", "INTEGER"),
        ("analysis_tasks", "total_duration_ms", "INTEGER"),
    ]
    try:
        async with engine.connect() as conn:
            for table, column, col_type in migrations:
                try:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                    )
                    await conn.commit()
                    logger.info(f"迁移完成: 添加 {table}.{column} 列")
                except Exception:
                    await conn.rollback()
                    logger.debug(f"迁移跳过: {table}.{column} 列可能已存在")
    except Exception as exc:
        logger.warning(f"数据库迁移执行异常（可忽略）: {exc!s}")


async def init_database() -> None:
    """初始化数据库。

    执行以下操作：
    1. 检查数据库连接
    2. 创建所有表
    3. 执行迁移
    """
    logger.info("开始初始化数据库...")

    # 检查连接
    connected = await check_database_connection()
    if not connected:
        logger.warning("数据库连接失败，跳过表创建。请确保 PostgreSQL 服务已启动。")
        return

    # 创建表
    await create_all_tables()
    logger.info("数据库初始化完成")

    # 执行迁移
    await run_migrations()
