"""
Auto Pricing Lab v2 — API Routes (Step 10)

POST /api/v1/auto/price          — single quote (customer-facing)
POST /api/v1/auto/price/batch    — batch quotes (lab use)
GET  /api/v1/auto/monitoring     — drift report (admin)
POST /api/v1/auto/train          — trigger ML retraining (admin)
"""
from __future__ import annotations
import sys, os
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.data.features import VehicleProfile
from app.data.validation import validate_profile
from app.pricing_engine.final_pricing import compute_final_price
from app.ml import inference as ml_inference

router = APIRouter(prefix="/api/v1/auto", tags=["auto-pricing"])

ADMIN_KEY = os.getenv("ADMIN_API_KEY", "")


def _require_admin(x_api_key: str = Header(None)):
    if not ADMIN_KEY or x_api_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Admin key required")


# ─── Request / Response Models ────────────────────────────────────────────────

class AutoPriceRequest(BaseModel):
    vehicle_type: str
    year_of_manufacture: int = Field(..., ge=1980, le=2025)
    region: str
    driver_age: int = Field(..., ge=18, le=75)
    accident_history: bool
    coverage: str
    tier: str
    family_size: int = Field(default=1, ge=1, le=6)
    reference_year: int = Field(default=2024, ge=2020, le=2030)


class MultipliersOut(BaseModel):
    vehicle_age: float
    driver_age: float
    region: float
    accident_history: float
    coverage: float
    combined: float


class GLMBreakdownOut(BaseModel):
    base_frequency: float
    base_severity: float
    base_pure_premium: float
    multipliers: MultipliersOut
    risk_adjusted_premium: float
    loading_factor: float
    loaded_premium: float
    tier_multiplier: float
    tiered_premium: float
    deductible_credit: float
    glm_price: float


class AutoPriceResponse(BaseModel):
    vehicle_type: str
    region: str
    tier: str
    coverage: str
    glm_price: float
    ml_adjustment: float
    ml_adjustment_vnd: float
    ml_confidence: float
    ml_available: bool
    ml_model_version: int
    final_price: float
    expected_cost: float
    margin: float
    margin_percent: float
    model_source: str
    model_accuracy_pct: float
    glm_breakdown: GLMBreakdownOut


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/price", response_model=AutoPriceResponse)
def price_vehicle(req: AutoPriceRequest):
    """Compute auto insurance premium for a single vehicle profile."""
    err = validate_profile(req.model_dump())
    if err:
        raise HTTPException(status_code=422, detail=err)

    profile = VehicleProfile(
        vehicle_type=req.vehicle_type,
        year_of_manufacture=req.year_of_manufacture,
        region=req.region,
        driver_age=req.driver_age,
        accident_history=req.accident_history,
        coverage=req.coverage,
        tier=req.tier,
        family_size=req.family_size,
        reference_year=req.reference_year,
    )

    result = compute_final_price(profile)
    glm = result.glm_breakdown
    mults = glm.multipliers

    return AutoPriceResponse(
        vehicle_type=result.vehicle_type,
        region=result.region,
        tier=result.tier,
        coverage=result.coverage,
        glm_price=result.glm_price,
        ml_adjustment=result.ml_adjustment,
        ml_adjustment_vnd=result.ml_adjustment_vnd,
        ml_confidence=result.ml_confidence,
        ml_available=result.ml_available,
        ml_model_version=result.ml_model_version,
        final_price=result.final_price,
        expected_cost=result.expected_cost,
        margin=result.margin,
        margin_percent=result.margin_percent,
        model_source=result.model_source,
        model_accuracy_pct=result.model_accuracy_pct,
        glm_breakdown=GLMBreakdownOut(
            base_frequency=glm.base_frequency,
            base_severity=glm.base_severity,
            base_pure_premium=glm.base_pure_premium,
            multipliers=MultipliersOut(
                vehicle_age=mults.vehicle_age,
                driver_age=mults.driver_age,
                region=mults.region,
                accident_history=mults.accident_history,
                coverage=mults.coverage,
                combined=mults.combined,
            ),
            risk_adjusted_premium=glm.risk_adjusted_premium,
            loading_factor=glm.loading_factor,
            loaded_premium=glm.loaded_premium,
            tier_multiplier=glm.tier_multiplier,
            tiered_premium=glm.tiered_premium,
            deductible_credit=glm.deductible_credit,
            glm_price=glm.glm_price,
        ),
    )


@router.post("/price/batch", response_model=List[AutoPriceResponse])
def price_batch(reqs: List[AutoPriceRequest]):
    """Batch pricing for up to 50 vehicle profiles."""
    if len(reqs) > 50:
        raise HTTPException(status_code=422, detail="Batch limit is 50 profiles")
    return [price_vehicle(r) for r in reqs]


@router.get("/monitoring")
def get_monitoring(_: None = Depends(_require_admin)):
    """Return current drift monitoring report. Admin only."""
    # Without a live DB, return placeholder — real implementation reads from DB
    return {
        "message": "Monitoring requires claim data in database.",
        "status": "no_data",
        "hint": "POST claims to /api/v1/auto/claims to populate feedback loop.",
    }


@router.post("/train")
def trigger_retraining(claims_csv: Optional[str] = None, _: None = Depends(_require_admin)):
    """Trigger ML model retraining. Admin only."""
    try:
        from app.ml.train_model import train
        metrics = train(claims_csv)
        ml_inference.reload_model()
        return {"status": "success", "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
