"""
公共 Schema 定义
包括统一响应格式、分页参数、枚举类型等。
"""

from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

# 泛型类型变量
T = TypeVar("T")
DataT = TypeVar("DataT")


# ============================================================
# 枚举类型
# ============================================================


class ErrorType(str, Enum):
    """错误类型枚举。"""

    TYPO = "typo"  # 错别字
    GRAMMAR = "grammar"  # 语病
    OMISSION = "omission"  # 漏字
    FORMAT = "format"  # 格式错误


class RiskLevel(str, Enum):
    """风险等级枚举。"""

    LOW = "low"  # 低风险 0-30
    MODERATE = "moderate"  # 中风险 31-60
    HIGH = "high"  # 高风险 61-80
    CRITICAL = "critical"  # 严重风险 81-100

    @classmethod
    def from_score(cls, score: float) -> "RiskLevel":
        """根据评分返回风险等级。

        Args:
            score: 风险评分（0-100）

        Returns:
            RiskLevel: 对应的风险等级
        """
        if score <= 30:
            return cls.LOW
        elif score <= 60:
            return cls.MODERATE
        elif score <= 80:
            return cls.HIGH
        else:
            return cls.CRITICAL


class TaskStatus(str, Enum):
    """分析任务状态枚举。"""

    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentStatus(str, Enum):
    """文档状态枚举（文档级状态）。"""

    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class ParseStatus(str, Enum):
    """解析状态枚举（解析引擎进度）。"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================
# 统一响应格式
# ============================================================


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式。

    所有接口统一返回该格式，code=0 表示成功，非0表示错误。
    """

    code: int = Field(default=0, description="业务状态码，0表示成功")
    message: str = Field(default="success", description="提示信息")
    data: Optional[T] = Field(default=None, description="响应数据")

    @classmethod
    def success(cls, data: Optional[T] = None, message: str = "success") -> "ApiResponse[T]":
        """创建成功响应。

        Args:
            data: 响应数据
            message: 提示信息

        Returns:
            ApiResponse: 成功响应
        """
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, code: int = 400, message: str = "error", data: Optional[T] = None) -> "ApiResponse[T]":
        """创建错误响应。

        Args:
            code: 错误码
            message: 错误信息
            data: 附加数据

        Returns:
            ApiResponse: 错误响应
        """
        return cls(code=code, message=message, data=data)


class PaginationParams(BaseModel):
    """分页查询参数。"""

    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")
    sort_by: Optional[str] = Field(default=None, description="排序字段")
    sort_order: Optional[str] = Field(default="desc", description="排序方向: asc/desc")


class PaginatedResponse(BaseModel, Generic[DataT]):
    """分页响应数据。"""

    items: list[DataT] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页条数")
    total_pages: int = Field(default=0, description="总页数")
