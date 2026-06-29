"""合规审查编排器 — 完整分析管线"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.core.compliance_config import get_active_clause_types, get_active_rules
from app.models.compliance import ComplianceAnalysis, ComplianceClause
from app.models.project import BidDocument
from app.services.analysis.compliance_clause_extractor import extract_clauses_async
from app.services.analysis.compliance_rule_engine import run_rule_engine
from app.services.analysis.compliance_scorer import calculate_compliance_score


class ComplianceOrchestrator:
    """合规审查编排器 — 完整分析管线。"""

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    async def run_analysis(self, analysis_id: str) -> dict[str, Any]:
        """执行完整合规审查管线。

        管线：文档文本 → 条款提取 → 规则引擎 → 评分 → 持久化
        """
        async with self.db_session_factory() as db:
            stmt = select(ComplianceAnalysis).where(
                ComplianceAnalysis.id == analysis_id
            )
            result = await db.execute(stmt)
            analysis = result.scalar_one_or_none()
            if not analysis:
                return {"status": "error", "message": "分析任务不存在"}

            analysis.status = "analyzing"
            analysis.progress = 0
            analysis.started_at = datetime.now(timezone.utc)
            await db.commit()

            doc_stmt = select(BidDocument).where(
                BidDocument.id == analysis.document_id
            )
            doc_result = await db.execute(doc_stmt)
            doc = doc_result.scalar_one_or_none()
            if not doc or not doc.content_text:
                analysis.status = "failed"
                analysis.error_message = "文档未解析或内容为空"
                await db.commit()
                return {"status": "failed", "error": "no_content"}

            document_text = doc.content_text

        # ---- 阶段1：条款提取 ----
        clause_types = get_active_clause_types()
        clauses_raw = await extract_clauses_async(document_text, clause_types)
        logger.info(f"条款提取完成: {len(clauses_raw)} 条")

        # ---- 阶段2：规则引擎判定 ----
        rules = get_active_rules()
        clauses_evaluated = run_rule_engine(clauses_raw, rules)
        logger.info(f"规则引擎判定完成: {len(clauses_evaluated)} 条")

        # ---- 阶段3：综合评分 ----
        score_result = calculate_compliance_score(clauses_evaluated)

        # ---- 阶段4：持久化结果 ----
        async with self.db_session_factory() as db:
            for clause_data in clauses_evaluated:
                clause = ComplianceClause(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    clause_type=clause_data.get("type", "other"),
                    original_text=clause_data.get("original_text", ""),
                    location=clause_data.get("location"),
                    params=clause_data.get("params"),
                    risk_level=clause_data.get("risk_level", "green"),
                    matched_rules=clause_data.get("matched_rules", []),
                )
                db.add(clause)

            analysis.status = "completed"
            analysis.progress = 100
            analysis.compliance_score = Decimal(str(score_result["score"]))
            analysis.risk_level = score_result["risk_level"]
            analysis.clause_count = score_result["total_count"]
            analysis.violation_count = (
                score_result["red_count"] + score_result["yellow_count"]
            )
            analysis.completed_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info(
            f"合规审查完成: score={score_result['score']}, "
            f"level={score_result['risk_level']}, "
            f"clauses={score_result['total_count']}"
        )
        return {"status": "completed", **score_result}
