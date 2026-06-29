"""
API v1 路由聚合。
聚合所有 v1 版本的路由到主路由器。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.projects import router as projects_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.documents import router as documents_router
from app.api.v1.reports import router as reports_router
from app.api.v1.settings import router as settings_router
from app.api.v1.compliance import router as compliance_router

router = APIRouter(prefix="/api/v1")

# 注册子路由
router.include_router(projects_router)
router.include_router(analysis_router)
router.include_router(documents_router)
router.include_router(reports_router)
router.include_router(settings_router)
router.include_router(compliance_router)

# Dashboard 统计（直接注册，无子前缀）
from app.api.v1.dashboard import router as dashboard_router
router.include_router(dashboard_router)
