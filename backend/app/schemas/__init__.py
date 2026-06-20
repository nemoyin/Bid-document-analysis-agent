"""
Pydantic Schema 模块
定义请求/响应数据结构和统一响应格式。
"""

from app.schemas.common import (
    ApiResponse,
    PaginationParams,
    PaginatedResponse,
    ErrorType,
    RiskLevel,
    TaskStatus,
    DocumentStatus,
    ParseStatus,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectDetailResponse,
    BidDocumentCreate,
    BidDocumentResponse,
    BidDocumentDetailResponse,
)
from app.schemas.analysis import (
    AnalysisTaskCreate,
    AnalysisTaskResponse,
    AnalysisTaskDetailResponse,
    SimilarityResultResponse,
    ErrorDetectionResultResponse,
    ImageSimilarityResultResponse,
    RiskAnalysisRequest,
)

__all__ = [
    # common
    "ApiResponse",
    "PaginationParams",
    "PaginatedResponse",
    "ErrorType",
    "RiskLevel",
    "TaskStatus",
    "DocumentStatus",
    "ParseStatus",
    # project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "ProjectDetailResponse",
    "BidDocumentCreate",
    "BidDocumentResponse",
    "BidDocumentDetailResponse",
    # analysis
    "AnalysisTaskCreate",
    "AnalysisTaskResponse",
    "AnalysisTaskDetailResponse",
    "SimilarityResultResponse",
    "ErrorDetectionResultResponse",
    "ImageSimilarityResultResponse",
    "RiskAnalysisRequest",
]
