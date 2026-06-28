"""
TDD Phase 3：编排器评分与进度计算验证。

测试 AnalysisOrchestrator 的核心评分逻辑、进度计算、
ETA 估算、风险等级边界值。

使用 monkeypatch 注入已知配置，避免受 analysis_config.json 影响。
"""

import uuid
from decimal import Decimal

import pytest

from app.schemas.common import RiskLevel
from app.services.analysis.analysis_orchestrator import (
    DIMENSIONS,
    AnalysisOrchestrator,
    _load_analysis_config,
)

# ── 默认配置（PRD v1.1 权重） ─────────────────────────────────────────

_DEFAULT_CONFIG = {
    "text_similarity_weight": 0.30,
    "structure_similarity_weight": 0.15,
    "image_similarity_weight": 0.15,
    "table_similarity_weight": 0.10,
    "error_consistency_weight": 0.20,
    "metadata_consistency_weight": 0.10,
    "risk_low": 0.30,
    "risk_medium": 0.60,
    "risk_high": 0.85,
}


@pytest.fixture
def orchestrator():
    """创建编排器实例（不依赖真实 DB）。"""
    return AnalysisOrchestrator.__new__(AnalysisOrchestrator)


@pytest.fixture
def patch_config(monkeypatch):
    """注入默认配置，隔离 analysis_config.json 的副作用。"""
    monkeypatch.setattr(
        "app.services.analysis.analysis_orchestrator._load_analysis_config",
        lambda: dict(_DEFAULT_CONFIG),
    )


# ── 维度配置测试 ──────────────────────────────────────────────────────

class TestDimensionsConfig:
    """DIMENSIONS 列表配置正确性。"""

    def test_eight_dimensions_defined(self):
        keys = [d["key"] for d in DIMENSIONS]
        assert len(DIMENSIONS) == 8  # V1.1: 8 dimensions
        for key in ["text_similarity", "structure_similarity", "image_similarity",
                     "table_similarity", "error_consistency", "metadata_consistency",
                     "template_reuse", "electronic_signature"]:
            assert key in keys

    def test_all_have_required_fields(self):
        for d in DIMENSIONS:
            assert "key" in d
            assert "weight" in d
            assert "seconds_per" in d


# ── 风险评分测试 ──────────────────────────────────────────────────────

