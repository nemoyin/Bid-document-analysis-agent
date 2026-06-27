"""
系统设置 API 路由。
提供分析配置和风险等级阈值的读取/修改接口。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter(prefix="/settings")

# 配置文件路径（同项目 data 目录）
CONFIG_FILE = Path(settings.ROOT_DIR) / "data" / "analysis_config.json"


# ============================================================
# Schema
# ============================================================

class AnalysisConfig(BaseModel):
    """分析配置。"""
    text_similarity_weight: float = Field(default=0.4, ge=0.0, le=1.0, description="文本相似度权重")
    image_similarity_weight: float = Field(default=0.25, ge=0.0, le=1.0, description="图片相似度权重")
    error_consistency_weight: float = Field(default=0.35, ge=0.0, le=1.0, description="错误一致性权重")
    similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="文本相似度阈值")
    chunk_size: int = Field(default=512, ge=64, le=2048, description="文档分块大小")
    max_file_size_mb: int = Field(default=100, ge=1, le=200, description="文件上传限制(MB)")


class RiskLevelThresholds(BaseModel):
    """风险等级阈值。"""
    low: float = Field(default=0.3, ge=0.0, le=1.0, description="低风险上限")
    medium: float = Field(default=0.6, ge=0.0, le=1.0, description="中风险上限")
    high: float = Field(default=0.85, ge=0.0, le=1.0, description="高风险上限（以上为CRITICAL）")


class SettingsResponse(BaseModel):
    """完整设置响应。"""
    analysis: AnalysisConfig
    risk_thresholds: RiskLevelThresholds


# ============================================================
# 持久化工具
# ============================================================

def _load_config() -> dict:
    """从 JSON 文件加载配置，如果文件不存在则使用默认值。"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"配置文件解析失败，使用默认值: {exc!s}")
    return {}


def _save_config(data: dict) -> None:
    """保存配置到 JSON 文件。"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"配置已保存: {CONFIG_FILE}")


def _merge_with_defaults(persisted: dict) -> dict:
    """将持久化配置与代码默认值合并，缺失的字段用默认值填补。"""
    defaults = {
        "text_similarity_weight": settings.TEXT_SIMILARITY_WEIGHT,
        "image_similarity_weight": settings.IMAGE_SIMILARITY_WEIGHT,
        "error_consistency_weight": settings.ERROR_CONSISTENCY_WEIGHT,
        "similarity_threshold": settings.SIMILARITY_THRESHOLD,
        "chunk_size": settings.CHUNK_SIZE,
        "max_file_size_mb": settings.MAX_FILE_SIZE // (1024 * 1024),
        "risk_low": settings.RISK_LEVEL_LOW,
        "risk_medium": settings.RISK_LEVEL_MEDIUM,
        "risk_high": settings.RISK_LEVEL_HIGH,
    }
    merged = defaults.copy()
    merged.update(persisted)
    return merged


def _to_response(data: dict) -> SettingsResponse:
    """将 dict 转为 SettingsResponse。"""
    return SettingsResponse(
        analysis=AnalysisConfig(
            text_similarity_weight=data.get("text_similarity_weight", 0.4),
            image_similarity_weight=data.get("image_similarity_weight", 0.25),
            error_consistency_weight=data.get("error_consistency_weight", 0.35),
            similarity_threshold=data.get("similarity_threshold", 0.8),
            chunk_size=data.get("chunk_size", 512),
            max_file_size_mb=data.get("max_file_size_mb", 100),
        ),
        risk_thresholds=RiskLevelThresholds(
            low=data.get("risk_low", 0.3),
            medium=data.get("risk_medium", 0.6),
            high=data.get("risk_high", 0.85),
        ),
    )


# ============================================================
# API 端点
# ============================================================


@router.get("", response_model=dict)
async def get_settings():
    """获取系统设置。"""
    persisted = _load_config()
    merged = _merge_with_defaults(persisted)
    response = _to_response(merged)
    # 包装在 ApiResponse 格式中
    return {"code": 0, "message": "success", "data": response.model_dump()}


@router.put("/analysis", response_model=dict)
async def update_analysis_config(config: AnalysisConfig):
    """更新分析配置。"""
    persisted = _load_config()
    persisted["text_similarity_weight"] = config.text_similarity_weight
    persisted["image_similarity_weight"] = config.image_similarity_weight
    persisted["error_consistency_weight"] = config.error_consistency_weight
    persisted["similarity_threshold"] = config.similarity_threshold
    persisted["chunk_size"] = config.chunk_size
    persisted["max_file_size_mb"] = config.max_file_size_mb
    _save_config(persisted)

    merged = _merge_with_defaults(persisted)
    response = _to_response(merged)
    return {"code": 0, "message": "分析配置已更新", "data": response.model_dump()}


@router.put("/risk-thresholds", response_model=dict)
async def update_risk_thresholds(thresholds: RiskLevelThresholds):
    """更新风险等级阈值。"""
    persisted = _load_config()
    persisted["risk_low"] = thresholds.low
    persisted["risk_medium"] = thresholds.medium
    persisted["risk_high"] = thresholds.high
    _save_config(persisted)

    merged = _merge_with_defaults(persisted)
    response = _to_response(merged)
    return {"code": 0, "message": "风险等级阈值已更新", "data": response.model_dump()}
