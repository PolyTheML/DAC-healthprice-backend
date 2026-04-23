"""API routes for /pricing endpoints (sensitivity analysis, what-if scenarios)."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from medical_reader.pricing import (
    calculate_annual_premium,
    ASSUMPTIONS,
    calculate_escalation_schedule,
    EscalationParameters,
    ESCALATION_PARAMS,
)


router = APIRouter()


# ============= ESCALATION MODELS =============

class EscalationRequest(BaseModel):
    """Request body for escalation pricing endpoints."""

    base_annual_premium: float = Field(..., gt=0, description="Standard annual premium in USD (before escalation)")
    base_coverage: float = Field(..., gt=0, description="Year 1 coverage amount in USD")

    # Optional parameter overrides
    escalation_rate: float = Field(0.05, ge=0.01, le=0.20, description="Annual coverage escalation rate (default 5%)")
    discount_rate: float = Field(0.06, ge=0.01, le=0.15, description="Actuarial discount rate (default 6%)")
    duration_years: int = Field(20, ge=5, le=30, description="Policy duration in years (default 20)")
    terminal_cap: float = Field(2.50, ge=1.10, le=5.00, description="Max coverage multiple vs. base (default 2.5×)")


class EscalationWhatIfRequest(BaseModel):
    """Request body for escalation what-if comparisons."""

    base_annual_premium: float = Field(..., gt=0)
    base_coverage: float = Field(..., gt=0)
    scenarios: List[dict] = Field(
        ...,
        description="List of parameter override dicts. Each can set: escalation_rate, discount_rate, duration_years, terminal_cap",
        max_length=5,
    )


@router.get("/what-if")
async def pricing_what_if(
    age: int = 45,
    gender: str = "M",
    bmi: float = 25.0,
    smoker: bool = False,
    alcohol_use: Optional[str] = None,
    diabetes: bool = False,
    hypertension: bool = False,
    hyperlipidemia: bool = False,
    family_history_chd: bool = False,
    systolic: Optional[int] = None,
    diastolic: Optional[int] = None,
    face_amount: float = 50000.0,
    policy_term_years: int = 10,
):
    """
    What-if analysis: Calculate premium for arbitrary medical/product parameters.

    Query parameters:
    - age: Age in years (18-100)
    - gender: M or F (default M)
    - bmi: Body Mass Index (10-60)
    - smoker: true/false (default false)
    - alcohol_use: None/Moderate/Heavy (default None)
    - diabetes: true/false (default false)
    - hypertension: true/false (default false)
    - hyperlipidemia: true/false (default false)
    - family_history_chd: true/false (default false)
    - systolic: Systolic BP in mmHg (optional)
    - diastolic: Diastolic BP in mmHg (optional)
    - face_amount: Coverage amount in USD (default 50000)
    - policy_term_years: Policy term in years (default 10)

    Returns:
    Full premium breakdown with all components visible.

    Example:
        GET /pricing/what-if?age=55&smoker=true&face_amount=100000&policy_term_years=20
    """

    try:
        breakdown = calculate_annual_premium(
            face_amount=face_amount,
            policy_term_years=policy_term_years,
            age=age,
            gender=gender,
            bmi=bmi,
            smoker=smoker,
            alcohol_use=alcohol_use,
            diabetes=diabetes,
            hypertension=hypertension,
            hyperlipidemia=hyperlipidemia,
            family_history_chd=family_history_chd,
            systolic=systolic,
            diastolic=diastolic,
            assumptions=ASSUMPTIONS,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation failed: {str(e)}")

    return {
        "input_parameters": {
            "age": age,
            "gender": gender,
            "bmi": bmi,
            "smoker": smoker,
            "alcohol_use": alcohol_use,
            "diabetes": diabetes,
            "hypertension": hypertension,
            "hyperlipidemia": hyperlipidemia,
            "family_history_chd": family_history_chd,
            "systolic": systolic,
            "diastolic": diastolic,
            "face_amount": face_amount,
            "policy_term_years": policy_term_years,
        },
        "mortality_calculation": {
            "base_mortality_rate": round(breakdown.base_mortality_rate, 4),
            "mortality_ratio": round(breakdown.mortality_ratio, 4),
            "risk_factors_applied": breakdown.factor_breakdown,
        },
        "premium_breakdown": {
            "pure_annual_premium": round(breakdown.pure_annual_premium, 2),
            "expense_loading": round(breakdown.expense_loading, 2),
            "commission_loading": round(breakdown.commission_loading, 2),
            "profit_loading": round(breakdown.profit_loading, 2),
            "contingency_loading": round(breakdown.contingency_loading, 2),
            "total_loading": round(breakdown.total_loading_amount, 2),
            "gross_annual_premium": round(breakdown.gross_annual_premium, 2),
            "gross_monthly_premium": round(breakdown.gross_monthly_premium, 2),
        },
        "risk_classification": {
            "risk_tier": breakdown.risk_tier,
            "mortality_ratio_formatted": f"{breakdown.mortality_ratio:.1%}",
        },
        "metadata": {
            "assumption_version": breakdown.assumption_version,
        },
    }


# ============= ESCALATION ENDPOINTS =============

@router.post("/escalation")
async def price_with_escalation(req: EscalationRequest):
    """
    Calculate premium and full 20-year schedule for an automatic escalation product.

    The escalation product lets coverage grow 5% per year with no health re-check,
    while the customer pays the same level premium every year.

    The cost factor (~10.3% for default params) is loaded into Year 1 premium to fund
    the increasing coverage obligation.

    Request body:
    - base_annual_premium: Standard (non-escalated) annual premium in USD
    - base_coverage:        Year 1 coverage / annual benefit limit in USD
    - escalation_rate:      Annual escalation rate (default 0.05 = 5%)
    - discount_rate:        Actuarial discount rate (default 0.06 = 6%)
    - duration_years:       Policy duration (default 20)
    - terminal_cap:         Max coverage multiple (default 2.5× = 250%)

    Returns:
    - Escalated Year 1 premium (annual + monthly)
    - Cost factor with breakdown
    - Full year-by-year coverage and loyalty bonus schedule
    - IRC-compliant parameter audit trail

    Example:
        POST /pricing/escalation
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
        schedule = calculate_escalation_schedule(
            base_annual_premium=req.base_annual_premium,
            base_coverage=req.base_coverage,
            params=params,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Escalation calculation failed: {str(e)}")

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
            "terminal_cap_multiple": f"{params.terminal_cap:.1f}×",
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
        "metadata": {
            "escalation_version": schedule.version,
        },
    }


