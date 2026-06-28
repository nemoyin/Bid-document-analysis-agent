"""
TDD Phase 2B：表格相似度单元测试。

测试 _jaccard_sets、_flatten_cells、compare_table_pair、
compute_document_table_similarity、analyze_table_similarity。
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.analysis import SimilarityResult
from app.services.analysis.table_similarity import (
    _flatten_cells,
    _jaccard_sets,
    analyze_table_similarity,
    compare_table_pair,
    compute_document_table_similarity,
)

# ── 纯函数测试（同步） ────────────────────────────────────────────────

class TestJaccardSets:
    """_jaccard_sets() 单元测试。"""

    def test_identical(self):
        assert _jaccard_sets({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint(self):
        assert _jaccard_sets({"a"}, {"b"}) == 0.0

    def test_half_overlap(self):
        assert _jaccard_sets({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3, abs=0.01)

    def test_empty(self):
        assert _jaccard_sets(set(), {"a"}) == 0.0
        assert _jaccard_sets(set(), set()) == 0.0


class TestFlattenCells:
    """_flatten_cells() 单元测试。"""

    def test_normal_table(self):
        data = [["A", "B"], ["C", "D"]]
        result = _flatten_cells(data)
        assert result == {"A", "B", "C", "D"}

    def test_empty_cells_excluded(self):
        data = [["A", ""], ["", "B"]]
        result = _flatten_cells(data)
        assert result == {"A", "B"}

    def test_whitespace_trimmed(self):
        data = [[" A ", " B "]]
        result = _flatten_cells(data)
        assert result == {"A", "B"}

    def test_empty_table(self):
        assert _flatten_cells([]) == set()


class TestCompareTablePair:
    """compare_table_pair() 单元测试。"""

    def test_identical_tables(self):
        """完全相同的表格。"""
        table = [["序号", "姓名", "职务"], ["1", "张三", "经理"], ["2", "李四", "工程师"]]
        result = compare_table_pair(table, table)
        assert result["header_sim"] == 1.0
        assert result["structure_sim"] == 1.0
        assert result["content_sim"] == 1.0
        assert result["overall"] == pytest.approx(1.0, abs=0.01)

    def test_different_headers_same_data(self):
        """表头不同，数据相同 → 整体分应较低。"""
        table_a = [["序号", "姓名", "职务"], ["1", "张三", "经理"]]
        table_b = [["编号", "名称", "职位"], ["1", "张三", "经理"]]
        result = compare_table_pair(table_a, table_b)
        assert result["header_sim"] < 0.5  # 表头不匹配
        assert result["overall"] < 0.6

    def test_different_sizes(self):
        """不同行列数。"""
        table_a = [["A", "B"], ["1", "2"]]
        table_b = [["A", "B", "C", "D"], ["1", "2", "3", "4"], ["5", "6", "7", "8"]]
        result = compare_table_pair(table_a, table_b)
        assert result["structure_sim"] < 0.6
        assert result["overall"] < 0.7

    def test_empty_input(self):
        """空输入优雅处理。"""
        result = compare_table_pair([], [["A", "B"]])
        assert result["overall"] == 0.0
        result = compare_table_pair([], [])
        assert result["overall"] == 0.0

    def test_returns_all_keys(self):
        """返回字典包含所有预期键。"""
        table = [["A", "B"], ["1", "2"]]
        result = compare_table_pair(table, table)
        for key in ["header_sim", "structure_sim", "content_sim", "overall"]:
            assert key in result
            assert isinstance(result[key], float)
            assert 0.0 <= result[key] <= 1.0

    def test_single_row_table(self):
        """只有表头的单行表格。"""
        table = [["A", "B"]]  # 仅表头，无数据行
        result = compare_table_pair(table, table)
        assert result["header_sim"] == 1.0


class TestComputeDocumentTableSimilarity:
    """compute_document_table_similarity() 单元测试。"""

    def test_no_tables(self):
        """空表格列表。"""
        score = compute_document_table_similarity([], [])
        assert score == 0.0

    def test_one_table_each(self):
        """每文档一个表格。"""
        ta = [{"data": [["序号", "姓名"], ["1", "张三"]]}]
        tb = [{"data": [["序号", "姓名"], ["1", "张三"]]}]
        score = compute_document_table_similarity(ta, tb)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_table_without_data_key(self):
        """表格缺少 data 字段。"""
        ta = [{"rows": 2}]
        tb = [{"data": [["A"]]}]
        score = compute_document_table_similarity(ta, tb)
        assert score == 0.0

    def test_best_match_averaging(self):
        """取最佳匹配的平均值。"""
        ta = [{"data": [["A", "B"], ["1", "2"]]}]
        tb = [
            {"data": [["A", "B"], ["3", "4"]]},   # 相同表头不同数据
            {"data": [["X", "Y"], ["1", "2"]]},   # 不同表头
        ]
        score = compute_document_table_similarity(ta, tb)
        assert 0.0 < score <= 1.0


# ── DB 集成测试（异步） ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestAnalyzeTableSimilarity:
    """analyze_table_similarity() 集成测试。"""

    async def test_returns_zero_for_few_documents(self, db_session_factory, sample_project):
        """文档不足2个时返回0。"""
        count = await analyze_table_similarity(
            project_id=sample_project.id,
            analysis_task_id=uuid.uuid4(),
            db_session_factory=db_session_factory,
        )
        assert count == 0

    async def test_updates_table_similarity(
        self, db_session_factory, sample_project, sample_documents,
    ):
        """有表格数据的文档应更新 SimilarityResult.table_similarity。"""
        doc1, doc2 = sample_documents
        task_id = uuid.uuid4()

        # 先创建 SimilarityResult
        async with db_session_factory() as db:
            sim = SimilarityResult(
                id=str(uuid.uuid4()),
                task_id=str(task_id),
                doc1_id=doc1.id,
                doc2_id=doc2.id,
                full_text_similarity=60.00,
            )
            db.add(sim)
            await db.commit()

        count = await analyze_table_similarity(
            project_id=sample_project.id,
            analysis_task_id=task_id,
            db_session_factory=db_session_factory,
        )
        assert count >= 1

        # 验证 table_similarity 已被填充
        async with db_session_factory() as db:
            stmt = select(SimilarityResult).where(
                SimilarityResult.task_id == str(task_id),
            )
            result = await db.execute(stmt)
            sim = result.scalar_one_or_none()
            assert sim is not None
            assert sim.table_similarity is not None
            assert 0 <= float(sim.table_similarity) <= 100
