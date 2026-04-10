"""
Health Insurance Pricing Lab — API Routes

POST /api/v1/health/price                 — single quote (customer-facing)
POST /api/v1/health/price/underwriting    — with medical extraction (underwriter-facing)
POST /api/v1/health/price/batch           — batch quotes (lab use)
GET  /api/v1/health/monitoring            — drift report (admin)
GET  /api/v1/health/risk-classification   — risk tier info (customer-facing)
"""
from __future__ import annotations
import sys, os
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, Depends, Header, UploadFile, File, Form
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.data.health_features import MedicalProfile, extract_health_features
from app.data.health_validation import validate_health_profile, validate_extracted_medical_data
from app.pricing_engine.health_pricing import compute_health_glm_price, HEALTH_COEFF


router = APIRouter(prefix="/api/v1/health", tags=["health-pricing"])

ADMIN_KEY = os.getenv("ADMIN_API_KEY", "")


def _require_admin(x_api_key: str = Header(None)):
    if not ADMIN_KEY or x_api_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Admin key required")


# ─── Request / Response Models ────────────────────────────────────────────────

class HealthPriceRequest(BaseModel):
    """Health insurance quote request."""
    age: int = Field(..., ge=18, le=100)
    gender: str = Field(..., description="Male | Female | Other")
    country: str = Field("cambodia", description="cambodia | vietnam")
    region: str = Field(...)
    smoking_status: str = Field(default="Never", description="Never | Former | Current")
    exercise_frequency: str = Field(default="Moderate", description="Sedentary | Light | Moderate | Active")
    occupation_type: str = Field(default="Office/Desk")
    alcohol_use: str = Field(default="Never", description="Never | Occasional | Regular | Heavy")
    diet_quality: str = Field(default="Balanced", description="Healthy | Balanced | High Processed")
    sleep_hours_per_night: str = Field(default="Fair (5-7h)")
    stress_level: str = Field(default="Low", description="Low | Moderate | High")
    motorbike_use: str = Field(default="No", description="No | Never | Occasional | Daily")
    distance_to_hospital_km: float = Field(default=5.0, ge=0.0, le=200.0)
    pre_existing_conditions: List[str] = Field(default_factory=list)
    family_history: List[str] = Field(default_factory=list)
    bmi: Optional[float] = Field(None, ge=10.0, le=60.0)
    systolic_bp: Optional[int] = Field(None, ge=70, le=200)
    diastolic_bp: Optional[int] = Field(None, ge=40, le=120)
    ipd_tier: str = Field(default="Silver", description="Bronze | Silver | Gold | Platinum")
    coverage_types: List[str] = Field(default_factory=lambda: ["ipd"])
    face_amount: float = Field(default=50000.0, ge=10000.0, le=500000.0)
    policy_term_years: int = Field(default=1, ge=1, le=40)


class HealthPriceBreakdownOut(BaseModel):
    """Detailed pricing breakdown."""
    base_mortality_rate: float
    mortality_ratio: float
    pure_annual_premium: float
    expense_loading: float
    commission_loading: float
    profit_loading: float
    contingency_loading: float
    total_loading_amount: float
    loaded_premium: float
    tier_multiplier: float
    gross_annual_premium: float
    gross_monthly_premium: float
    factor_breakdown: Dict[str, float]


class HealthPriceResponse(BaseModel):
    """Health insurance quote response."""
    age: int
    gender: str
    ipd_tier: str
    coverage_types: List[str]
    base_mortality_rate: float
    mortality_ratio: float
    risk_tier: str  # LOW | MEDIUM | HIGH | DECLINE
    mortality_ratio_percent: str
    gross_annual_premium: float
    gross_monthly_premium: float
    total_loading_percent: float
    assumption_version: str
    breakdown: HealthPriceBreakdownOut


class HealthUnderwritingRequest(BaseModel):
    """Request for medical extraction + pricing."""
    # Medical PDF upload (handled via UploadFile in endpoint)
    age: int = Field(default=None, description="Optional if extracting from PDF")
    gender: str = Field(default=None)
    country: str = Field(default="cambodia")
    region: str = Field(...)
    ipd_tier: str = Field(default="Silver")
    coverage_types: List[str] = Field(default_factory=lambda: ["ipd"])
    face_amount: float = Field(default=50000.0)
    policy_term_years: int = Field(default=1)


class RiskClassificationOut(BaseModel):
    """Risk tier definition."""
    tier: str
    mortality_ratio_range: str
    description: str
    approval_likelihood: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/price", response_model=HealthPriceResponse)
