"""
分析任务 Schema 定义
包括分析任务、相似度结果、错误检测、图片相似等模型。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 分析任务 Schema
# ============================================================


class AnalysisTaskCreate(BaseModel):
    """创建分析任务请求。"""

    project_id: uuid.UUID = Field(..., description="项目ID")
    task_type: str = Field(
        default="full_analysis",
        pattern="^(full_analysis|text_only|image_only)$",
        description="任务类型",
    )


class AnalysisTaskResponse(BaseModel):
    """分析任务响应。"""

    id: uuid.UUID = Field(..., description="任务ID")
    project_id: uuid.UUID = Field(..., description="项目ID")
    status: str = Field(..., description="任务状态")
    task_type: str = Field(..., description="任务类型")
    progress: int = Field(default=0, description="进度百分比")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    celery_task_id: Optional[str] = Field(default=None, description="Celery任务ID")
    risk_score: Optional[float] = Field(default=None, description="综合风险评分")
    risk_level: Optional[str] = Field(default=None, description="风险等级")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    dimension_scores: Optional[dict] = Field(default=None, description="各维度评分 {text_score, image_score, error_score}")

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """从 ORM 对象创建，解析 error_message 中的维度评分。"""
        if hasattr(obj, "__table__"):
            import json as _json
            d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            if d.get("error_message"):
                try:
                    parsed = _json.loads(d["error_message"])
                    if isinstance(parsed, dict) and "text_score" in parsed:
                        d["dimension_scores"] = parsed
                except (ValueError, TypeError):
                    pass
            return super().model_validate(d, **kwargs)
        return super().model_validate(obj, **kwargs)



class AnalysisTaskDetailResponse(AnalysisTaskResponse):
    """分析任务详情响应（含各项结果）。"""

    similarity_results: list["SimilarityResultResponse"] = Field(
        default_factory=list, description="相似度结果"
    )
    error_detection_results: list["ErrorDetectionResultResponse"] = Field(
        default_factory=list, description="错误检测结果"
    )
    image_similarity_results: list["ImageSimilarityResultResponse"] = Field(
        default_factory=list, description="图片相似结果"
    )


# ============================================================
# 相似度结果 Schema
# ============================================================


class SimilarityResultResponse(BaseModel):
    """文本相似度结果响应。"""

    id: uuid.UUID = Field(..., description="结果ID")
    task_id: uuid.UUID = Field(..., description="分析任务ID")
    doc1_id: uuid.UUID = Field(..., description="文档A ID")
    doc2_id: uuid.UUID = Field(..., description="文档B ID")
    full_text_similarity: Optional[Decimal] = Field(default=None, description="全文相似度")
    technical_similarity: Optional[Decimal] = Field(default=None, description="技术部分相似度")
    business_similarity: Optional[Decimal] = Field(default=None, description="商务部分相似度")
    structure_similarity: Optional[Decimal] = Field(default=None, description="目录结构相似度（预留）")
    table_similarity: Optional[Decimal] = Field(default=None, description="表格相似度（预留）")
    metadata_consistency: Optional[Decimal] = Field(default=None, description="元数据一致性（预留）")
    details: Optional[dict] = Field(default=None, description="详细分析结果")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")

    model_config = {"from_attributes": True}


# ============================================================
# 错误检测结果 Schema
# ============================================================


class ErrorDetectionResultResponse(BaseModel):
    """错误检测结果响应。"""

    id: uuid.UUID = Field(..., description="结果ID")
    task_id: uuid.UUID = Field(..., description="分析任务ID")
    document_id: uuid.UUID = Field(..., description="文档ID")
    error_type: str = Field(..., description="错误类型")
    original_text: str = Field(..., description="原始文本")
    corrected_text: Optional[str] = Field(default=None, description="建议修正")
    position: Optional[dict] = Field(default=None, description="位置信息")
    error_hash: Optional[str] = Field(default=None, description="错误特征哈希")
    is_shared: Optional[bool] = Field(default=None, description="是否跨文档共享")
    shared_document_ids: Optional[dict] = Field(default=None, description="共享文档ID列表")

    model_config = {"from_attributes": True}


# ============================================================
# 图片相似结果 Schema
# ============================================================


class ImageSimilarityResultResponse(BaseModel):
    """图片相似结果响应。"""

    id: uuid.UUID = Field(..., description="结果ID")
    task_id: uuid.UUID = Field(..., description="分析任务ID")
    document_id: uuid.UUID = Field(..., description="文档ID")
    image_hash: str = Field(..., description="图片哈希值")
    image_path: str = Field(..., description="图片路径")
    similar_image_path: Optional[str] = Field(default=None, description="相似图片的存储路径")
    page_number: Optional[int] = Field(default=None, description="页码")
    bounding_box: Optional[dict] = Field(default=None, description="位置信息")
    hash_algorithm: str = Field(default="pHash", description="哈希算法")
    similar_image_id: Optional[uuid.UUID] = Field(default=None, description="相似图片ID")
    similarity_score: Optional[Decimal] = Field(default=None, description="相似度")

    model_config = {"from_attributes": True}


# ============================================================
# 风险分析请求
# ============================================================


class RiskAnalysisRequest(BaseModel):
    """风险分析请求。"""

    project_id: uuid.UUID = Field(..., description="项目ID")
    text_weight: float = Field(default=0.4, ge=0.0, le=1.0, description="文本相似度权重")
    image_weight: float = Field(default=0.25, ge=0.0, le=1.0, description="图片相似度权重")
    error_weight: float = Field(default=0.35, ge=0.0, le=1.0, description="错误一致性权重")
