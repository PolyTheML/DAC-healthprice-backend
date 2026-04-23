"""Request/Response Pydantic models for API endpoints."""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class CaseSubmitResponse(BaseModel):
    """Response from POST /cases (case submission)."""
    case_id: str
    status: str
    risk_level: str
    risk_score: float
    overall_confidence: float
    final_premium: float
    requires_review: bool
    audit_entries: int
    created_at: datetime


class CaseListItem(BaseModel):
    """Item in GET /cases list response."""
    case_id: str
    status: str
    risk_level: str
    risk_score: float
    final_premium: float
    reviewer_id: Optional[str] = None
    created_at: datetime


class ReviewRequest(BaseModel):
    """Request body for POST /cases/{case_id}/review."""
    approved: bool
    notes: str
    reviewer_id: str


class ReviewResponse(BaseModel):
    """Response from POST /cases/{case_id}/review."""
    case_id: str
    status: str
    approved: bool
    reviewer_id: str
    timestamp: datetime


class CaseDetailResponse(BaseModel):
    """Full case details from GET /cases/{case_id}."""
    case_id: str
    status: str
    risk_level: str
    risk_score: float
    overall_confidence: float
    final_premium: float
    requires_review: bool
    audit_entries: int
    created_at: datetime
    updated_at: datetime
    extracted_data: Dict[str, Any]
    actuarial: Dict[str, Any]
    review_notes: Optional[Dict[str, Any]] = None


class AuditReportResponse(BaseModel):
    """Response from GET /cases/{case_id}/audit-report."""
    case_id: str
    report: str


class PricingBreakdownResponse(BaseModel):
    """Full pricing breakdown from GET /cases/{case_id}/pricing-breakdown."""
    case_id: str

    # Input parameters
    face_amount: float
    policy_term_years: int

    # Mortality and risk
    base_mortality_rate: float
    mortality_ratio: float
    risk_tier: str

    # Premium breakdown
    pure_premium: float
    expense_loading: float
    commission_loading: float
    profit_loading: float
    contingency_loading: float
    total_loading: float
    gross_annual_premium: float
    gross_monthly_premium: float

    # Risk factors applied
    factor_breakdown: Dict[str, float]

    # Metadata
    assumption_version: str
    calculation_notes: str