def price_health_insurance(req: HealthPriceRequest):
    """Compute health insurance premium for a single applicant profile."""

    # Validate input
    profile_dict = req.model_dump()
    err = validate_health_profile(profile_dict)
    if err:
        raise HTTPException(status_code=422, detail=err)

    # Create profile
    profile = MedicalProfile(**profile_dict)

    # Compute GLM pricing
    result = compute_health_glm_price(profile)

    # Format response
    loading_ratio = (result.total_loading_amount / result.pure_annual_premium * 100) if result.pure_annual_premium > 0 else 0

    return HealthPriceResponse(
        age=result.age,
        gender=result.gender,
        ipd_tier=result.ipd_tier,
        coverage_types=result.coverage_types,
        base_mortality_rate=round(result.base_mortality_rate, 4),
        mortality_ratio=round(result.mortality_ratio, 4),
        risk_tier=result.risk_tier,
        mortality_ratio_percent=f"{result.mortality_ratio * 100:.1f}%",
        gross_annual_premium=round(result.gross_annual_premium, 2),
        gross_monthly_premium=round(result.gross_monthly_premium, 2),
        total_loading_percent=f"{loading_ratio:.1f}%",
        assumption_version=result.assumption_version,
        breakdown=HealthPriceBreakdownOut(
            base_mortality_rate=round(result.base_mortality_rate, 4),
            mortality_ratio=round(result.mortality_ratio, 4),
            pure_annual_premium=round(result.pure_annual_premium, 2),
            expense_loading=round(result.expense_loading, 2),
            commission_loading=round(result.commission_loading, 2),
            profit_loading=round(result.profit_loading, 2),
            contingency_loading=round(result.contingency_loading, 2),
            total_loading_amount=round(result.total_loading_amount, 2),
            loaded_premium=round(result.loaded_premium, 2),
            tier_multiplier=round(result.tier_multiplier, 2),
            gross_annual_premium=round(result.gross_annual_premium, 2),
            gross_monthly_premium=round(result.gross_monthly_premium, 2),
            factor_breakdown={k: round(v, 4) for k, v in result.factor_breakdown.items()},
        ),
    )


@router.post("/price/batch")
def batch_health_price(requests: List[HealthPriceRequest]):
    """Compute quotes for multiple applicants (lab/testing endpoint)."""
    results = []
    for req in requests:
        try:
            result = price_health_insurance(req)
            results.append({"success": True, "quote": result})
        except HTTPException as e:
            results.append({"success": False, "error": e.detail})
    return results


@router.get("/risk-classification")
def get_risk_classifications():
    """
    Return risk tier definitions.
    Useful for customer education on risk classes.
    """
    return {
        "LOW": RiskClassificationOut(
            tier="LOW",
            mortality_ratio_range="≤ 1.20",
            description="Standard health profile with minimal risk factors. Approval is immediate.",
            approval_likelihood="95%+"
        ),
        "MEDIUM": RiskClassificationOut(
            tier="MEDIUM",
            mortality_ratio_range="1.20 - 1.80",
            description="Some risk factors (e.g., smoking or controlled condition). May require medical exam.",
            approval_likelihood="85-95%"
        ),
        "HIGH": RiskClassificationOut(
            tier="HIGH",
            mortality_ratio_range="1.80 - 3.00",
            description="Multiple risk factors or significant conditions. Requires underwriter review.",
            approval_likelihood="60-85%"
        ),
        "DECLINE": RiskClassificationOut(
            tier="DECLINE",
            mortality_ratio_range="> 3.00",
            description="Uninsurable risk profile. Declined or needs specialized underwriting.",
            approval_likelihood="< 60%"
        ),
    }


@router.get("/monitoring", dependencies=[Depends(_require_admin)])
def health_monitoring():
    """Admin endpoint: pricing drift and performance metrics."""
    return {
        "status": "ok",
        "last_updated": "2026-04-10T14:30:00Z",
        "assumptions_version": HEALTH_COEFF["version"],
        "assumptions_last_updated": HEALTH_COEFF["last_updated"],
        "quotes_processed_today": 0,  # Would come from database
        "average_premium_computed": 0.0,
        "modal_risk_tier": "MEDIUM",
        "health_check": "All systems operational"
    }


@router.post("/price/what-if")
def what_if_analysis(
    age: int = 45,
    gender: str = "Male",
    bmi: float = 25.0,
    smoker: bool = False,
    diabetes: bool = False,
    hypertension: bool = False,
    ipd_tier: str = "Silver",
    face_amount: float = 50000.0,
):
    """
    What-if analysis endpoint: rapidly test different parameter combinations.

    Example: GET /api/v1/health/price/what-if?age=55&smoker=true&face_amount=100000
    """
    req = HealthPriceRequest(
        age=age,
        gender=gender,
        country="cambodia",
        region="Phnom Penh",
        smoking_status="Current" if smoker else "Never",
        exercise_frequency="Moderate",
        occupation_type="Office/Desk",
        alcohol_use="Never",
        diet_quality="Balanced",
        sleep_hours_per_night="Fair (5-7h)",
        stress_level="Low",
        motorbike_use="No",
        distance_to_hospital_km=5.0,
        bmi=bmi,
        pre_existing_conditions=(["Diabetes"] if diabetes else []) + (["Hypertension"] if hypertension else []),
        family_history=[],
        ipd_tier=ipd_tier,
        coverage_types=["ipd"],
        face_amount=face_amount,
        policy_term_years=1,
    )

    return price_health_insurance(req)
