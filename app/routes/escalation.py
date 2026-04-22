"""
Escalation Product Routes — DAC HealthPrice Platform

POST /api/v1/escalation        — compute escalated premium + 20-year schedule
POST /api/v1/escalation/what-if — compare up to 5 parameter scenarios
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from medical_reader.pricing.escalation_calculator import (
    EscalationParameters,
    ESCALATION_PARAMS,
    calculate_escalation_schedule,
)

router = APIRouter(prefix="/api/v1/escalation", tags=["escalation"])


# ── Request models ────────────────────────────────────────────────────────────

class EscalationRequest(BaseModel):
    base_annual_premium: float = Field(..., gt=0, description="Standard annual premium in USD")
    base_coverage: float       = Field(..., gt=0, description="Year 1 coverage / annual benefit limit in USD")
    escalation_rate: float     = Field(0.05, ge=0.01, le=0.20)
    discount_rate: float       = Field(0.06, ge=0.01, le=0.15)
    duration_years: int        = Field(20,   ge=5,    le=30)
    terminal_cap: float        = Field(2.50, ge=1.10, le=5.00)


class WhatIfRequest(BaseModel):
    base_annual_premium: float = Field(..., gt=0)
    base_coverage: float       = Field(..., gt=0)
    scenarios: List[dict]      = Field(..., max_length=5,
        description="List of param override dicts (escalation_rate, discount_rate, duration_years, terminal_cap)")


# ── Helper ────────────────────────────────────────────────────────────────────

def _serialize(schedule, params):
    return {
        "premium_summary": {
            "base_annual_premium":      schedule.base_annual_premium,
            "escalated_annual_premium": schedule.escalated_annual_premium,
            "escalated_monthly_premium": schedule.escalated_monthly_premium,
            "cost_factor":     schedule.cost_factor,
            "cost_factor_pct": schedule.cost_factor_pct,
        },
        "coverage_summary": {
            "year_1_coverage":     schedule.base_coverage,
            "terminal_coverage":   schedule.terminal_coverage,
            "terminal_cap_multiple": f"{params.terminal_cap:.1f}×",
            "cap_reached_at_year": schedule.cap_year,
        },
        "projections": [
            {
                "year":                      p.year,
                "coverage_multiple":         p.coverage_multiple,
                "coverage_amount":           p.coverage_amount,
                "annual_premium":            p.annual_premium,
                "monthly_premium":           p.monthly_premium,
                "cumulative_escalation_pct": p.cumulative_escalation_pct,
                "loyalty_bonus":             p.loyalty_bonus,
            }
            for p in schedule.projections
        ],
        "parameters": {
            "escalation_rate":  params.escalation_rate,
            "discount_rate":    params.discount_rate,
            "duration_years":   params.duration_years,
            "terminal_cap":     params.terminal_cap,
            "cap_utilization":  params.cap_utilization,
        },
        "metadata": {"escalation_version": schedule.version},
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("")
async def price_with_escalation(req: EscalationRequest):
    """
    Calculate escalated premium + full 20-year coverage schedule.

    The escalation product lets coverage grow 5%/year with the same level premium
    and no health re-check. The cost factor (~10.1% for defaults) is loaded into
    Year 1 premium to fund the increasing coverage obligation.

    Example:
        POST /api/v1/escalation
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

    return _serialize(schedule, params)


@router.post("/what-if")
async def escalation_what_if(req: WhatIfRequest):
    """
    Compare cost factors and premiums across up to 5 parameter scenarios.

    Useful for actuarial sensitivity analysis and IRC submissions.

    Example:
        POST /api/v1/escalation/what-if
        {
          "base_annual_premium": 500,
          "base_coverage": 50000,
          "scenarios": [
            {"escalation_rate": 0.03},
            {"escalation_rate": 0.05},
            {"escalation_rate": 0.08, "terminal_cap": 3.0}
          ]
        }
    """
    if not req.scenarios:
        raise HTTPException(status_code=400, detail="At least one scenario required")

    results = []
    for i, overrides in enumerate(req.scenarios):
        try:
            params = EscalationParameters(
                escalation_rate=overrides.get("escalation_rate", ESCALATION_PARAMS.escalation_rate),
                discount_rate=overrides.get("discount_rate",    ESCALATION_PARAMS.discount_rate),
                duration_years=overrides.get("duration_years",  ESCALATION_PARAMS.duration_years),
                terminal_cap=overrides.get("terminal_cap",      ESCALATION_PARAMS.terminal_cap),
                cap_utilization=ESCALATION_PARAMS.cap_utilization,
                bonus_year_10_pct=ESCALATION_PARAMS.bonus_year_10_pct,
                bonus_year_20_pct=ESCALATION_PARAMS.bonus_year_20_pct,
            )
            schedule = calculate_escalation_schedule(req.base_annual_premium, req.base_coverage, params)

            snap_years = {y for y in [1, 2, 3, 5, 10, 20] if y <= params.duration_years}
            snapshots  = {
                f"year_{p.year}": {"coverage": p.coverage_amount, "cumulative_pct": p.cumulative_escalation_pct}
                for p in schedule.projections if p.year in snap_years
            }
            results.append({
                "scenario":                  i + 1,
                "parameters":                overrides,
                "cost_factor":               schedule.cost_factor,
                "cost_factor_pct":           schedule.cost_factor_pct,
                "escalated_annual_premium":  schedule.escalated_annual_premium,
                "escalated_monthly_premium": schedule.escalated_monthly_premium,
                "terminal_coverage":         schedule.terminal_coverage,
                "cap_reached_at_year":       schedule.cap_year,
                "coverage_snapshots":        snapshots,
            })
        except Exception as e:
            results.append({"scenario": i + 1, "parameters": overrides, "error": str(e)})

    return {
        "base": {
            "annual_premium_no_escalation":  req.base_annual_premium,
            "monthly_premium_no_escalation": round(req.base_annual_premium / 12, 2),
            "base_coverage":                 req.base_coverage,
        },
        "scenarios": results,
    }
