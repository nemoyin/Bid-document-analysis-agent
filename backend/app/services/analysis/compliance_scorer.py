"""合规评分引擎 — 基于条款风险等级的扣分模型"""
from typing import Any

from app.core.compliance_config import load_compliance_config


def calculate_compliance_score(
    clauses: list[dict],
    config: dict | None = None,
) -> dict[str, Any]:
    """根据条款风险等级计算合规评分。

    Args:
        clauses: 已判定的条款列表 (risk_level + matched_rules)
        config: 评分配置，默认从 compliance_config.json 读取

    Returns:
        dict: {score, risk_level, red_count, yellow_count, green_count, total_count}
    """
    if config is None:
        config = load_compliance_config()
    scoring = config.get("scoring", {})

    initial = scoring.get("initial_score", 100)
    red_deduction = scoring.get("red_deduction", 20)
    yellow_deduction = scoring.get("yellow_deduction", 8)

    red_count = sum(1 for c in clauses if c.get("risk_level") == "red")
    yellow_count = sum(1 for c in clauses if c.get("risk_level") == "yellow")
    green_count = sum(1 for c in clauses if c.get("risk_level") == "green")

    score = max(0, initial - red_count * red_deduction - yellow_count * yellow_deduction)

    risk_low = scoring.get("risk_low", 85)
    risk_medium = scoring.get("risk_medium", 60)
    risk_high = scoring.get("risk_high", 40)

    if score >= risk_low:
        risk_level = "low"
    elif score >= risk_medium:
        risk_level = "moderate"
    elif score >= risk_high:
        risk_level = "high"
    else:
        risk_level = "critical"

    return {
        "score": score,
        "risk_level": risk_level,
        "red_count": red_count,
        "yellow_count": yellow_count,
        "green_count": green_count,
        "total_count": len(clauses),
    }
