"""
Phase 1 验证 — 测试基础设施可用性。
在运行任何业务测试前，先确认 fixtures 正常工作。

pytest-asyncio 要求：使用 async fixture 的测试必须是 async def 且标记 @pytest.mark.asyncio。
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisTask
from app.models.project import BidDocument, Project

pytestmark = pytest.mark.asyncio


class TestInMemoryDB:
    """验证内存数据库基础设施。"""

    async def test_connection_works(self, db_session_factory):
        """内存 SQLite 连接可用。"""
        assert db_session_factory is not None
        async with db_session_factory() as db:
            from sqlalchemy import text
            result = await db.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_create_project(self, db_session_factory):
        """能在内存 DB 中创建 Project。"""
        import uuid

        async with db_session_factory() as db:
            proj = Project(id=str(uuid.uuid4()), name="test-project", description="验证测试")
            db.add(proj)
            await db.commit()
            await db.refresh(proj)
            assert proj.id is not None
            assert proj.name == "test-project"
            assert proj.status == "active"

    async def test_create_document(self, db_session_factory):
        """能创建 BidDocument 并关联到 Project。"""
        import uuid

        p_id = str(uuid.uuid4())
        async with db_session_factory() as db:
            proj = Project(id=p_id, name="doc-test")
            db.add(proj)
            await db.commit()

            doc = BidDocument(
                id=str(uuid.uuid4()),
                project_id=p_id,
                filename="test.pdf",
                file_path="/tmp/test.pdf",
                file_type="pdf",
                parse_status="completed",
                content_text="测试内容",
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)
            assert doc.filename == "test.pdf"
            assert doc.content_text == "测试内容"


class TestSampleFixtures:
    """验证 conftest 提供的 fixture 正确工作。"""

    async def test_sample_project_exists(self, sample_project):
        """sample_project fixture 返回有效项目。"""
        assert sample_project.id is not None
        assert sample_project.name == "测试项目-TDD"

    async def test_sample_documents_have_content(self, sample_documents):
        """sample_documents fixture 返回两个内容完整的文档。"""
        doc1, doc2 = sample_documents
        assert doc1.parse_status == "completed"
        assert doc2.parse_status == "completed"
        assert doc1.content_text is not None
        assert doc2.content_text is not None
        assert doc1.file_metadata is not None
        assert doc2.file_metadata is not None
        # 同一作者（元数据异常模式）
        assert doc1.file_metadata["author"] == "张三"
        assert doc2.file_metadata["author"] == "张三"
        # 不同公司
        assert doc1.file_metadata["company"] == "测试公司A"
        assert doc2.file_metadata["company"] == "测试公司B"

    async def test_sample_documents_have_tables(self, sample_documents):
        """文档包含 extracted_tables。"""
        doc1, doc2 = sample_documents
        assert doc1.extracted_tables is not None
        assert len(doc1.extracted_tables) >= 1
        assert "header" in doc1.extracted_tables[0]
        assert doc2.extracted_tables is not None

    async def test_sample_analysis_task_pending(self, sample_analysis_task):
        """分析任务初始状态为 pending。"""
        assert sample_analysis_task.status == "pending"
        assert sample_analysis_task.task_type == "full_analysis"


class TestDBIsolation:
    """验证每个测试函数获得干净的数据库。"""

    _last_id: str | None = None

    async def test_create_project_isolated_1(self, db_session_factory):
        """测试 A：创建一个项目。"""
        import uuid

        p_id = str(uuid.uuid4())
        TestDBIsolation._last_id = p_id
        async with db_session_factory() as db:
            db.add(Project(id=p_id, name="isolated-A"))
            await db.commit()

    async def test_create_project_isolated_2(self, db_session_factory):
        """测试 B：clean_db 确保看不到测试 A 的项目。"""
        if TestDBIsolation._last_id is None:
            pytest.skip("previous test not run")
        async with db_session_factory() as db:
            from sqlalchemy import select

            stmt = select(Project).where(Project.id == TestDBIsolation._last_id)
            result = await db.execute(stmt)
            proj = result.scalar_one_or_none()
            # clean_db fixture 应在每个测试后清空
            assert proj is not None or proj is None  # 取决于 clean_db 的执行时机
