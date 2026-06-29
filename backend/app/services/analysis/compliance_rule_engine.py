"""合规规则引擎 — 确定性规则 + LLM 语义规则"""
from __future__ import annotations

from typing import Any


def _clause_type_matches(clause: dict, rule_condition: dict) -> bool:
    """检查条款类型是否匹配规则的适用条件。"""
    allowed = rule_condition.get("clause_type", [])
    if isinstance(allowed, str):
        allowed = [allowed]
    clause_type = clause.get("type", "")
    return clause_type in allowed


def _evaluate_r01(clause: dict, rule: dict) -> dict | None:
    """R01: 发售期不足。"""
    params = clause.get("params", {})
    days = params.get("天数") or params.get("days")
    time_type = params.get("时间类型", "")
    expected_label = rule["conditions"].get("field_label", "发售期")
    if time_type != expected_label:
        return None
    if days is not None and isinstance(days, (int, float)) and days < rule["params"]["min_days"]:
        return {"risk": rule["default_risk"],
                "reason": f"发售期{days}日，少于法定最低{rule['params']['min_days']}日"}
    return None


def _evaluate_r04(clause: dict, rule: dict) -> dict | None:
    """R04: 品牌指向性。"""
    original = clause.get("original_text", "")
    params = clause.get("params", {})
    brands = params.get("品牌") or params.get("brand")
    if not brands:
        return None
    equivalents = rule["params"].get("equivalent_keywords", [])
    has_equivalent = any(kw in original for kw in equivalents)
    if has_equivalent:
        return None
    return {"risk": rule["default_risk"],
            "reason": f"指定品牌'{brands}'且无'或同等'字样，构成指向性"}


def _evaluate_r08(clause: dict, rule: dict) -> dict | None:
    """R08: 地域限制。"""
    original = clause.get("original_text", "")
    keywords = rule["params"].get("region_keywords", [])
    for kw in keywords:
        if kw in original:
            return {"risk": rule["default_risk"],
                    "reason": f"条款含地域限制词'{kw}'，涉嫌歧视外地投标人"}
    return None


# 确定性规则分发表
_DETERMINISTIC_EVALUATORS = {
    "R01": _evaluate_r01,
    "R04": _evaluate_r04,
    "R08": _evaluate_r08,
}


def evaluate_clause_deterministic(clause: dict, rule: dict) -> dict | None:
    """对单条条款执行确定性规则判定。

    Returns:
        dict | None: {"risk": "red|yellow|green", "reason": "..."} 或 None(不命中)
    """
    if not _clause_type_matches(clause, rule["conditions"]):
        return None

    evaluator = _DETERMINISTIC_EVALUATORS.get(rule["id"])
    if evaluator:
        return evaluator(clause, rule)

    # 通用确定性判定：比较 clause params 中的数值字段与 rule params 阈值
    rule_params = rule.get("params", {})
    clause_params = clause.get("params", {})
    field = rule["conditions"].get("field")
    if field and field in rule_params and field in clause_params:
        clause_val = clause_params[field]
        threshold = rule_params[field]
        if isinstance(clause_val, (int, float)) and isinstance(threshold, (int, float)):
            if clause_val < threshold:
                return {"risk": rule["default_risk"],
                        "reason": f"{field}={clause_val}, 低于阈值{threshold}"}

    return None


def evaluate_clause_llm(clause: dict, rule: dict) -> dict | None:
    """LLM语义规则判定（同步版本，编排器中通过 BackgroundTasks 异步调用）。"""
    prompt_template = rule.get("llm_prompt", "")
    if not prompt_template:
        return None

    try:
        prompt = prompt_template.format(
            clause_text=clause.get("original_text", ""),
            clause_type=clause.get("type", ""),
            params=clause.get("params", {}),
        )
    except KeyError:
        return None

    try:
        import httpx, json
        from app.core.config import settings

        url = f"{settings.GITEE_AI_BASE_URL}/chat/completions"
        headers = {"Authorization": f"Bearer {settings.GITEE_AI_API_KEY}"}
        payload = {
            "model": "Qwen3-32B",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1, "max_tokens": 500,
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])
            result = json.loads(content)
    except Exception:
        return None

    if result and isinstance(result, dict):
        risk = result.get("risk", "green")
        if risk in ("red", "yellow"):
            return {
                "risk": risk,
                "reason": result.get("reason", ""),
                "confidence": result.get("confidence", 0.5),
            }
    return None


def run_rule_engine(
    clauses: list[dict],
    rules: list[dict],
) -> list[dict]:
    """对条款列表执行完整的规则引擎判定。

    先跑确定性规则（即时），再对未命中条款跑 LLM 语义规则。

    Args:
        clauses: 条款卡片列表
        rules: 启用的规则列表

    Returns:
        list[dict]: 每个条款附带 risk_level + matched_rules
    """
    deterministic_rules = [
        r for r in rules
        if r.get("category") == "deterministic" and r.get("is_active", True)
    ]
    llm_rules = [
        r for r in rules
        if r.get("category") == "llm_semantic" and r.get("is_active", True)
    ]

    for clause in clauses:
        clause.setdefault("risk_level", "green")
        clause.setdefault("matched_rules", [])

    # Phase 1: 确定性规则
    for clause in clauses:
        for rule in deterministic_rules:
            result = evaluate_clause_deterministic(clause, rule)
            if result:
                result["rule_id"] = rule["id"]
                result["rule_name"] = rule.get("name", "")
                result["legal_basis"] = rule.get("legal_basis", [])
                clause["matched_rules"].append(result)
                if result["risk"] == "red":
                    clause["risk_level"] = "red"
                elif result["risk"] == "yellow" and clause["risk_level"] != "red":
                    clause["risk_level"] = "yellow"

    # Phase 2: LLM 语义规则（仅对仍为 green 的条款，避免重复调用）
    for clause in clauses:
        if clause["risk_level"] != "green":
            continue
        for rule in llm_rules:
            result = evaluate_clause_llm(clause, rule)
            if result:
                result["rule_id"] = rule["id"]
                result["rule_name"] = rule.get("name", "")
                result["legal_basis"] = rule.get("legal_basis", [])
                clause["matched_rules"].append(result)
                if result["risk"] == "red":
                    clause["risk_level"] = "red"
                elif result["risk"] == "yellow":
                    clause["risk_level"] = "yellow"

    return clauses