@router.post("/escalation/what-if")
async def escalation_what_if(req: EscalationWhatIfRequest):
    """
    Compare escalation cost factors and premiums across multiple parameter scenarios.

    Useful for actuarial sensitivity analysis and IRC submissions showing
    how the product behaves under different assumptions.

    Request body:
    - base_annual_premium: Standard annual premium in USD
    - base_coverage:        Year 1 coverage in USD
    - scenarios:            List of up to 5 parameter override dicts

    Each scenario dict can contain any of:
        escalation_rate, discount_rate, duration_years, terminal_cap

    Returns:
    Comparison table of cost factors, escalated premiums, and 5-year snapshots
    for each scenario vs. the base (no escalation).

    Example:
        POST /pricing/escalation/what-if
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
    for i, scenario_overrides in enumerate(req.scenarios):
        try:
            params = EscalationParameters(
                escalation_rate=scenario_overrides.get("escalation_rate", ESCALATION_PARAMS.escalation_rate),
                discount_rate=scenario_overrides.get("discount_rate", ESCALATION_PARAMS.discount_rate),
                duration_years=scenario_overrides.get("duration_years", ESCALATION_PARAMS.duration_years),
                terminal_cap=scenario_overrides.get("terminal_cap", ESCALATION_PARAMS.terminal_cap),
                cap_utilization=ESCALATION_PARAMS.cap_utilization,
                bonus_year_10_pct=ESCALATION_PARAMS.bonus_year_10_pct,
                bonus_year_20_pct=ESCALATION_PARAMS.bonus_year_20_pct,
            )
            schedule = calculate_escalation_schedule(
                base_annual_premium=req.base_annual_premium,
                base_coverage=req.base_coverage,
                params=params,
            )

            # 5-year snapshot: years 1, 2, 3, 5, 10 (or fewer if duration < 10)
            snapshot_years = [y for y in [1, 2, 3, 5, 10] if y <= params.duration_years]
            snapshots = {
                f"year_{p.year}": {
                    "coverage": p.coverage_amount,
                    "cumulative_escalation_pct": p.cumulative_escalation_pct,
                }
                for p in schedule.projections
                if p.year in snapshot_years
            }

            results.append({
                "scenario": i + 1,
                "parameters": {k: v for k, v in scenario_overrides.items()},
                "cost_factor": schedule.cost_factor,
                "cost_factor_pct": schedule.cost_factor_pct,
                "escalated_annual_premium": schedule.escalated_annual_premium,
                "escalated_monthly_premium": schedule.escalated_monthly_premium,
                "terminal_coverage": schedule.terminal_coverage,
                "cap_reached_at_year": schedule.cap_year,
                "coverage_snapshots": snapshots,
            })
        except Exception as e:
            results.append({
                "scenario": i + 1,
                "parameters": scenario_overrides,
                "error": str(e),
            })

    return {
        "base": {
            "annual_premium_no_escalation": req.base_annual_premium,
            "monthly_premium_no_escalation": round(req.base_annual_premium / 12, 2),
            "base_coverage": req.base_coverage,
        },
        "scenarios": results,
    }
