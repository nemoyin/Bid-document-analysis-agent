"""合规审查 API"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db, async_session_factory
from app.models.compliance import ComplianceAnalysis, ComplianceClause
from app.schemas.compliance import (
    ComplianceAnalysisCreate,
    ComplianceAnalysisResponse,
    ComplianceClauseResponse,
)
from app.schemas.common import ApiResponse
from app.services.analysis.compliance_orchestrator import ComplianceOrchestrator

router = APIRouter(prefix="/compliance")


async def _run_compliance_background(analysis_id: str) -> None:
    """后台执行合规审查。"""
    orchestrator = ComplianceOrchestrator(db_session_factory=async_session_factory)
    try:
        await orchestrator.run_analysis(analysis_id)
    except Exception as exc:
        import logging
        logging.getLogger("bass").error(f"合规审查后台任务失败: {exc!s}")
        try:
            async with async_session_factory() as db:
                stmt = select(ComplianceAnalysis).where(
                    ComplianceAnalysis.id == analysis_id
                )
                result = await db.execute(stmt)
                analysis = result.scalar_one_or_none()
                if analysis:
                    analysis.status = "failed"
                    analysis.error_message = str(exc)[:500]
                    await db.commit()
        except Exception:
            pass


@router.post("/analyze", response_model=ApiResponse[ComplianceAnalysisResponse])
async def start_compliance_analysis(
    data: ComplianceAnalysisCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """启动招标文件合规审查分析。"""
    analysis = ComplianceAnalysis(
        project_id=data.project_id,
        document_id=data.document_id,
        status="pending",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    background_tasks.add_task(_run_compliance_background, str(analysis.id))

    return ApiResponse.success(
        data=ComplianceAnalysisResponse.model_validate(analysis),
        message="合规审查已启动",
    )


@router.get("/{analysis_id}", response_model=ApiResponse[ComplianceAnalysisResponse])
async def get_compliance_result(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取合规审查分析结果（含条款详情）。"""
    stmt = select(ComplianceAnalysis).where(ComplianceAnalysis.id == analysis_id)
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="分析任务不存在")

    # 单独查询 clauses 避免 async lazy-load 问题
    clause_stmt = (
        select(ComplianceClause)
        .where(ComplianceClause.analysis_id == analysis_id)
        .order_by(ComplianceClause.created_at)
    )
    clause_result = await db.execute(clause_stmt)
    clauses = clause_result.scalars().all()

    # 手动构建响应，避免 relationship lazy-load
    return ApiResponse.success(data=ComplianceAnalysisResponse(
        id=analysis.id,
        project_id=analysis.project_id,
        document_id=analysis.document_id,
        status=analysis.status,
        progress=analysis.progress,
        compliance_score=analysis.compliance_score,
        risk_level=analysis.risk_level,
        clause_count=analysis.clause_count,
        violation_count=analysis.violation_count,
        error_message=analysis.error_message,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
        clauses=[ComplianceClauseResponse.model_validate(c) for c in clauses],
    ))
