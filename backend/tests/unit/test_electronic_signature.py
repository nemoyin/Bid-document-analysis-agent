"""
TDD Phase 7A：电子标书特征检测单元测试（先写测试，后实现）。

测试 extract_electronic_signatures、compare_electronic_signatures、
analyze_electronic_signature。
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.analysis import ElectronicSignatureResult

try:
    from app.services.analysis.electronic_signature import (
        compare_electronic_signatures,
        extract_electronic_signatures,
        analyze_electronic_signature,
    )
    ESIG_AVAILABLE = True
except ImportError:
    ESIG_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not ESIG_AVAILABLE,
    reason="electronic_signature 模块尚未实现（TDD Green 阶段前）",
)


# ── 纯函数测试 ────────────────────────────────────────────────────────

class TestExtractElectronicSignatures:
    """extract_electronic_signatures() 单元测试。"""

    def test_extract_creator_from_metadata(self):
        """从元数据提取创建者信息。"""
        metadata = {
            "author": "张三",
            "creator": "Microsoft Word",
            "producer": "Microsoft Word",
            "last_modified_by": "张三",
        }
        sig = extract_electronic_signatures(metadata, upload_ip=None)
        assert sig["creator_id"] == "张三"
        assert sig["software"] == "Microsoft Word"

    def test_extract_software_producer_fallback(self):
        """creator 为空时回退到 producer。"""
        metadata = {"author": "", "creator": "", "producer": "WPS Office"}
        sig = extract_electronic_signatures(metadata, upload_ip=None)
        assert sig["software"] == "WPS Office"

    def test_extract_upload_ip(self):
        """upload_ip 参数正确提取。"""
        sig = extract_electronic_signatures({}, upload_ip="192.168.1.100")
        assert sig["ip_address"] == "192.168.1.100"

    def test_extract_without_ip(self):
        """无 upload_ip 时应返回 None。"""
        sig = extract_electronic_signatures({}, upload_ip=None)
        assert sig["ip_address"] is None

    def test_empty_metadata_returns_defaults(self):
        """空元数据返回合理默认值。"""
        sig = extract_electronic_signatures({}, upload_ip=None)
        assert "creator_id" in sig
        assert "software" in sig
        assert "ip_address" in sig
        assert "modified_time" in sig


class TestCompareElectronicSignatures:
    """compare_electronic_signatures() 单元测试。"""

    def test_all_match(self):
        """所有维度匹配 → 100 分。"""
        sig = {
            "creator_id": "张三", "software": "Microsoft Word",
            "ip_address": "192.168.1.1", "mac_address": "AA:BB:CC:DD:EE:FF",
        }
        result = compare_electronic_signatures(sig, sig)
        assert result["signature_score"] == pytest.approx(1.0, abs=0.01)
        assert result["creator_match"] is True
        assert result["software_match"] is True
        assert result["ip_match"] is True
        assert result["mac_match"] is True

    def test_none_match(self):
        """全部不匹配 → 0 分。"""
        sig_a = {
            "creator_id": "张三", "software": "Word",
            "ip_address": "192.168.1.1", "mac_address": None,
        }
        sig_b = {
            "creator_id": "李四", "software": "WPS",
            "ip_address": "10.0.0.1", "mac_address": None,
        }
        result = compare_electronic_signatures(sig_a, sig_b)
        assert result["signature_score"] < 0.1
        assert result["creator_match"] is False
        assert result["software_match"] is False

    def test_only_creator_matches(self):
        """仅创建者匹配 → ~0.20 分。"""
        sig_a = {"creator_id": "张三", "software": "Word", "ip_address": None, "mac_address": None}
        sig_b = {"creator_id": "张三", "software": "WPS", "ip_address": None, "mac_address": None}
        result = compare_electronic_signatures(sig_a, sig_b)
        # creator 权重 = 0.20/(0.20+0.15) = 0.571 because ip and mac are None
        # Actually, when ip and mac are both None, weights redistribute:
        # Available: creator(0.20) + software(0.15) = 0.35
        # Match: creator = 0.20 → score = 0.20/0.35 ≈ 0.571
        assert 0.4 < result["signature_score"] < 0.75

    def test_ip_same_subnet_match(self):
        """同子网 IP → True。"""
        sig_a = {"creator_id": "", "software": "", "ip_address": "192.168.1.1", "mac_address": None}
        sig_b = {"creator_id": "", "software": "", "ip_address": "192.168.1.100", "mac_address": None}
        result = compare_electronic_signatures(sig_a, sig_b)
        assert result["ip_match"] is True

    def test_ip_different_match(self):
        """不同子网 → False。"""
        sig_a = {"creator_id": "", "software": "", "ip_address": "192.168.1.1", "mac_address": None}
        sig_b = {"creator_id": "", "software": "", "ip_address": "10.0.0.1", "mac_address": None}
        result = compare_electronic_signatures(sig_a, sig_b)
        assert result["ip_match"] is False

    def test_mac_unavailable(self):
        """MAC 不可用 → mac_match=None，权重重分配。"""
        sig_a = {"creator_id": "张三", "software": "Word", "ip_address": None, "mac_address": None}
        sig_b = {"creator_id": "张三", "software": "Word", "ip_address": None, "mac_address": None}
        result = compare_electronic_signatures(sig_a, sig_b)
        assert result["mac_match"] is None
        # creator + software 都匹配 → 1.0
        assert result["signature_score"] == pytest.approx(1.0, abs=0.01)

    def test_weights_sum_to_one(self):
        """校验权重和=1.0（仅包含可用维度）。"""
        sig_a = {"creator_id": "张三", "software": "Word", "ip_address": "1.1.1.1", "mac_address": "AA:BB:CC:DD:EE:FF"}
        sig_b = {"creator_id": "张三", "software": "Word", "ip_address": "1.1.1.1", "mac_address": "AA:BB:CC:DD:EE:FF"}
        result = compare_electronic_signatures(sig_a, sig_b)
        assert result["signature_score"] == pytest.approx(1.0, abs=0.01)

    def test_creator_normalization(self):
        """creator 去空格 + 大小写折叠。"""
        sig_a = extract_electronic_signatures({"author": "张三 "}, None)
        sig_b = extract_electronic_signatures({"author": "张三"}, None)
        result = compare_electronic_signatures(sig_a, sig_b)
        assert result["creator_match"] is True

    def test_returns_all_expected_keys(self):
        """返回字典含所有预期键。"""
        sig = {"creator_id": "", "software": "", "ip_address": None, "mac_address": None, "modified_time": ""}
        r = compare_electronic_signatures(sig, sig)
        for k in ["signature_score", "creator_match", "software_match", "ip_match", "mac_match", "matched_items", "details"]:
            assert k in r


# ── DB 集成测试 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAnalyzeElectronicSignature:
    """analyze_electronic_signature() 集成测试。"""

    async def test_returns_zero_for_few_documents(self, db_session_factory, sample_project):
        """文档不足2个时返回0。"""
        count = await analyze_electronic_signature(
            project_id=sample_project.id,
            analysis_task_id=uuid.uuid4(),
            db_session_factory=db_session_factory,
        )
        assert count == 0
