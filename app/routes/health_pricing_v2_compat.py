"""
Health Insurance Pricing v2 Compatibility Layer

Adapter for existing frontend expecting /api/v2/* endpoints.
Translates v2 format to v1 health pricing and back.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.data.health_features import MedicalProfile, extract_health_features
from app.data.health_validation import validate_health_profile
from app.pricing_engine.health_pricing import compute_health_glm_price


router = APIRouter(prefix="/api/v2", tags=["health-pricing-v2"])


# ─── Request / Response Models (v2 format) ────────────────────────────────────

class HealthPriceRequestV2(BaseModel):
    """Frontend v2 format request."""
    age: int = Field(..., ge=18, le=100)
    gender: str = Field(default="Male", description="Male | Female | Other")
    region: str = Field(...)
    smoking_status: str = Field(default="Never", description="Never | Former | Current")
    occupation_type: str = Field(default="Office/Desk")
    ipd_tier: str = Field(default="Silver", description="Bronze | Silver | Gold | Platinum")
    family_size: int = Field(default=1, ge=1, le=6)
    include_opd: bool = Field(default=False)
    include_dental: bool = Field(default=False)
    include_maternity: bool = Field(default=False)
    preexist_conditions: List[str] = Field(default_factory=list)
    exercise_frequency: str = Field(default="Moderate")
    exercise_days: int = Field(default=3, ge=0, le=7)
    exercise_mins: int = Field(default=30, ge=0)


class HealthPriceResponseV2(BaseModel):
    """Frontend v2 format response."""
    quote_id: str
    total_annual_premium: float
    total_monthly_premium: float
    risk_tier: str
    mortality_ratio: float
    base_mortality_rate: float
    status: str = "success"


class SessionResponse(BaseModel):
    """Session health check response."""
    status: str
    timestamp: str


# ─── Helper functions ────────────────────────────────────────────────────────

def translate_v2_to_v1(req: HealthPriceRequestV2) -> MedicalProfile:
    """Translate v2 frontend request to v1 health profile."""

    # Build coverage types from v2 flags
    coverage_types = ["ipd"]  # IPD always included
    if req.include_opd:
        coverage_types.append("opd")
    if req.include_dental:
        coverage_types.append("dental")
    if req.include_maternity:
        coverage_types.append("maternity")

    # Infer lifestyle from exercise frequency and days/mins
    if req.exercise_days == 0:
        exercise = "Sedentary"
    elif req.exercise_days <= 2:
        exercise = "Light"
    elif req.exercise_days <= 4:
        exercise = "Moderate"
    else:
        exercise = "Active"

    # Map preexist_conditions (filter "None")
    conditions = [c for c in req.preexist_conditions if c and c.lower() != "none"]

    # Country: infer from region (TODO: could be more sophisticated)
    if req.region in ["Ho Chi Minh City", "Hanoi", "Da Nang", "Can Tho", "Hai Phong"]:
        country = "vietnam"
    else:
        country = "cambodia"

    return MedicalProfile(
        age=req.age,
        gender=req.gender,
        country=country,
        region=req.region,
        smoking_status=req.smoking_status,
        exercise_frequency=exercise,
        occupation_type=req.occupation_type,
        alcohol_use="Never",  # Not provided in v2; default
        diet_quality="Balanced",  # Not provided in v2; default
        sleep_hours_per_night="Good (7-9h)",  # Not provided in v2; default
        stress_level="Low",  # Not provided in v2; default
        motorbike_use="No",  # Not provided in v2; default
        distance_to_hospital_km=10.0,  # Not provided in v2; reasonable default
        pre_existing_conditions=conditions,
        family_history=[],  # Not provided in v2
        ipd_tier=req.ipd_tier,
        coverage_types=coverage_types,
        face_amount=50000.0,  # Standard face amount
        policy_term_years=1,
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/price", response_model=HealthPriceResponseV2)
def price_v2(req: HealthPriceRequestV2):
    """
    V2 compatibility endpoint: POST /api/v2/price

    Translates v2 frontend format to health insurance pricing.
    """

    # Translate v2 → v1
    profile = translate_v2_to_v1(req)

    # Validate
    profile_dict = {
        "age": profile.age,
        "gender": profile.gender,
        "country": profile.country,
        "region": profile.region,
        "smoking_status": profile.smoking_status,
        "exercise_frequency": profile.exercise_frequency,
        "occupation_type": profile.occupation_type,
        "alcohol_use": profile.alcohol_use,
        "diet_quality": profile.diet_quality,
        "sleep_hours_per_night": profile.sleep_hours_per_night,
        "stress_level": profile.stress_level,
        "motorbike_use": profile.motorbike_use,
        "distance_to_hospital_km": profile.distance_to_hospital_km,
        "pre_existing_conditions": profile.pre_existing_conditions,
        "family_history": profile.family_history,
    }

    err = validate_health_profile(profile_dict)
    if err:
        raise HTTPException(status_code=422, detail=err)

    # Price
    result = compute_health_glm_price(profile)

    # Return v2 format
    return HealthPriceResponseV2(
        quote_id=f"quote-{result.age}-{result.gender[0]}-{result.risk_tier}",
        total_annual_premium=round(result.gross_annual_premium, 2),
        total_monthly_premium=round(result.gross_monthly_premium, 2),
        risk_tier=result.risk_tier,
        mortality_ratio=round(result.mortality_ratio, 4),
        base_mortality_rate=round(result.base_mortality_rate, 4),
    )


@router.get("/session")
def session_check():
    """Health check endpoint for frontend."""
    from datetime import datetime, timezone
    return SessionResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/health")
def health():
    """Health check endpoint for frontend."""
    return {"status": "ok", "message": "Health insurance pricing service is running"}


