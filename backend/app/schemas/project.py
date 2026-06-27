"""
项目与文档 Schema 定义
包括项目 CRUD、文档上传等请求/响应模型。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 项目 Schema
# ============================================================


class ProjectCreate(BaseModel):
    """创建项目请求。"""

    name: str = Field(..., min_length=1, max_length=255, description="项目名称")
    description: Optional[str] = Field(default=None, max_length=2000, description="项目描述")


class ProjectUpdate(BaseModel):
    """更新项目请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="项目名称")
    description: Optional[str] = Field(default=None, max_length=2000, description="项目描述")
    status: Optional[str] = Field(default=None, pattern="^(active|archived)$", description="项目状态")


class ProjectResponse(BaseModel):
    """项目响应（列表项）。"""

    id: uuid.UUID = Field(..., description="项目ID")
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(default=None, description="项目描述")
    status: str = Field(default="active", description="项目状态")
    file_count: int = Field(default=0, description="标书文件数量")
    risk_level: Optional[str] = Field(default=None, description="风险等级")
    average_score: Optional[Decimal] = Field(default=None, description="平均风险评分")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")

    model_config = {"from_attributes": True}


# ============================================================
# 文档 Schema（必须在 ProjectDetailResponse 之前定义）
# ============================================================


class BidDocumentResponse(BaseModel):
    """文档响应。"""

    id: uuid.UUID = Field(..., description="文档ID")
    project_id: uuid.UUID = Field(..., description="所属项目ID")
    filename: str = Field(..., description="文件名")
    file_size: Optional[int] = Field(default=None, description="文件大小（字节）")
    file_type: Optional[str] = Field(default=None, description="文件类型")
    status: str = Field(default="uploaded", description="文档状态")
    parse_status: Optional[str] = Field(default=None, description="解析状态")
    page_count: Optional[int] = Field(default=None, description="页数")
    created_at: Optional[datetime] = Field(default=None, description="上传时间")

    model_config = {"from_attributes": True}


class BidDocumentCreate(BaseModel):
    """创建文档记录请求（上传后调用）。"""

    project_id: uuid.UUID = Field(..., description="所属项目ID")
    filename: str = Field(..., max_length=255, description="文件名")
    file_path: str = Field(..., max_length=500, description="文件存储路径")
    file_size: Optional[int] = Field(default=None, description="文件大小（字节）")
    file_type: Optional[str] = Field(default=None, pattern="^(pdf|doc|docx)$", description="文件类型")


class BidDocumentDetailResponse(BidDocumentResponse):
    """文档详情响应（含文本内容和元数据）。"""

    content_text: Optional[str] = Field(default=None, description="提取的文本内容")
    file_metadata: Optional[dict] = Field(default=None, description="文件元数据")
    parsed_at: Optional[datetime] = Field(default=None, description="解析完成时间")


# ============================================================
# 项目详情（依赖 BidDocumentResponse，放在最后）
# ============================================================


class ProjectDetailResponse(ProjectResponse):
    """项目详情响应（含文档列表）。"""

    documents: list[BidDocumentResponse] = Field(default_factory=list, description="标书文档列表")
    recent_tasks: list = Field(default_factory=list, description="最近分析任务")
