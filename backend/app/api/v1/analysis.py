"""
分析任务 API 路由
提供分析任务的创建、触发执行、查询和结果获取接口。
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.db.session import get_db, async_session_factory
from app.models.analysis import (
    AnalysisTask,
    SimilarityResult,
    ErrorDetectionResult,
    ImageSimilarityResult,
)
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.analysis import (
    AnalysisTaskCreate,
    AnalysisTaskResponse,
    AnalysisTaskDetailResponse,
    SimilarityResultResponse,
    ErrorDetectionResultResponse,
    ImageSimilarityResultResponse,
)
from app.services.analysis.analysis_orchestrator import AnalysisOrchestrator

router = APIRouter(prefix="/analysis")


# ============================================================
# 后台分析任务执行
# ============================================================


async def _run_analysis_background(
    project_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
) -> None:
    """后台执行完整分析流程。

    通过 Orchestrator 执行多阶段分析，结果自动写入数据库。

    Args:
        project_id: 项目ID
        analysis_task_id: 分析任务ID
    """
    logger.info(
        f"后台分析任务启动: task={analysis_task_id}, project={project_id}"
    )

    orchestrator = AnalysisOrchestrator(
        db_session_factory=async_session_factory
    )

    try:
        result = await orchestrator.run_analysis(
            project_id=project_id,
            analysis_task_id=analysis_task_id,
        )
        logger.info(f"后台分析任务完成: {result}")
    except Exception as exc:
        logger.error(f"后台分析任务失败: {exc!s}")
        # 更新任务状态为失败
        try:
            async with async_session_factory() as db:
                task_result = await db.execute(
                    select(AnalysisTask).where(
                        AnalysisTask.id == analysis_task_id
                    )
                )
                task = task_result.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error_message = str(exc)[:500]
                    await db.commit()
        except Exception as inner_exc:
            logger.error(f"更新失败任务状态异常: {inner_exc!s}")


# ============================================================
# 分析任务管理
# ============================================================


@router.post("/tasks", response_model=ApiResponse[AnalysisTaskResponse])
async def create_analysis_task(
    data: AnalysisTaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """创建并启动分析任务。

    创建一个分析任务记录，并通过后台任务启动完整分析流程。
    分析包括：文本相似度、图片相似度、错误检测、综合评分。
    """
    # 注意: 数据库列类型为 String(36)，SQLite/PG 都按字符串存
    task = AnalysisTask(
        project_id=str(data.project_id),
        task_type=data.task_type,
        status="pending",
        progress=0,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    # 显式 commit，确保 BackgroundTasks 跑起来时 task 已在 DB 中
    await db.commit()
    await db.refresh(task)

    logger.info(
        f"分析任务创建: {task.id}, 项目: {data.project_id}, 类型: {data.task_type}"
    )

    # 通过 BackgroundTasks 启动异步分析
    # 注意：background.add_task 在响应返回后、get_db 退出前执行，
    # 所以这里在内部新开 session 处理失败状态，避免污染主 session。
    background_tasks.add_task(
        _run_analysis_background,
        project_id=str(data.project_id),
        analysis_task_id=str(task.id),
    )

    return ApiResponse.success(
        data=AnalysisTaskResponse.model_validate(task),
        message="分析任务创建成功，后台分析已启动",
    )


@router.get("/tasks", response_model=ApiResponse[PaginatedResponse[AnalysisTaskResponse]])
async def list_analysis_tasks(
    project_id: Optional[str] = Query(default=None, description="按项目筛选"),
    status: Optional[str] = Query(default=None, description="按状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
):
    """获取分析任务列表。"""
    query = select(AnalysisTask)
    count_query = select(func.count(AnalysisTask.id))

    if project_id:
        query = query.where(AnalysisTask.project_id == project_id)
        count_query = count_query.where(AnalysisTask.project_id == project_id)
    if status:
        query = query.where(AnalysisTask.status == status)
        count_query = count_query.where(AnalysisTask.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(AnalysisTask.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    tasks = result.scalars().all()

    items = [AnalysisTaskResponse.model_validate(t) for t in tasks]

    return ApiResponse.success(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/tasks/{task_id}", response_model=ApiResponse[AnalysisTaskDetailResponse])
async def get_analysis_task_detail(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    progress_only: bool = Query(default=False, description="仅返回进度字段（不含结果列表，适合轮询）"),
):
    """获取分析任务详情（含各项分析结果）。传 ?progress_only=true 时仅返回进度数据。"""
    result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="分析任务不存在")

    if progress_only:
        return ApiResponse.success(data=AnalysisTaskResponse.model_validate(task))

    # 获取相似度结果
    sim_result = await db.execute(
        select(SimilarityResult).where(SimilarityResult.task_id == task_id)
    )
    similarity_results = sim_result.scalars().all()

    # 获取错误检测结果
    err_result = await db.execute(
        select(ErrorDetectionResult).where(ErrorDetectionResult.task_id == task_id)
    )
    error_results = err_result.scalars().all()

    # 获取图片相似结果
    img_result = await db.execute(
        select(ImageSimilarityResult).where(ImageSimilarityResult.task_id == task_id)
    )
    image_results = img_result.scalars().all()

    response = AnalysisTaskDetailResponse(
        **AnalysisTaskResponse.model_validate(task).model_dump(),
        similarity_results=[
            SimilarityResultResponse.model_validate(r) for r in similarity_results
        ],
        error_detection_results=[
            ErrorDetectionResultResponse.model_validate(r) for r in error_results
        ],
        image_similarity_results=[
            ImageSimilarityResultResponse.model_validate(r) for r in image_results
        ],
    )
    return ApiResponse.success(data=response)




# ============================================================
# 相似度结果
# ============================================================


@router.get(
    "/tasks/{task_id}/similarity",
    response_model=ApiResponse[list[SimilarityResultResponse]],
)
async def get_similarity_results(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取分析任务的相似度结果列表。"""
    result = await db.execute(
        select(SimilarityResult).where(SimilarityResult.task_id == task_id)
    )
    items = result.scalars().all()
    return ApiResponse.success(
        data=[SimilarityResultResponse.model_validate(r) for r in items]
    )


# ============================================================
# 错误检测结果
# ============================================================


@router.get(
    "/tasks/{task_id}/errors",
    response_model=ApiResponse[list[ErrorDetectionResultResponse]],
)
async def get_error_detection_results(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取分析任务的错误检测结果列表。"""
    result = await db.execute(
        select(ErrorDetectionResult).where(ErrorDetectionResult.task_id == task_id)
    )
    items = result.scalars().all()
    return ApiResponse.success(
        data=[ErrorDetectionResultResponse.model_validate(r) for r in items]
    )


# ============================================================
# 图片相似结果
# ============================================================


@router.get(
    "/tasks/{task_id}/images",
    response_model=ApiResponse[list[ImageSimilarityResultResponse]],
)
async def get_image_similarity_results(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取分析任务的图片相似结果列表。"""
    result = await db.execute(
        select(ImageSimilarityResult).where(ImageSimilarityResult.task_id == task_id)
    )
    items = result.scalars().all()
    return ApiResponse.success(
        data=[ImageSimilarityResultResponse.model_validate(r) for r in items]
    )
