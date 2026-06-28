"""
分析任务、相似度结果、错误检测结果、图片相似结果模型定义
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AnalysisTask(Base, TimestampMixin):
    """分析任务表，记录每次分析作业的信息。"""

    __tablename__ = "analysis_tasks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="任务ID",
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        comment="任务状态: pending/analyzing/completed/failed",
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        default="full_analysis",
        comment="任务类型: full_analysis/text_only/image_only",
    )
    progress: Mapped[int] = mapped_column(
        Integer, default=0, comment="进度百分比 0-100"
    )
    progress_detail: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="详细进度: 6维度状态 + current_dimension"
    )
    total_comparisons: Mapped[int] = mapped_column(
        Integer, default=0, comment="总对比对数"
    )
    completed_comparisons: Mapped[int] = mapped_column(
        Integer, default=0, comment="已完成对比对数"
    )
    issues_found: Mapped[int] = mapped_column(
        Integer, default=0, comment="累计发现问题数"
    )
    estimated_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="预计剩余秒数 (ETA)"
    )
    total_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="任务实际耗时(毫秒)，完成后持久化"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="错误信息（任务失败时）"
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Celery 任务ID"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="开始时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="完成时间"
    )
    risk_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="综合风险评分 0.00-100.00"
    )
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="风险等级: LOW/MEDIUM/HIGH/CRITICAL"
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project", back_populates="analysis_tasks"
    )
    similarity_results: Mapped[list["SimilarityResult"]] = relationship(
        "SimilarityResult",
        back_populates="analysis_task",
        cascade="all, delete-orphan",
    )
    error_detection_results: Mapped[list["ErrorDetectionResult"]] = relationship(
        "ErrorDetectionResult",
        back_populates="analysis_task",
        cascade="all, delete-orphan",
    )
    image_similarity_results: Mapped[list["ImageSimilarityResult"]] = relationship(
        "ImageSimilarityResult",
        back_populates="analysis_task",
        cascade="all, delete-orphan",
    )
    template_reuse_results: Mapped[list["TemplateReuseResult"]] = relationship(
        "TemplateReuseResult",
        back_populates="analysis_task",
        cascade="all, delete-orphan",
    )
    electronic_signature_results: Mapped[list["ElectronicSignatureResult"]] = relationship(
        "ElectronicSignatureResult",
        back_populates="analysis_task",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisTask(id={self.id}, project_id={self.project_id}, "
            f"status='{self.status}')>"
        )


class SimilarityResult(Base, TimestampMixin):
    """文本相似度结果表，存储两两文档之间的相似度分析结果。"""

    __tablename__ = "similarity_results"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="结果ID",
    )
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属分析任务ID",
    )
    doc1_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bid_documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="文档A ID",
    )
    doc2_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bid_documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="文档B ID",
    )
    full_text_similarity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="全文相似度 0.00-100.00"
    )
    technical_similarity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="技术部分相似度"
    )
    business_similarity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="商务部分相似度"
    )
    structure_similarity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="目录结构相似度（预留）"
    )
    table_similarity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="表格相似度（预留）"
    )
    metadata_consistency: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="元数据一致性（预留）"
    )
    details: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="详细分析结果（相似段落列表等）"
    )

    # 关系
    analysis_task: Mapped["AnalysisTask"] = relationship(
        "AnalysisTask", back_populates="similarity_results"
    )
    doc1: Mapped["BidDocument"] = relationship(
        "BidDocument", foreign_keys=[doc1_id], back_populates="analysis_results_doc1"
    )
    doc2: Mapped["BidDocument"] = relationship(
        "BidDocument", foreign_keys=[doc2_id], back_populates="analysis_results_doc2"
    )

    def __repr__(self) -> str:
        return (
            f"<SimilarityResult(id={self.id}, doc1={self.doc1_id}, "
            f"doc2={self.doc2_id}, similarity={self.full_text_similarity})>"
        )


class ErrorDetectionResult(Base, TimestampMixin):
    """错误检测结果表，存储标书中的错别字、语病等检测结果。"""

    __tablename__ = "error_detection_results"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="结果ID",
    )
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属分析任务ID",
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bid_documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属文档ID",
    )
    error_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="错误类型: typo/grammar/omission/format",
    )
    original_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="原始文本（含错误）"
    )
    corrected_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="建议修正文本"
    )
    position: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="错误位置信息 {page, paragraph, offset}"
    )
    error_hash: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="错误特征哈希（用于跨文档比对）"
    )
    is_shared: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True,
        comment="是否与其他文档共享相同错误（用于错误一致性分析）"
    )
    shared_document_ids: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="共享相同错误的文档ID列表",
    )

    # 关系
    analysis_task: Mapped["AnalysisTask"] = relationship(
        "AnalysisTask", back_populates="error_detection_results"
    )
    document: Mapped["BidDocument"] = relationship(
        "BidDocument", back_populates="error_detections"
    )

    def __repr__(self) -> str:
        return (
            f"<ErrorDetectionResult(id={self.id}, doc={self.document_id}, "
            f"type='{self.error_type}')>"
        )


class ImageSimilarityResult(Base, TimestampMixin):
    """图片相似分析结果表，存储标书中提取的图片特征及相似比对结果。"""

    __tablename__ = "image_similarity_results"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="结果ID",
    )
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属分析任务ID",
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bid_documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属文档ID",
    )
    image_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="图片哈希值（pHash/dHash/aHash）"
    )
    image_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="图片存储路径"
    )
    similar_image_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="相似图片的存储路径（用于前端对比预览）"
    )
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="图片所在页码"
    )
    bounding_box: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="图片位置信息 {x, y, width, height}"
    )
    hash_algorithm: Mapped[str] = mapped_column(
        String(20), default="pHash", comment="哈希算法: pHash/dHash/aHash"
    )
    similar_image_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        comment="相似图片ID（跨文档比对时）",
    )
    similarity_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="图片相似度 0.00-100.00"
    )

    # 关系
    analysis_task: Mapped["AnalysisTask"] = relationship(
        "AnalysisTask", back_populates="image_similarity_results"
    )
    document: Mapped["BidDocument"] = relationship(
        "BidDocument", back_populates="image_features"
    )

    def __repr__(self) -> str:
        return (
            f"<ImageSimilarityResult(id={self.id}, doc={self.document_id}, "
            f"hash={self.image_hash[:16]}...)>"
        )


class TemplateReuseResult(Base, TimestampMixin):
    """模板复用分析结果表，检测不同标书是否使用相同文档模板。"""

    __tablename__ = "template_reuse_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()), comment="结果ID",
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_tasks.id", ondelete="CASCADE"),
        nullable=False, comment="所属分析任务ID",
    )
    doc1_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bid_documents.id", ondelete="CASCADE"),
        nullable=False, comment="文档A ID",
    )
    doc2_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bid_documents.id", ondelete="CASCADE"),
        nullable=False, comment="文档B ID",
    )
    reuse_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="模板复用度 0.00-100.00",
    )
    style_match_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="样式匹配度 (字体/段落/颜色)",
    )
    layout_match_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="布局匹配度 (页边距/页眉/页脚)",
    )
    heading_match_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="标题层级匹配度",
    )
    section_match_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="节结构匹配度",
    )
    details: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="详细分析结果 (样式列表/差异项)",
    )

    # 关系
    analysis_task: Mapped["AnalysisTask"] = relationship(
        "AnalysisTask", back_populates="template_reuse_results",
    )
    doc1: Mapped["BidDocument"] = relationship(
        "BidDocument", foreign_keys=[doc1_id],
    )
    doc2: Mapped["BidDocument"] = relationship(
        "BidDocument", foreign_keys=[doc2_id],
    )

    def __repr__(self) -> str:
        return (
            f"<TemplateReuseResult(id={self.id}, doc1={self.doc1_id}, "
            f"doc2={self.doc2_id}, reuse={self.reuse_score})>"
        )


class ElectronicSignatureResult(Base, TimestampMixin):
    """电子标书特征检测结果表，检测机器码/IP/创建者ID等电子证据。"""

    __tablename__ = "electronic_signature_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()), comment="结果ID",
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_tasks.id", ondelete="CASCADE"),
        nullable=False, comment="所属分析任务ID",
    )
    doc1_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bid_documents.id", ondelete="CASCADE"),
        nullable=False, comment="文档A ID",
    )
    doc2_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bid_documents.id", ondelete="CASCADE"),
        nullable=False, comment="文档B ID",
    )
    signature_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="电子签名一致性得分 0.00-100.00",
    )
    mac_match: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="MAC地址是否匹配 (None=无法获取)",
    )
    ip_match: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="上传IP是否匹配 (None=无法获取)",
    )
    creator_match: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="文件创建者ID是否匹配",
    )
    software_match: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="编辑软件版本是否一致",
    )
    details: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="详细证据 (mac_addresses, ip_addresses, creator_ids, ...)",
    )

    # 关系
    analysis_task: Mapped["AnalysisTask"] = relationship(
        "AnalysisTask", back_populates="electronic_signature_results",
    )
    doc1: Mapped["BidDocument"] = relationship(
        "BidDocument", foreign_keys=[doc1_id],
    )
    doc2: Mapped["BidDocument"] = relationship(
        "BidDocument", foreign_keys=[doc2_id],
    )

    def __repr__(self) -> str:
        return (
            f"<ElectronicSignatureResult(id={self.id}, doc1={self.doc1_id}, "
            f"doc2={self.doc2_id}, score={self.signature_score})>"
        )
