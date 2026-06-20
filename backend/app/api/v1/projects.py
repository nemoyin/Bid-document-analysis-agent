"""
项目 CRUD API 路由
提供项目的增删改查和文档管理接口。
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from loguru import logger

from app.db.session import get_db
from app.models.project import Project, BidDocument
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectDetailResponse,
    BidDocumentCreate,
    BidDocumentResponse,
    BidDocumentDetailResponse,
)
from app.core.config import settings

router = APIRouter(prefix="/projects")


# ============================================================
# 项目 CRUD
# ============================================================


@router.get("", response_model=ApiResponse[PaginatedResponse[ProjectResponse]])
async def list_projects(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    status: Optional[str] = Query(default=None, description="筛选状态"),
    keyword: Optional[str] = Query(default=None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
):
    """获取项目列表（分页）。"""
    # 构建查询
    query = select(Project)
    count_query = select(func.count(Project.id))

    if status:
        query = query.where(Project.status == status)
        count_query = count_query.where(Project.status == status)
    if keyword:
        keyword_filter = Project.name.ilike(f"%{keyword}%")
        query = query.where(keyword_filter)
        count_query = count_query.where(keyword_filter)

    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 获取分页数据
    offset = (page - 1) * page_size
    query = query.order_by(Project.updated_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    projects = result.scalars().all()

    # 转换响应
    items = [ProjectResponse.model_validate(p) for p in projects]

    return ApiResponse.success(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/{project_id}", response_model=ApiResponse[ProjectDetailResponse])
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目详情（含文档列表）。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 获取文档列表
    doc_result = await db.execute(
        select(BidDocument).where(BidDocument.project_id == project_id)
    )
    documents = doc_result.scalars().all()

    response = ProjectDetailResponse(
        **ProjectResponse.model_validate(project).model_dump(),
        documents=[BidDocumentResponse.model_validate(d) for d in documents],
    )
    return ApiResponse.success(data=response)


@router.post("", response_model=ApiResponse[ProjectResponse])
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """创建新项目。"""
    project = Project(
        name=data.name,
        description=data.description,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)

    logger.info(f"项目创建成功: {project.id} - {project.name}")
    return ApiResponse.success(
        data=ProjectResponse.model_validate(project),
        message="项目创建成功",
    )


@router.put("/{project_id}", response_model=ApiResponse[ProjectResponse])
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新项目信息。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.status is not None:
        project.status = data.status

    await db.flush()
    await db.refresh(project)

    logger.info(f"项目更新成功: {project.id}")
    return ApiResponse.success(data=ProjectResponse.model_validate(project))


@router.delete("/{project_id}", response_model=ApiResponse)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """删除项目及其所有关联数据。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    await db.delete(project)
    logger.info(f"项目已删除: {project_id}")
    return ApiResponse.success(message="项目已删除")


# ============================================================
# 文档管理
# ============================================================


@router.get(
    "/{project_id}/documents",
    response_model=ApiResponse[PaginatedResponse[BidDocumentResponse]],
)
async def list_documents(
    project_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取项目下的文档列表（分页）。"""
    # 校验项目存在
    proj = await db.execute(select(Project).where(Project.id == project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在")

    count_q = select(func.count(BidDocument.id)).where(
        BidDocument.project_id == project_id
    )
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        select(BidDocument)
        .where(BidDocument.project_id == project_id)
        .order_by(BidDocument.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [BidDocumentResponse.model_validate(d) for d in result.scalars().all()]
    return ApiResponse.success(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get(
    "/{project_id}/documents/{document_id}",
    response_model=ApiResponse[BidDocumentDetailResponse],
)
async def get_document_detail(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取文档详情。"""
    result = await db.execute(
        select(BidDocument).where(
            BidDocument.id == document_id,
            BidDocument.project_id == project_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    return ApiResponse.success(data=BidDocumentDetailResponse.model_validate(doc))


@router.delete(
    "/{project_id}/documents/{document_id}",
    response_model=ApiResponse,
)
async def delete_document(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除文档。"""
    result = await db.execute(
        select(BidDocument).where(
            BidDocument.id == document_id,
            BidDocument.project_id == project_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 更新项目文档计数
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if project and project.file_count > 0:
        project.file_count -= 1

    await db.delete(doc)
    return ApiResponse.success(message="文档已删除")
