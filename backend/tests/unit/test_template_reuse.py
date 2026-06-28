"""
TDD Phase 5A：模板复用分析单元测试（先写测试，后实现）。

测试 extract_docx_template_features、extract_pdf_template_features、
compare_template_features、analyze_template_reuse。
"""

import uuid
from io import BytesIO

import pytest
import pytest_asyncio
from docx import Document
from docx.shared import Inches
from sqlalchemy import select

from app.models.analysis import SimilarityResult, TemplateReuseResult

# 被测试的模块在 Phase 5B 中实现，这些导入当前会失败（TDD Red 阶段）
# 运行前需确认模块存在或跳过导入
try:
    from app.services.analysis.template_reuse import (
        compare_template_features,
        extract_docx_template_features,
        extract_pdf_template_features,
        analyze_template_reuse,
    )
    TEMPLATE_REUSE_AVAILABLE = True
except ImportError:
    TEMPLATE_REUSE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not TEMPLATE_REUSE_AVAILABLE,
    reason="template_reuse 模块尚未实现（TDD Green 阶段前）",
)


# ── 纯函数测试 ────────────────────────────────────────────────────────

class TestExtractDocxTemplateFeatures:
    """extract_docx_template_features() 单元测试。"""

    def test_extracts_styles_from_docx(self, docx_bytes_template_a):
        """从 DOCX 提取样式特征。"""
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(docx_bytes_template_a)
            tmp_path = f.name
        try:
            features = extract_docx_template_features(tmp_path)
            assert "styles" in features
            assert "layout" in features
            assert "sections" in features
            assert "heading_structure" in features
        finally:
            os.unlink(tmp_path)

    def test_extracts_layout_margins(self, docx_bytes_template_a):
        """页边距提取正确 — 预期 1.0in top, 1.25in left。"""
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(docx_bytes_template_a)
            tmp_path = f.name
        try:
            features = extract_docx_template_features(tmp_path)
            layout = features["layout"]
            assert abs(layout.get("margin_top", 0) - 1.0) < 0.2
            assert abs(layout.get("margin_left", 0) - 1.25) < 0.3
        finally:
            os.unlink(tmp_path)

    def test_empty_for_corrupt_file(self):
        """无效文件返回空特征。"""
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"not a valid docx file")
            tmp_path = f.name
        try:
            features = extract_docx_template_features(tmp_path)
            # 应返回空字典或所有值均为空
            assert isinstance(features, dict)
        finally:
            os.unlink(tmp_path)


class TestCompareTemplateFeatures:
    """compare_template_features() 单元测试。"""

    def test_identical_features(self):
        """相同特征 → 得分 1.0。"""
        fa = {
            "styles": {"Normal": {"font_name": "SimSun", "font_size": 12}},
            "layout": {"margin_top": 1.0, "margin_bottom": 1.0, "margin_left": 1.25, "margin_right": 1.25},
            "sections": [{"type": "continuous"}],
            "heading_structure": [{"text": "第一章 概述", "level": 1}],
        }
        result = compare_template_features(fa, fa)
        assert result["reuse_score"] == pytest.approx(1.0, abs=0.01)
        assert result["style_match_score"] == pytest.approx(1.0, abs=0.01)
        assert result["layout_match_score"] == pytest.approx(1.0, abs=0.01)

    def test_different_fonts(self):
        """不同字体 → 样式分低。"""
        fa = {"styles": {"Normal": {"font_name": "SimSun", "font_size": 12}}, "layout": {}, "sections": [], "heading_structure": []}
        fb = {"styles": {"Normal": {"font_name": "Arial", "font_size": 11}}, "layout": {}, "sections": [], "heading_structure": []}
        result = compare_template_features(fa, fb)
        assert result["style_match_score"] < 0.5

    def test_different_layout(self):
        """不同页边距 → 布局分低。"""
        fa = {"styles": {}, "layout": {"margin_top": 1.0, "margin_left": 1.0}, "sections": [], "heading_structure": []}
        fb = {"styles": {}, "layout": {"margin_top": 2.0, "margin_left": 2.0}, "sections": [], "heading_structure": []}
        result = compare_template_features(fa, fb)
        assert result["layout_match_score"] < 0.5

    def test_empty_features(self):
        """空特征 → 0 分。"""
        r = compare_template_features({}, {})
        assert r["reuse_score"] == 0.0

    def test_returns_all_sub_scores(self):
        """返回字典包含所有预期键。"""
        fa = {"styles": {}, "layout": {}, "sections": [], "heading_structure": []}
        r = compare_template_features(fa, fa)
        for key in ["reuse_score", "style_match_score", "layout_match_score",
                     "heading_match_score", "section_match_score"]:
            assert key in r
            assert isinstance(r[key], float)
            assert 0.0 <= r[key] <= 1.0

    def test_weighted_composite(self):
        """验证加权融合：样式(0.4) + 布局(0.3) + 标题(0.2) + 节(0.1)。"""
        fa = {
            "styles": {"A": {"font_name": "SimSun"}},
            "layout": {"margin_top": 1.0},
            "sections": [],
            "heading_structure": [],
        }
        fb = {
            "styles": {"B": {"font_name": "Arial"}},  # 不同样式
            "layout": {"margin_top": 1.0},             # 相同布局
            "sections": [],
            "heading_structure": [],
        }
        result = compare_template_features(fa, fb)
        # 仅 layout 匹配（0.3 权重） + section 匹配（0.1 权重，都为空）= 0.4
        assert 0.3 < result["reuse_score"] < 0.6


# ── DB 集成测试 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAnalyzeTemplateReuse:
    """analyze_template_reuse() 集成测试。"""

    async def test_returns_zero_for_few_documents(self, db_session_factory, sample_project):
        """文档不足2个时返回0。"""
        count = await analyze_template_reuse(
            project_id=sample_project.id,
            analysis_task_id=uuid.uuid4(),
            db_session_factory=db_session_factory,
        )
        assert count == 0
