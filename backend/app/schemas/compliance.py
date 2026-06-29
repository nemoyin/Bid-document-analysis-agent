"""合规审查 Schemas"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ComplianceClauseResponse(BaseModel):
    id: str
    analysis_id: str
    clause_type: str
    original_text: str
    location: Optional[dict] = None
    params: Optional[dict] = None
    risk_level: Optional[str] = None
    matched_rules: Optional[dict] = None
    model_config = {"from_attributes": True}


class ComplianceAnalysisResponse(BaseModel):
    id: str
    project_id: str
    document_id: str
    status: str
    progress: int = 0
    compliance_score: Optional[Decimal] = None
    risk_level: Optional[str] = None
    clause_count: int = 0
    violation_count: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    clauses: list[ComplianceClauseResponse] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class ComplianceAnalysisCreate(BaseModel):
    project_id: str
    document_id: str
