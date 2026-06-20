"""
SQLAlchemy 声明基类与混入
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类。"""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """自动生成表名（驼峰转蛇形）。"""
        name_parts: list[str] = []
        for char in cls.__name__:
            if char.isupper() and name_parts:
                name_parts.append("_" + char.lower())
            else:
                name_parts.append(char.lower())
        return "".join(name_parts)

    def to_dict(self) -> dict:
        """将模型实例转换为字典。"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name, None)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result


class TimestampMixin:
    """时间戳混入类，提供 created_at 和 updated_at 字段。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="更新时间",
    )
