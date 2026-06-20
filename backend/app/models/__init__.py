"""数据库模型模块

核心数据模型定义，包含项目、文档、分析任务、相似度结果等实体。
"""

from app.models.base import Base, TimestampMixin
from app.models.project import Project, BidDocument
from app.models.analysis import (
    AnalysisTask,
    SimilarityResult,
    ErrorDetectionResult,
    ImageSimilarityResult,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "Project",
    "BidDocument",
    "AnalysisTask",
    "SimilarityResult",
    "ErrorDetectionResult",
    "ImageSimilarityResult",
]
