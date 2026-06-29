"""测试合规规则引擎 + 评分"""
import pytest
from app.services.analysis.compliance_rule_engine import (
    evaluate_clause_deterministic,
    run_rule_engine,
)
from app.services.analysis.compliance_scorer import calculate_compliance_score

# 测试用规则定义
R01_RULE = {
    "id": "R01", "name": "发售期不足", "category": "deterministic", "default_risk": "red",
    "conditions": {"clause_type": "timeline", "field": "天数", "field_label": "发售期"},
    "params": {"min_days": 5},
    "legal_basis": [{"law": "实施条例", "article": "第16条"}],
}
R04_RULE = {
    "id": "R04", "name": "品牌指向性", "category": "deterministic", "default_risk": "red",
    "conditions": {"clause_type": "technical"},
    "params": {"min_brands": 3, "equivalent_keywords": ["或同等", "或相当于"]},
    "legal_basis": [{"law": "实施条例", "article": "第32条"}],
}
R08_RULE = {
    "id": "R08", "name": "地域限制", "category": "deterministic", "default_risk": "red",
    "conditions": {"clause_type": ["qualification", "performance", "scoring"]},
    "params": {"region_keywords": ["本地", "本省", "本市"]},
    "legal_basis": [{"law": "实施条例", "article": "第32条"}],
}


class TestDeterministicRules:
    def test_r01_sale_period_too_short(self):
        clause = {"type": "timeline", "original_text": "发售期3个工作日",
                  "params": {"天数": 3, "时间类型": "发售期"}}
        result = evaluate_clause_deterministic(clause, R01_RULE)
        assert result is not None
        assert result["risk"] == "red"

    def test_r01_sale_period_ok(self):
        clause = {"type": "timeline", "original_text": "发售期7个工作日",
                  "params": {"天数": 7, "时间类型": "发售期"}}
        result = evaluate_clause_deterministic(clause, R01_RULE)
        assert result is None

    def test_r01_wrong_clause_type(self):
        clause = {"type": "qualification", "params": {"天数": 3}}
        result = evaluate_clause_deterministic(clause, R01_RULE)
        assert result is None

    def test_r04_brand_without_equivalent(self):
        clause = {"type": "technical", "original_text": "须采用Intel处理器",
                  "params": {"品牌": "Intel"}}
        result = evaluate_clause_deterministic(clause, R04_RULE)
        assert result is not None
        assert result["risk"] == "red"

    def test_r04_brand_with_equivalent(self):
        clause = {"type": "technical", "original_text": "须采用Intel处理器或同等",
                  "params": {"品牌": "Intel"}}
        result = evaluate_clause_deterministic(clause, R04_RULE)
        assert result is None  # 有"或同等"，不违规

    def test_r08_region_keyword(self):
        clause = {"type": "qualification", "original_text": "投标人须在本省具有3年以上经验"}
        result = evaluate_clause_deterministic(clause, R08_RULE)
        assert result is not None
        assert result["risk"] == "red"

    def test_r08_no_region_keyword(self):
        clause = {"type": "qualification", "original_text": "投标人须具有3年以上经验"}
        result = evaluate_clause_deterministic(clause, R08_RULE)
        assert result is None


class TestRuleEngine:
    def test_run_engine_deterministic(self):
        clauses = [
            {"type": "timeline", "original_text": "发售期3日",
             "params": {"天数": 3, "时间类型": "发售期"}},
            {"type": "qualification", "original_text": "须有营业执照", "params": {}},
        ]
        rules = [R01_RULE, R08_RULE]
        results = run_rule_engine(clauses, rules)
        # clause 0 hits R01 → red
        assert results[0]["risk_level"] == "red"
        assert len(results[0]["matched_rules"]) >= 1
        # clause 1 is clean
        assert results[1]["risk_level"] == "green"

    def test_empty_clauses(self):
        assert run_rule_engine([], [R01_RULE]) == []


class TestComplianceScorer:
    def test_all_green_full_score(self):
        clauses = [{"risk_level": "green"}, {"risk_level": "green"}, {"risk_level": "green"}]
        result = calculate_compliance_score(clauses)
        assert result["score"] == 100
        assert result["risk_level"] == "low"

    def test_one_red_deducts(self):
        clauses = [{"risk_level": "red", "matched_rules": [{"rule_id": "R01"}]},
                   {"risk_level": "green"}]
        result = calculate_compliance_score(clauses)
        assert result["score"] == 80
        assert result["red_count"] == 1

    def test_mixed_deductions(self):
        clauses = [
            {"risk_level": "red"}, {"risk_level": "red"},
            {"risk_level": "yellow"}, {"risk_level": "yellow"},
            {"risk_level": "green"},
        ]
        result = calculate_compliance_score(clauses)
        assert result["score"] == 44  # 100 - 2*20 - 2*8
        assert result["risk_level"] == "high"

    def test_zero_floor(self):
        clauses = [{"risk_level": "red"} for _ in range(10)]
        result = calculate_compliance_score(clauses)
        assert result["score"] == 0
        assert result["risk_level"] == "critical"
