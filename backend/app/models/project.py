"""
项目与文档模型定义
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    """项目表，存储投标分析项目信息。"""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="项目名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="项目描述"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="active", comment="项目状态: active/archived"
    )
    file_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="标书文件数量"
    )
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="风险等级: low/moderate/high/critical"
    )
    average_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="平均风险评分"
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, comment="创建用户ID（预留）"
    )

    # 关系
    documents: Mapped[list["BidDocument"]] = relationship(
        "BidDocument", back_populates="project", cascade="all, delete-orphan"
    )
    analysis_tasks: Mapped[list["AnalysisTask"]] = relationship(
        "AnalysisTask", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"


class BidDocument(Base, TimestampMixin):
    """标书文档表，存储上传的投标文件信息。"""

    __tablename__ = "bid_documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="文档ID",
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID",
    )
    filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="原始文件名"
    )
    file_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="文件存储路径"
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="文件大小（字节）"
    )
    file_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="文件类型: pdf/doc/docx"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="uploaded", comment="文档状态: uploaded/parsing/parsed/failed"
    )
    parse_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="解析状态: pending/processing/completed/failed"
    )
    content_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="提取的文本内容"
    )
    file_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True, comment="文件元数据（作者、创建时间等）"
    )
    page_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="文档页数"
    )
    parsed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="解析完成时间"
    )
    extracted_images: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="提取的图片列表 [{page, hash, path}, ...]"
    )
    extracted_tables: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="提取的表格数据 [[{page, rows, cols, header, data}], ...]"
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project", back_populates="documents"
    )
    analysis_results_doc1: Mapped[list["SimilarityResult"]] = relationship(
        "SimilarityResult",
        foreign_keys="SimilarityResult.doc1_id",
        back_populates="doc1",
        cascade="all, delete-orphan",
    )
    analysis_results_doc2: Mapped[list["SimilarityResult"]] = relationship(
        "SimilarityResult",
        foreign_keys="SimilarityResult.doc2_id",
        back_populates="doc2",
        cascade="all, delete-orphan",
    )
    error_detections: Mapped[list["ErrorDetectionResult"]] = relationship(
        "ErrorDetectionResult", back_populates="document", cascade="all, delete-orphan"
    )
    image_features: Mapped[list["ImageSimilarityResult"]] = relationship(
        "ImageSimilarityResult", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BidDocument(id={self.id}, filename='{self.filename}', status='{self.status}')>"
