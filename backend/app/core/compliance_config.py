"""合规审查配置加载"""
import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "compliance_config.json"
)

_config_cache: dict[str, Any] | None = None


def load_compliance_config() -> dict[str, Any]:
    """加载合规审查配置（带缓存）。"""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _config_cache = json.load(f)
    else:
        _config_cache = {"clause_types": [], "scoring": {}, "default_rules": []}
    return _config_cache


def reload_compliance_config() -> dict[str, Any]:
    """强制重新加载配置（用于管理界面修改后刷新）。"""
    global _config_cache
    _config_cache = None
    return load_compliance_config()


def get_active_clause_types() -> list[dict]:
    """获取当前启用的条款类型列表。"""
    cfg = load_compliance_config()
    return [t for t in cfg.get("clause_types", []) if t.get("active")]


def get_active_rules() -> list[dict]:
    """获取当前启用的规则列表。"""
    cfg = load_compliance_config()
    return [r for r in cfg.get("default_rules", []) if r.get("is_active")]
