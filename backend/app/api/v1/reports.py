"""
报告导出 API 路由
提供 PDF/Word 报告生成和下载接口。
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from loguru import logger
from urllib.parse import quote

from app.db.session import async_session_factory
from app.schemas.common import ApiResponse
from app.services.report.report_generator import ReportGenerator

router = APIRouter(prefix="/projects/{project_id}/reports")


@router.get("")
async def download_report(
    project_id: str,
    task_id: str = Query(..., description="分析任务ID"),
    format: str = Query(default="pdf", pattern="^(pdf|word)$", description="报告格式"),
):
    """生成并下载分析报告。

    Args:
        project_id: 项目ID
        task_id: 分析任务ID（需为 completed 状态）
        format: 报告格式 (pdf / word)

    Returns:
        FileResponse: 报告文件下载
    """
    generator = ReportGenerator()

    try:
        file_bytes, filename = await generator.generate_report(
            db_session_factory=async_session_factory,
            project_id=project_id,
            task_id=task_id,
            output_format=format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"报告生成失败: {exc!s}")
        raise HTTPException(status_code=500, detail="报告生成失败")

    content_type_map = {
        "pdf": "application/pdf",
        "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    return Response(
        content=file_bytes,
        media_type=content_type_map.get(format, "application/octet-stream"),
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "Content-Length": str(len(file_bytes)),
        },
    )


@router.get("/data", response_model=ApiResponse)
async def get_report_data(
    project_id: str,
    task_id: str = Query(..., description="分析任务ID"),
):
    """获取分析报告原始数据（供前端渲染图表）。

    Args:
        project_id: 项目ID
        task_id: 分析任务ID

    Returns:
        ApiResponse: 报告数据结构
    """
    from sqlalchemy import select
    from app.models.analysis import (
        AnalysisTask,
        ErrorDetectionResult,
        ImageSimilarityResult,
        SimilarityResult,
    )
    from app.models.project import Project

    async with async_session_factory() as db:
        proj_result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        task_result = await db.execute(
            select(AnalysisTask).where(AnalysisTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        sim_result = await db.execute(
            select(SimilarityResult).where(SimilarityResult.task_id == task_id)
        )
        sims = sim_result.scalars().all()

        err_result = await db.execute(
            select(ErrorDetectionResult).where(
                ErrorDetectionResult.task_id == task_id
            )
        )
        errs = err_result.scalars().all()

        img_result = await db.execute(
            select(ImageSimilarityResult).where(
                ImageSimilarityResult.task_id == task_id
            )
        )
        imgs = img_result.scalars().all()

        # 解析6维度评分
        import json as _json
        dimension_scores = {}
        if task.error_message:
            try:
                parsed = _json.loads(task.error_message)
                if isinstance(parsed, dict) and "text_score" in parsed:
                    dimension_scores = parsed
            except (ValueError, TypeError):
                pass

        return ApiResponse.success(
            data={
                "project_name": project.name,
                "analysis_time": str(task.completed_at) if task.completed_at else None,
                "risk_score": float(task.risk_score or 0),
                "risk_level": task.risk_level,
                "dimension_scores": dimension_scores,
                "similarity_count": len(sims),
                "error_count": len(errs),
                "image_count": len(imgs),
            }
        )