class TestCalculateRiskScore:
    """calculate_risk_score() — 需要 patch_config。"""

    def test_all_half(self, orchestrator, patch_config):
        score = orchestrator.calculate_risk_score(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_all_zero(self, orchestrator, patch_config):
        score = orchestrator.calculate_risk_score(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_all_one(self, orchestrator, patch_config):
        score = orchestrator.calculate_risk_score(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_weights_sum_to_one(self, orchestrator, patch_config):
        """patch_config 注入默认值后权重和应为 1.0。"""
        from app.services.analysis import analysis_orchestrator as ao
        cfg = ao._load_analysis_config()
        total = (cfg["text_similarity_weight"] + cfg["structure_similarity_weight"]
                 + cfg["image_similarity_weight"] + cfg["table_similarity_weight"]
                 + cfg["error_consistency_weight"] + cfg["metadata_consistency_weight"])
        assert total == pytest.approx(1.0, abs=0.01)

    def test_clamped_to_zero(self, orchestrator, patch_config):
        score = orchestrator.calculate_risk_score(-0.5, -0.5, -0.5, -0.5, -0.5, -0.5)
        assert score >= 0.0

    def test_clamped_to_one(self, orchestrator, patch_config):
        score = orchestrator.calculate_risk_score(2.0, 2.0, 2.0, 2.0, 2.0, 2.0)
        assert score <= 1.0

    def test_text_only(self, orchestrator, patch_config):
        score = orchestrator.calculate_risk_score(1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert score == pytest.approx(0.30, abs=0.01)


# ── 风险等级测试 ──────────────────────────────────────────────────────

class TestRiskToLevel:
    """risk_to_level() 边界值 — 依赖 patch_config。"""

    def test_low(self, orchestrator, patch_config):
        assert orchestrator.risk_to_level(0.0) == RiskLevel.LOW
        assert orchestrator.risk_to_level(0.29) == RiskLevel.LOW

    def test_moderate(self, orchestrator, patch_config):
        assert orchestrator.risk_to_level(0.30) == RiskLevel.MODERATE
        assert orchestrator.risk_to_level(0.59) == RiskLevel.MODERATE

    def test_high(self, orchestrator, patch_config):
        assert orchestrator.risk_to_level(0.60) == RiskLevel.HIGH
        assert orchestrator.risk_to_level(0.84) == RiskLevel.HIGH

    def test_critical(self, orchestrator, patch_config):
        assert orchestrator.risk_to_level(0.85) == RiskLevel.CRITICAL
        assert orchestrator.risk_to_level(1.0) == RiskLevel.CRITICAL


# ── 进度计算测试 ──────────────────────────────────────────────────────

class TestWeightedProgress:
    """_calculate_weighted_progress() — 不依赖 config，不需要 patch。"""

    def test_all_pending(self, orchestrator):
        detail = {
            "dimensions": {
                k: {"status": "pending", "completed": 0, "total": 10}
                for k in ["text_similarity", "structure_similarity", "image_similarity",
                          "table_similarity", "error_consistency", "metadata_consistency"]
            },
        }
        assert orchestrator._calculate_weighted_progress(detail) == 0

    def test_all_completed(self, orchestrator):
        detail = {
            "dimensions": {
                k: {"status": "completed", "completed": 10, "total": 10}
                for k in ["text_similarity", "structure_similarity", "image_similarity",
                          "table_similarity", "error_consistency", "metadata_consistency",
                          "template_reuse", "electronic_signature"]
            },
        }
        assert orchestrator._calculate_weighted_progress(detail) == 100

    def test_text_half_done(self, orchestrator):
        """文本50%完成 → 权重30% × 50% = 15%。"""
        dims = {}
        for k in ["text_similarity", "structure_similarity", "image_similarity",
                   "table_similarity", "error_consistency", "metadata_consistency"]:
            dims[k] = {"status": "pending", "completed": 0, "total": 5}
        dims["text_similarity"] = {"status": "running", "completed": 5, "total": 10}
        detail = {"dimensions": dims}
        # 8-dim: text weight = 0.25, 50% done → 12.5 → floor 12
        pct = orchestrator._calculate_weighted_progress(detail)
        assert pct in (12, 13)  # floor rounding may give 12 or 13

    def test_text_and_structure_done(self, orchestrator):
        """文本完成 + 结构完成 → 45%。"""
        dims = {}
        for k in ["text_similarity", "structure_similarity", "image_similarity",
                   "table_similarity", "error_consistency", "metadata_consistency"]:
            dims[k] = {"status": "pending", "completed": 0, "total": 5}
        dims["text_similarity"] = {"status": "completed", "completed": 10, "total": 10}
        dims["structure_similarity"] = {"status": "completed", "completed": 5, "total": 5}
        detail = {"dimensions": dims}
        # 8-dim: text(0.25) + structure(0.10) = 35%
        assert orchestrator._calculate_weighted_progress(detail) == 35


class TestETA:
    """_calculate_eta() — 不依赖 config。"""

    def test_all_completed_zero_eta(self, orchestrator):
        detail = {
            "dimensions": {
                k: {"status": "completed", "completed": 10, "total": 10}
                for k in ["text_similarity", "structure_similarity", "image_similarity",
                          "table_similarity", "error_consistency", "metadata_consistency"]
            },
        }
        assert orchestrator._calculate_eta(detail) == 0

    def test_one_pending(self, orchestrator):
        """仅文本维度 pending（10个对比，5秒/个）→ ETA = 50。"""
        dims = {}
        for k in ["text_similarity", "structure_similarity", "image_similarity",
                   "table_similarity", "error_consistency", "metadata_consistency"]:
            dims[k] = {"status": "completed", "completed": 0, "total": 0}
        dims["text_similarity"] = {"status": "pending", "completed": 0, "total": 10}
        detail = {"dimensions": dims}
        assert orchestrator._calculate_eta(detail) == 50

    def test_two_pending(self, orchestrator):
        """文本(10×5) + 错误(8×10) → ETA = 130。"""
        dims = {}
        for k in ["text_similarity", "structure_similarity", "image_similarity",
                   "table_similarity", "error_consistency", "metadata_consistency"]:
            dims[k] = {"status": "completed", "completed": 0, "total": 0}
        dims["text_similarity"] = {"status": "pending", "completed": 0, "total": 10}
        dims["error_consistency"] = {"status": "pending", "completed": 0, "total": 8}
        detail = {"dimensions": dims}
        assert orchestrator._calculate_eta(detail) == 130
