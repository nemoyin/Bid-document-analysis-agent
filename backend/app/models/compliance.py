"""招标文件合规审查数据模型"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ComplianceRule(Base, TimestampMixin):
    """合规审查规则表"""

    __tablename__ = "compliance_rules"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, comment="规则ID (R01,R02,...)"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="规则名称")
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="deterministic|llm_semantic"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="启用状态")
    default_risk: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="默认风险等级: red/yellow/green"
    )
    weight: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True, comment="评分权重"
    )
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="适用条件")
    params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="可配置参数")
    legal_basis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="引用法条")
    llm_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="LLM prompt模板")

    def __repr__(self) -> str:
        return f"<ComplianceRule(id={self.id}, name='{self.name}')>"


class ComplianceAnalysis(Base, TimestampMixin):
    """合规审查分析任务表"""

    __tablename__ = "compliance_analyses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bid_documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default="pending", comment="pending/analyzing/completed/failed"
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="进度 0-100")
    compliance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="合规评分 0-100"
    )
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="low/moderate/high/critical"
    )
    clause_count: Mapped[int] = mapped_column(Integer, default=0, comment="提取的条款总数")
    violation_count: Mapped[int] = mapped_column(Integer, default=0, comment="违规条款数")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    clauses: Mapped[list["ComplianceClause"]] = relationship(
        "ComplianceClause", back_populates="analysis", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ComplianceAnalysis(id={self.id}, status='{self.status}')>"


class ComplianceClause(Base, TimestampMixin):
    """合规审查条款结果表"""

    __tablename__ = "compliance_clauses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("compliance_analyses.id", ondelete="CASCADE"), nullable=False
    )
    clause_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="条款类型")
    original_text: Mapped[str] = mapped_column(Text, nullable=False, comment="条款原文")
    location: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="章节/页码")
    params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="结构化参数")
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="green/yellow/red"
    )
    matched_rules: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="命中的规则列表及违规依据"
    )

    analysis: Mapped["ComplianceAnalysis"] = relationship(
        "ComplianceAnalysis", back_populates="clauses"
    )

    def __repr__(self) -> str:
        return f"<ComplianceClause(id={self.id}, type='{self.clause_type}', risk='{self.risk_level}')>"
