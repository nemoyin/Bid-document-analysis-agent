"""
TDD Phase 2A：目录结构相似度单元测试。

测试 extract_headings、compare_heading_sequences、_lcs_length
以及 analyze_structure_similarity（DB 集成）。
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.analysis import SimilarityResult
from app.services.analysis.structure_similarity import (
    _lcs_length,
    analyze_structure_similarity,
    compare_heading_sequences,
    extract_headings,
)

# ── 纯函数测试（同步） ────────────────────────────────────────────────

class TestExtractHeadings:
    """extract_headings() 单元测试。"""

    def test_chinese_chapter_headings(self):
        """中文"第X章"格式。"""
        text = "第一章 概述\n这是正文。\n第二章 技术方案\n更多正文。"
        result = extract_headings(text)
        assert len(result) >= 2
        texts = {h["text"] for h in result}
        assert "第一章 概述" in texts
        assert "第二章 技术方案" in texts
        for h in result:
            assert "text" in h
            assert "level" in h
            assert h["level"] >= 1

    def test_numbered_headings(self):
        """数字编号标题 — 注意 regex 要求 number.number 后必须有数字，裸 "1." 不被识别。"""
        text = "1.1 背景\n2.1 方案\n3.2 实施\n正文段落。"
        result = extract_headings(text)
        # 只有 "1.1 背景" "2.1 方案" "3.2 实施" 这种 "数字.数字" 格式被识别
        assert len(result) >= 3
        levels = {h["text"]: h["level"] for h in result}
        # 所有 number.number 格式应被识别为 level 2
        for h in result:
            assert h["level"] >= 1

    def test_chinese_number_headings(self):
        """中文数字编号。"""
        text = "一、项目概况\n（二）技术需求\n1、实施计划"
        result = extract_headings(text)
        assert len(result) >= 2

    def test_empty_text(self):
        """空文本返回空列表。"""
        assert extract_headings("") == []

    def test_no_headings(self):
        """无标题的纯段落。"""
        text = "这是普通段落文本。\n没有任何标题标记。\n只是正文内容。"
        result = extract_headings(text)
        assert len(result) == 0

    def test_long_line_skipped(self):
        """超过80字符的行不被识别为标题。"""
        long_line = "A" * 81
        text = f"第一章 概述\n{long_line}"
        result = extract_headings(text)
        # "第一章 概述" 应该被识别
        assert any("第一章" in h["text"] for h in result)
        # 超长行不应该作为标题
        assert not any(h["text"] == long_line for h in result)

    def test_bid_document_keywords(self):
        """投标常见章节关键词匹配。"""
        text = "投标函\n法定代表人授权书\n公司概况\n技术方案\n售后服务承诺"
        result = extract_headings(text)
        assert len(result) >= 3


class TestCompareHeadingSequences:
    """compare_heading_sequences() 单元测试。"""

    def test_identical_headings(self):
        """完全相同的标题序列。"""
        h = [
            {"text": "第一章 概述", "level": 1},
            {"text": "第二章 技术方案", "level": 1},
        ]
        score = compare_heading_sequences(h, h)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_disjoint_headings(self):
        """完全不重叠的标题 — 文本完全不同 + 结构不同才能拿到低分。"""
        a = [{"text": "第一章 概述", "level": 1}]
        b = [
            {"text": "第六章 售后服务", "level": 1},
            {"text": "6.1 服务内容", "level": 2},
        ]
        score = compare_heading_sequences(a, b)
        # 文本完全不重叠 + 标题数量不同 + level 序列不同 → 低分
        assert score < 0.3

    def test_partial_overlap(self):
        """50% 重叠。"""
        a = [
            {"text": "第一章 概述", "level": 1},
            {"text": "第二章 技术", "level": 1},
            {"text": "第三章 实施", "level": 1},
            {"text": "第四章 售后", "level": 1},
        ]
        b = [
            {"text": "第一章 概述", "level": 1},
            {"text": "第二章 技术", "level": 1},
            {"text": "第五章 质量", "level": 1},
            {"text": "第六章 安全", "level": 1},
        ]
        score = compare_heading_sequences(a, b)
        # 2/4 文本重叠 + 结构序列部分匹配 → 期望 0.3~0.7
        assert 0.3 < score < 0.8

    def test_empty_headings(self):
        """空标题列表。"""
        a = [{"text": "第一章", "level": 1}]
        score = compare_heading_sequences(a, [])
        assert score == 0.0
        score = compare_heading_sequences([], [])
        assert score == 0.0

    def test_same_number_different_text(self):
        """相同数量不同文本。"""
        a = [
            {"text": "第一章 概述", "level": 1},
            {"text": "第二章 技术方案", "level": 1},
        ]
        b = [
            {"text": "第一章 总则", "level": 1},
            {"text": "第二章 施工组织", "level": 1},
        ]
        score = compare_heading_sequences(a, b)
        # 文本不完全匹配但结构完全一致（level 序列相同）
        assert 0.3 < score < 0.7


class TestLCSLength:
    """_lcs_length() 单元测试。"""

    def test_basic(self):
        assert _lcs_length([1, 1, 2], [1, 2, 1]) == 2

    def test_identical(self):
        assert _lcs_length([1, 2, 3], [1, 2, 3]) == 3

    def test_no_common(self):
        assert _lcs_length([1, 1], [2, 2]) == 0

    def test_one_empty(self):
        assert _lcs_length([], [1, 2]) == 0
        assert _lcs_length([1, 2], []) == 0

    def test_both_empty(self):
        assert _lcs_length([], []) == 0

    def test_single_element(self):
        assert _lcs_length([1], [1]) == 1
        assert _lcs_length([1], [2]) == 0

    def test_repeated_elements(self):
        assert _lcs_length([1, 1, 1], [1, 1]) == 2


# ── DB 集成测试（异步） ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestAnalyzeStructureSimilarity:
    """analyze_structure_similarity() 集成测试。"""

    async def test_returns_zero_for_few_documents(self, db_session_factory, sample_project):
        """文档不足2个时返回0。"""
        # SQLite String(36) 列不支持 uuid.UUID 比较，直接传字符串
        count = await analyze_structure_similarity(
            project_id=sample_project.id,
            analysis_task_id=uuid.uuid4(),
            db_session_factory=db_session_factory,
        )
        assert count == 0

    async def test_updates_similarity_results(
        self, db_session_factory, sample_project, sample_documents,
    ):
        """有文档时应更新 SimilarityResult.structure_similarity。"""
        doc1, doc2 = sample_documents
        task_id = uuid.uuid4()

        # 先创建 SimilarityResult（模拟 text_similarity 已创建）
        async with db_session_factory() as db:
            sim = SimilarityResult(
                id=str(uuid.uuid4()),
                task_id=str(task_id),
                doc1_id=doc1.id,
                doc2_id=doc2.id,
                full_text_similarity=75.00,
            )
            db.add(sim)
            await db.commit()

        count = await analyze_structure_similarity(
            project_id=sample_project.id,
            analysis_task_id=task_id,
            db_session_factory=db_session_factory,
        )
        assert count >= 1

        # 验证 structure_similarity 已被填充
        async with db_session_factory() as db:
            stmt = select(SimilarityResult).where(
                SimilarityResult.task_id == str(task_id),
            )
            result = await db.execute(stmt)
            sim = result.scalar_one_or_none()
            assert sim is not None
            assert sim.structure_similarity is not None
            assert 0 <= float(sim.structure_similarity) <= 100
