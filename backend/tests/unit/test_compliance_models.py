"""测试 Compliance 数据模型"""
import pytest

from app.models.compliance import ComplianceAnalysis, ComplianceClause, ComplianceRule

pytestmark = pytest.mark.asyncio


class TestComplianceRule:
    async def test_create_rule(self, db_session_factory):
        async with db_session_factory() as db:
            rule = ComplianceRule(
                id="R01", name="发售期不足", category="deterministic",
                is_active=True, default_risk="red", weight=0.20,
                conditions={"clause_type": "timeline"},
                params={"min_days": 5},
                legal_basis=[{"law": "实施条例", "article": "第16条"}],
            )
            db.add(rule)
            await db.commit()
            await db.refresh(rule)
            assert rule.id == "R01"
            assert rule.is_active is True
            assert rule.params["min_days"] == 5


class TestComplianceAnalysis:
    async def test_create_analysis(self, db_session_factory, sample_project, sample_documents):
        doc1, _ = sample_documents
        import uuid
        async with db_session_factory() as db:
            analysis = ComplianceAnalysis(
                id=str(uuid.uuid4()),
                project_id=sample_project.id,
                document_id=doc1.id,
                status="pending",
            )
            db.add(analysis)
            await db.commit()
            await db.refresh(analysis)
            assert analysis.status == "pending"

    async def test_analysis_has_clauses(self, db_session_factory, sample_project, sample_documents):
        doc1, _ = sample_documents
        import uuid
        a_id = str(uuid.uuid4())
        async with db_session_factory() as db:
            analysis = ComplianceAnalysis(
                id=a_id, project_id=sample_project.id, document_id=doc1.id,
            )
            db.add(analysis)
            await db.commit()

            clause = ComplianceClause(
                id=str(uuid.uuid4()), analysis_id=a_id,
                clause_type="qualification",
                original_text="投标人须具有壹级资质",
                params={"资质等级": "壹级"},
                risk_level="yellow",
            )
            db.add(clause)
            await db.commit()

            # 直接查询 clauses 避免 async lazy-load
            from sqlalchemy import select
            stmt = select(ComplianceClause).where(ComplianceClause.analysis_id == a_id)
            result = await db.execute(stmt)
            clauses = result.scalars().all()
            assert len(clauses) == 1
            assert clauses[0].clause_type == "qualification"
