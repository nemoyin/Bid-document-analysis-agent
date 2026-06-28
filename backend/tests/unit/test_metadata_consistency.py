"""
TDD Phase 2C：元数据一致性单元测试。

测试 compare_metadata、analyze_metadata_consistency。
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.analysis import SimilarityResult
from app.services.analysis.metadata_consistency import (
    _METADATA_FIELDS,
    analyze_metadata_consistency,
    compare_metadata,
)

# ── 纯函数测试（同步） ────────────────────────────────────────────────

class TestCompareMetadata:
    """compare_metadata() 单元测试。"""

    def test_all_fields_match(self):
        """所有6个字段均匹配。"""
        meta = {
            "author": "张三",
            "creator": "Microsoft Word",
            "producer": "Microsoft Word",
            "title": "投标文件",
            "company": "测试公司",
            "last_modified_by": "张三",
        }
        result = compare_metadata(meta, meta)
        assert result["overall_score"] == pytest.approx(1.0, abs=0.01)
        assert len(result["matched_fields"]) == 6

    def test_only_author_matches(self):
        """仅 author 字段匹配。"""
        meta_a = {
            "author": "张三",
            "creator": "WPS Office",
            "producer": "WPS",
            "title": "文件A",
            "company": "公司A",
            "last_modified_by": "李四",
        }
        meta_b = {
            "author": "张三",
            "creator": "Microsoft Word",
            "producer": "Microsoft Word",
            "title": "文件B",
            "company": "公司B",
            "last_modified_by": "王五",
        }
        result = compare_metadata(meta_a, meta_b)
        assert result["matched_fields"] == ["author"]
        # author 权重 0.30 → 分数应该 >= 0.25
        assert 0.2 < result["overall_score"] < 0.5

    def test_none_match(self):
        """全部字段不同。"""
        meta_a = {"author": "张三", "creator": "WPS", "company": "公司A"}
        meta_b = {"author": "李四", "creator": "Word", "company": "公司B"}
        result = compare_metadata(meta_a, meta_b)
        assert result["matched_fields"] == []
        assert result["overall_score"] == 0.0

    def test_empty_dicts(self):
        """空元数据。"""
        result = compare_metadata({}, {})
        assert result["overall_score"] == 0.0
        assert result["matched_fields"] == []

    def test_case_insensitive(self):
        """大小写不敏感。"""
        meta_a = {"author": "ZHANGSAN"}
        meta_b = {"author": "zhangsan"}
        result = compare_metadata(meta_a, meta_b)
        assert "author" in result["matched_fields"]

    def test_whitespace_trimmed(self):
        """前后空格忽略。"""
        meta_a = {"author": "张三 "}
        meta_b = {"author": "张三"}
        result = compare_metadata(meta_a, meta_b)
        assert "author" in result["matched_fields"]

    def test_missing_field_handled(self):
        """某些字段缺失不影响比对。"""
        meta_a = {"author": "张三"}
        meta_b = {"author": "张三", "company": "公司A"}
        result = compare_metadata(meta_a, meta_b)
        # author 匹配
        assert "author" in result["matched_fields"]

    def test_details_structure(self):
        """返回的 details 包含期望字段。"""
        meta_a = {"author": "张三", "company": "公司A"}
        meta_b = {"author": "李四", "company": "公司A"}
        result = compare_metadata(meta_a, meta_b)
        assert "details" in result
        assert "matched_fields" in result
        assert "overall_score" in result
        # details 中的每项应有 field 和 matched
        for d in result["details"]:
            assert "field" in d
            assert "matched" in d

    def test_field_weights_present(self):
        """_METADATA_FIELDS 包含6个预期字段。"""
        assert len(_METADATA_FIELDS) == 6
        assert "author" in _METADATA_FIELDS
        assert "creator" in _METADATA_FIELDS
        assert "producer" in _METADATA_FIELDS
        assert "title" in _METADATA_FIELDS
        assert "company" in _METADATA_FIELDS
        assert "last_modified_by" in _METADATA_FIELDS


# ── DB 集成测试（异步） ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestAnalyzeMetadataConsistency:
    """analyze_metadata_consistency() 集成测试。"""

    async def test_returns_zero_for_few_documents(self, db_session_factory, sample_project):
        """文档不足2个时返回0。"""
        count = await analyze_metadata_consistency(
            project_id=sample_project.id,
            analysis_task_id=uuid.uuid4(),
            db_session_factory=db_session_factory,
        )
        assert count == 0

    async def test_updates_metadata_consistency(
        self, db_session_factory, sample_project, sample_documents,
    ):
        """有元数据的文档应更新 SimilarityResult.metadata_consistency。"""
        doc1, doc2 = sample_documents
        task_id = uuid.uuid4()

        # 先创建 SimilarityResult
        async with db_session_factory() as db:
            sim = SimilarityResult(
                id=str(uuid.uuid4()),
                task_id=str(task_id),
                doc1_id=doc1.id,
                doc2_id=doc2.id,
                full_text_similarity=50.00,
            )
            db.add(sim)
            await db.commit()

        count = await analyze_metadata_consistency(
            project_id=sample_project.id,  # SQLite 不支持 uuid.UUID 比较
            analysis_task_id=task_id,
            db_session_factory=db_session_factory,
        )
        assert count >= 1

        # 验证 metadata_consistency 已被填充
        async with db_session_factory() as db:
            stmt = select(SimilarityResult).where(
                SimilarityResult.task_id == str(task_id),
            )
            result = await db.execute(stmt)
            sim = result.scalar_one_or_none()
            assert sim is not None
            assert sim.metadata_consistency is not None
            assert 0 <= float(sim.metadata_consistency) <= 100
            # details 应包含 metadata_comparison
            assert sim.details is not None
            assert "metadata_comparison" in sim.details

    async def test_metadata_anomaly_detected(
        self, db_session_factory, sample_project, sample_documents,
    ):
        """同一作者不同公司 → 高元数据一致性（异常）。"""
        doc1, doc2 = sample_documents
        # 验证 conftest 设置了 author="张三" for both, different companies
        assert doc1.file_metadata["author"] == "张三"
        assert doc2.file_metadata["author"] == "张三"
        assert doc1.file_metadata["company"] != doc2.file_metadata["company"]

        task_id = uuid.uuid4()
        async with db_session_factory() as db:
            sim = SimilarityResult(
                id=str(uuid.uuid4()),
                task_id=str(task_id),
                doc1_id=doc1.id,
                doc2_id=doc2.id,
            )
            db.add(sim)
            await db.commit()

        await analyze_metadata_consistency(
            project_id=sample_project.id,
            analysis_task_id=task_id,
            db_session_factory=db_session_factory,
        )

        async with db_session_factory() as db:
            stmt = select(SimilarityResult).where(
                SimilarityResult.task_id == str(task_id),
            )
            result = await db.execute(stmt)
            sim = result.scalar_one_or_none()
            # 同一作者 + 相同 creator/producer → 得分应显著 > 0
            assert float(sim.metadata_consistency) > 30.0
