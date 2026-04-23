"""
Life Insurance Pricing Routes — Centralized Cambodia Life Pricing

POST /api/v1/life/quote          — full life insurance quote with Cambodia factors
GET  /api/v1/life/what-if        — what-if analysis (query params)
POST /api/v1/life/escalation     — escalation product schedule
POST /api/v1/life/escalation/what-if — multi-scenario escalation comparison
GET  /api/v1/life/assumptions    — current assumption version + metadata
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from medical_reader.pricing.cambodia_pricing import (
    CambodiaLifePricingRequest,
    calculate_cambodia_life_premium,
)
from medical_reader.pricing.assumptions import ASSUMPTIONS, ASSUMPTION_VERSION
from medical_reader.pricing.escalation_calculator import (
    EscalationParameters,
    ESCALATION_PARAMS,
    calculate_escalation_schedule,
)

router = APIRouter(prefix="/api/v1/life", tags=["life-pricing"])


# ── Request models ────────────────────────────────────────────────────────────

class LifeQuoteRequest(BaseModel):
    age: Optional[int] = Field(45, ge=0, le=100)
    gender: str = Field("M", description="M or F")
    bmi: Optional[float] = Field(25.0, ge=10, le=60)
    smoker: bool = False
    alcohol_use: str = Field("None", description="None, Moderate, or Heavy")
    diabetes: bool = False
    hypertension: bool = False
    hyperlipidemia: bool = False
    family_history_chd: bool = False
    systolic: Optional[int] = Field(None, ge=60, le=250)
    diastolic: Optional[int] = Field(None, ge=40, le=150)
    face_amount: float = Field(50000, gt=0, description="Coverage amount in USD")
    policy_term_years: int = Field(10, ge=1, le=40)
    # Cambodia-specific
    occupation_type: str = Field("office_desk", description="Occupation category")
    motorbike_usage: str = Field("never", description="never, occasional, or daily")
    province: str = Field("phnom_penh", description="Cambodia province")
    healthcare_tier: str = Field("unknown", description="tier_a, tier_b, clinic, or unknown")


class LifeEscalationRequest(BaseModel):
    base_annual_premium: float = Field(..., gt=0, description="Standard annual premium in USD")
    base_coverage: float = Field(..., gt=0, description="Year 1 coverage in USD")
    escalation_rate: float = Field(0.05, ge=0.01, le=0.20)
    discount_rate: float = Field(0.06, ge=0.01, le=0.15)
    duration_years: int = Field(20, ge=5, le=30)
    terminal_cap: float = Field(2.50, ge=1.10, le=5.00)


class LifeEscalationWhatIfRequest(BaseModel):
    base_annual_premium: float = Field(..., gt=0)
    base_coverage: float = Field(..., gt=0)
    scenarios: List[dict] = Field(..., max_length=5,
        description="List of param override dicts (escalation_rate, discount_rate, duration_years, terminal_cap)")


# ── Helper ──────────────────────────────────────────────────────────────────────

def _serialize_cambodia(result) -> dict:
    b = result.base
    return {
        "input_parameters": {
            "age": b.age, "gender": b.gender, "bmi": b.bmi,
            "smoker": b.smoker, "alcohol_use": b.alcohol_use,
            "diabetes": b.diabetes, "hypertension": b.hypertension,
            "hyperlipidemia": b.hyperlipidemia, "family_history_chd": b.family_history_chd,
            "systolic": b.systolic, "diastolic": b.diastolic,
            "face_amount": b.face_amount, "policy_term_years": b.policy_term_years,
            "occupation_type": result.occupation_multiplier and None,  # populated below
            "motorbike_usage": None, "province": None, "healthcare_tier": None,
        },
        "base_premium": {
            "mortality_ratio": round(b.mortality_ratio, 4),
            "pure_annual_premium": round(b.pure_annual_premium, 2),
            "gross_annual_premium": round(b.gross_annual_premium, 2),
            "gross_monthly_premium": round(b.gross_monthly_premium, 2),
            "risk_tier": b.risk_tier,
        },
        "cambodia_adjustments": {
            "occupation": {"multiplier": result.occupation_multiplier, "notes": result.occupation_notes},
            "endemic": {"multiplier": result.endemic_multiplier, "notes": result.endemic_notes},
            "healthcare_tier": {"discount": result.healthcare_discount, "notes": result.healthcare_notes},
        },
        "adjusted_premium": {
            "adjusted_mortality_ratio": round(result.adjusted_mortality_ratio, 4),
            "adjusted_pure_premium": round(result.adjusted_pure_premium, 2),
            "adjusted_gross_premium": round(result.adjusted_gross_premium, 2),
            "final_annual_premium": round(result.final_gross_premium, 2),
            "final_monthly_premium": round(result.final_monthly_premium, 2),
            "risk_tier": result.risk_tier,
        },
        "factor_breakdown": {k: round(v, 4) for k, v in result.factor_breakdown.items()},
        "metadata": {
            "assumption_version": result.assumption_version,
            "model_version": result.model_version,
        },
    }


def _serialize_escalation(schedule, params) -> dict:
    return {
        "premium_summary": {
            "base_annual_premium": schedule.base_annual_premium,
            "escalated_annual_premium": schedule.escalated_annual_premium,
            "escalated_monthly_premium": schedule.escalated_monthly_premium,
            "cost_factor": schedule.cost_factor,
            "cost_factor_pct": schedule.cost_factor_pct,
        },
        "coverage_summary": {
            "year_1_coverage": schedule.base_coverage,
            "terminal_coverage": schedule.terminal_coverage,
            "terminal_cap_multiple": f"{params.terminal_cap:.1f}x",
            "cap_reached_at_year": schedule.cap_year,
        },
        "projections": [
            {
                "year": p.year,
                "coverage_multiple": p.coverage_multiple,
                "coverage_amount": p.coverage_amount,
                "annual_premium": p.annual_premium,
                "monthly_premium": p.monthly_premium,
                "cumulative_escalation_pct": p.cumulative_escalation_pct,
                "loyalty_bonus": p.loyalty_bonus,
            }
            for p in schedule.projections
        ],
        "parameters": {
            "escalation_rate": params.escalation_rate,
            "discount_rate": params.discount_rate,
            "duration_years": params.duration_years,
            "terminal_cap": params.terminal_cap,
            "cap_utilization": params.cap_utilization,
        },
        "metadata": {"escalation_version": schedule.version},
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/quote")
async def life_quote(req: LifeQuoteRequest):
    """
    Full Cambodia life insurance quote with occupational, endemic, and healthcare-tier adjustments.

    Returns base premium, Cambodia adjustments, adjusted premium, and full factor breakdown.

    Example:
        POST /api/v1/life/quote
        {"age": 45, "face_amount": 100000, "province": "mondulkiri", "occupation_type": "construction"}
    """
    try:
        cambodia_req = CambodiaLifePricingRequest(
            age=req.age, gender=req.gender, bmi=req.bmi,
            smoker=req.smoker, alcohol_use=req.alcohol_use,
            diabetes=req.diabetes, hypertension=req.hypertension,
            hyperlipidemia=req.hyperlipidemia, family_history_chd=req.family_history_chd,
            systolic=req.systolic, diastolic=req.diastolic,
            face_amount=req.face_amount, policy_term_years=req.policy_term_years,
            occupation_type=req.occupation_type, motorbike_usage=req.motorbike_usage,
            province=req.province, healthcare_tier=req.healthcare_tier,
        )
        result = calculate_cambodia_life_premium(cambodia_req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation failed: {e}")

    resp = _serialize_cambodia(result)
    resp["input_parameters"]["occupation_type"] = req.occupation_type
    resp["input_parameters"]["motorbike_usage"] = req.motorbike_usage
    resp["input_parameters"]["province"] = req.province
    resp["input_parameters"]["healthcare_tier"] = req.healthcare_tier
    return resp


@router.get("/what-if")
async def life_what_if(
    age: int = 45, gender: str = "M", bmi: float = 25.0,
    smoker: bool = False, alcohol_use: str = "None",
    diabetes: bool = False, hypertension: bool = False,
    hyperlipidemia: bool = False, family_history_chd: bool = False,
    systolic: Optional[int] = None, diastolic: Optional[int] = None,
    face_amount: float = 50000, policy_term_years: int = 10,
    occupation_type: str = "office_desk", motorbike_usage: str = "never",
    province: str = "phnom_penh", healthcare_tier: str = "unknown",
):
    """
    What-if analysis for life insurance pricing (query params).

    Example:
        GET /api/v1/life/what-if?age=55&smoker=true&face_amount=100000&province=mondulkiri
    """
    try:
        cambodia_req = CambodiaLifePricingRequest(
            age=age, gender=gender, bmi=bmi,
            smoker=smoker, alcohol_use=alcohol_use,
            diabetes=diabetes, hypertension=hypertension,
            hyperlipidemia=hyperlipidemia, family_history_chd=family_history_chd,
            systolic=systolic, diastolic=diastolic,
            face_amount=face_amount, policy_term_years=policy_term_years,
            occupation_type=occupation_type, motorbike_usage=motorbike_usage,
            province=province, healthcare_tier=healthcare_tier,
        )
        result = calculate_cambodia_life_premium(cambodia_req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation failed: {e}")

    resp = _serialize_cambodia(result)
    resp["input_parameters"]["occupation_type"] = occupation_type
    resp["input_parameters"]["motorbike_usage"] = motorbike_usage
    resp["input_parameters"]["province"] = province
    resp["input_parameters"]["healthcare_tier"] = healthcare_tier
    return resp


@router.post("/escalation")
async def life_escalation(req: LifeEscalationRequest):
    """
    Calculate escalated premium + full 20-year coverage schedule for a life insurance policy.

    Example:
        POST /api/v1/life/escalation
        {"base_annual_premium": 500, "base_coverage": 50000}
    """
    try:
        params = EscalationParameters(
            escalation_rate=req.escalation_rate,
            discount_rate=req.discount_rate,
            duration_years=req.duration_years,
            terminal_cap=req.terminal_cap,
            cap_utilization=ESCALATION_PARAMS.cap_utilization,
            bonus_year_10_pct=ESCALATION_PARAMS.bonus_year_10_pct,
            bonus_year_20_pct=ESCALATION_PARAMS.bonus_year_20_pct,
        )
        schedule = calculate_escalation_schedule(req.base_annual_premium, req.base_coverage, params)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Escalation calculation failed: {e}")

    return _serialize_escalation(schedule, params)


@router.post("/escalation/what-if")
async def life_escalation_what_if(req: LifeEscalationWhatIfRequest):
    """
    Compare escalation cost factors across up to 5 parameter scenarios.

    Example:
        POST /api/v1/life/escalation/what-if
        {"base_annual_premium": 500, "base_coverage": 50000, "scenarios": [{"escalation_rate": 0.03}, {"escalation_rate": 0.08}]}
    """
    if not req.scenarios:
        raise HTTPException(status_code=400, detail="At least one scenario required")

    results = []
    for i, overrides in enumerate(req.scenarios):
        try:
            params = EscalationParameters(
                escalation_rate=overrides.get("escalation_rate", ESCALATION_PARAMS.escalation_rate),
                discount_rate=overrides.get("discount_rate", ESCALATION_PARAMS.discount_rate),
                duration_years=overrides.get("duration_years", ESCALATION_PARAMS.duration_years),
                terminal_cap=overrides.get("terminal_cap", ESCALATION_PARAMS.terminal_cap),
                cap_utilization=ESCALATION_PARAMS.cap_utilization,
                bonus_year_10_pct=ESCALATION_PARAMS.bonus_year_10_pct,
                bonus_year_20_pct=ESCALATION_PARAMS.bonus_year_20_pct,
            )
            schedule = calculate_escalation_schedule(req.base_annual_premium, req.base_coverage, params)
            snap_years = {y for y in [1, 2, 3, 5, 10, 20] if y <= params.duration_years}
            snapshots = {
                f"year_{p.year}": {"coverage": p.coverage_amount, "cumulative_pct": p.cumulative_escalation_pct}
                for p in schedule.projections if p.year in snap_years
            }
            results.append({
                "scenario": i + 1,
                "parameters": overrides,
                "cost_factor": schedule.cost_factor,
                "cost_factor_pct": schedule.cost_factor_pct,
                "escalated_annual_premium": schedule.escalated_annual_premium,
                "escalated_monthly_premium": schedule.escalated_monthly_premium,
                "terminal_coverage": schedule.terminal_coverage,
                "cap_reached_at_year": schedule.cap_year,
                "coverage_snapshots": snapshots,
            })
        except Exception as e:
            results.append({"scenario": i + 1, "parameters": overrides, "error": str(e)})

    return {
        "base": {
            "annual_premium_no_escalation": req.base_annual_premium,
            "monthly_premium_no_escalation": round(req.base_annual_premium / 12, 2),
            "base_coverage": req.base_coverage,
        },
        "scenarios": results,
    }


@router.get("/assumptions")
async def life_assumptions():
    """Return current life pricing assumption version, mortality tables, and risk factors."""
    mort = ASSUMPTIONS["mortality"]
    rf = ASSUMPTIONS["risk_factors"]
    loading = ASSUMPTIONS["loading"]
    tiers = ASSUMPTIONS["tiers"]
    occ = ASSUMPTIONS.get("cambodia_occupational")
    endemic = ASSUMPTIONS.get("cambodia_endemic")
    hc = ASSUMPTIONS.get("cambodia_healthcare_tier")

    return {
        "version": ASSUMPTION_VERSION,
        "mortality": {
            "base_rate_male": mort.base_rate_male,
            "base_rate_female": mort.base_rate_female,
        },
        "risk_factors": {
            "smoking": rf.smoking,
            "alcohol_heavy": rf.alcohol_heavy,
            "diabetes": rf.diabetes,
            "hypertension": rf.hypertension,
            "hyperlipidemia": rf.hyperlipidemia,
            "family_history_chd": rf.family_history_chd,
            "bmi_underweight": rf.bmi_underweight,
            "bmi_overweight": rf.bmi_overweight,
            "bmi_obese_1": rf.bmi_obese_1,
            "bmi_obese_2": rf.bmi_obese_2,
        },
        "loading": {
            "expense_ratio": loading.expense_ratio,
            "commission_ratio": loading.commission_ratio,
            "profit_margin": loading.profit_margin,
            "contingency": loading.contingency,
            "total_loading": loading.total_loading,
        },
        "tiers": {
            "low_max": tiers.low_max,
            "medium_max": tiers.medium_max,
            "high_max": tiers.high_max,
        },
        "cambodia": {
            "mortality_adj": ASSUMPTIONS.get("cambodia_mortality_adj"),
            "occupational": {k: getattr(occ, k) for k in [
                "motorbike_courier", "motorbike_daily", "motorbike_occasional",
                "construction", "manual_labor", "healthcare", "retail_service",
                "office_desk", "retired",
            ]} if occ else {},
            "endemic": {k: getattr(endemic, k) for k in [
                "phnom_penh", "siem_reap", "sihanoukville", "battambang",
                "kampong_cham", "mondulkiri", "ratanakiri", "rural_default",
            ]} if endemic else {},
            "healthcare_tier": {k: getattr(hc, k) for k in [
                "tier_a", "tier_b", "clinic", "unknown",
            ]} if hc else {},
        },
    }
