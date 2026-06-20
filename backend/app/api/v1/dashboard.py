"""
Dashboard 统计数据 API 路由。
提供首页仪表盘的聚合统计数据。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case, extract, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project, BidDocument
from app.models.analysis import AnalysisTask
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/dashboard")


@router.get("/stats", response_model=ApiResponse)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """获取仪表盘统计数据。

    Returns:
        - task_count: 总任务数（项目数）
        - report_count: 已有分析报告的任务数
        - document_count: 总标书文件数
        - risk_distribution: 风险等级分布
        - monthly_trend: 近6月创建趋势
        - analysis_stats: 分析任务统计（总次数、平均耗时、成功率）
    """
    now = datetime.now(timezone.utc)
    six_months_ago = now - timedelta(days=180)

    # ── 总任务数 ──
    task_count_result = await db.execute(select(func.count(Project.id)))
    task_count = task_count_result.scalar() or 0

    # ── 已有报告数（已分析有风险等级的项目） ──
    report_count_result = await db.execute(
        select(func.count(Project.id)).where(Project.risk_level.isnot(None))
    )
    report_count = report_count_result.scalar() or 0

    # ── 总标书文件数 ──
    doc_count_result = await db.execute(select(func.count(BidDocument.id)))
    document_count = doc_count_result.scalar() or 0

    # ── 风险等级分布 ──
    risk_result = await db.execute(
        select(
            func.coalesce(Project.risk_level, 'NONE').label('level'),
            func.count(Project.id).label('cnt'),
        ).group_by(text('level'))
    )
    risk_distribution = {
        row.level: row.cnt
        for row in risk_result.all()
    }

    # ── 近6月任务创建趋势（按月） ──
    trend_result = await db.execute(
        select(
            func.strftime('%Y-%m', Project.created_at).label('month'),
            func.count(Project.id).label('cnt'),
        )
        .where(Project.created_at >= six_months_ago)
        .group_by(text('month'))
        .order_by(text('month'))
    )
    monthly_trend = [
        {"month": row.month, "count": row.cnt}
        for row in trend_result.all()
    ]

    # ── 分析任务统计 ──
    analysis_count_result = await db.execute(
        select(func.count(AnalysisTask.id))
    )
    analysis_total = analysis_count_result.scalar() or 0

    completed_result = await db.execute(
        select(func.count(AnalysisTask.id)).where(AnalysisTask.status == 'completed')
    )
    completed_count = completed_result.scalar() or 0

    failed_result = await db.execute(
        select(func.count(AnalysisTask.id)).where(AnalysisTask.status == 'failed')
    )
    failed_count = failed_result.scalar() or 0

    # 平均分析耗时（秒）—— 对 completed 任务计算 started_at → completed_at
    avg_duration_result = await db.execute(
        select(
            func.avg(
                func.julianday(AnalysisTask.completed_at) * 86400
                - func.julianday(AnalysisTask.started_at) * 86400
            )
        ).where(
            AnalysisTask.status == 'completed',
            AnalysisTask.started_at.isnot(None),
            AnalysisTask.completed_at.isnot(None),
        )
    )
    avg_duration = avg_duration_result.scalar()
    avg_duration_seconds = round(float(avg_duration), 1) if avg_duration else 0

    # 分析次数趋势（近6月按月）
    analysis_trend_result = await db.execute(
        select(
            func.strftime('%Y-%m', AnalysisTask.created_at).label('month'),
            func.count(AnalysisTask.id).label('cnt'),
        )
        .where(AnalysisTask.created_at >= six_months_ago)
        .group_by(text('month'))
        .order_by(text('month'))
    )
    analysis_monthly_trend = [
        {"month": row.month, "count": row.cnt}
        for row in analysis_trend_result.all()
    ]

    return ApiResponse.success(data={
        "task_count": task_count,
        "report_count": report_count,
        "document_count": document_count,
        "risk_distribution": risk_distribution,
        "monthly_trend": monthly_trend,
        "analysis_stats": {
            "total": analysis_total,
            "completed": completed_count,
            "failed": failed_count,
            "avg_duration_seconds": avg_duration_seconds,
            "success_rate": round(completed_count / analysis_total * 100, 1) if analysis_total > 0 else 0,
        },
        "analysis_monthly_trend": analysis_monthly_trend,
    })
