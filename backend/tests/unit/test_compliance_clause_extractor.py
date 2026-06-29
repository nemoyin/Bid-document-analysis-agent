"""测试条款提取器"""
import pytest
from app.services.analysis.compliance_clause_extractor import coarse_split, build_extraction_prompt


class TestCoarseSplit:
    def test_split_by_chapter_headings(self):
        text = "第一章 招标公告\n1.1 项目概况\n这是招标项目的背景描述。\n\n第二章 投标人须知\n2.1 资格条件\n投标人须具有相关资质。"
        chunks = coarse_split(text)
        assert len(chunks) >= 2
        assert any("第一章" in c["title"] for c in chunks)
        assert any("第二章" in c["title"] for c in chunks)

    def test_split_by_numbered_sections(self):
        text = "1. 总则\n这是总则内容。\n\n2. 资格要求\n2.1 基本条件\n需要营业执照。\n2.2 业绩要求\n需要3个同类项目。"
        chunks = coarse_split(text)
        assert len(chunks) >= 2

    def test_empty_text(self):
        assert coarse_split("") == []

    def test_whitespace_only(self):
        assert coarse_split("   \n  \n ") == []

    def test_single_section_no_headings(self):
        text = "无章节标题的简单招标文件内容。\n只有几个段落。"
        chunks = coarse_split(text)
        assert len(chunks) == 1
        assert chunks[0]["title"] == "全文"

    def test_output_structure(self):
        text = "第一章 招标公告\n这是内容。"
        chunks = coarse_split(text)
        for c in chunks:
            assert "title" in c
            assert "content" in c
            assert "start_line" in c

    def test_short_text(self):
        text = "短文本"
        chunks = coarse_split(text)
        assert len(chunks) == 1


class TestBuildExtractionPrompt:
    def test_prompt_contains_clause_text(self):
        prompt = build_extraction_prompt(
            "投标人须具有壹级资质",
            [{"id": "qualification", "label": "资格条件"}],
        )
        assert "壹级资质" in prompt
        assert "qualification" in prompt
        assert "资格条件" in prompt

    def test_prompt_contains_all_types(self):
        types = [
            {"id": "qualification", "label": "资格条件"},
            {"id": "performance", "label": "业绩要求"},
        ]
        prompt = build_extraction_prompt("测试内容", types)
        assert "资格条件" in prompt
        assert "业绩要求" in prompt
