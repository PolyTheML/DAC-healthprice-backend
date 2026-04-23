"""
Life Pricing Node: Cambodia-specific premium calculation with risk adjustments.

Delegates to calculate_cambodia_life_premium() for the actual calculation,
then maps the result to UnderwritingState fields.

IRC Compliance: Every calculation is stamped with assumption_version and
includes a full factor_breakdown for regulatory transparency.
"""

from typing import Optional, Dict, Any
from ..state import UnderwritingState, RiskLevel, CambodiaOccupationRisk, CambodiaRegionRisk
from ..pricing.assumptions import ASSUMPTIONS
from ..pricing.cambodia_pricing import (
    CambodiaLifePricingRequest,
    calculate_cambodia_life_premium,
)


def life_pricing_node(state: UnderwritingState) -> UnderwritingState:
    """
    Life Pricing Node: Cambodia-specific premium calculation.

    Delegates to calculate_cambodia_life_premium() for the pure calculation,
    then maps the result to UnderwritingState fields and populates
    occupation_risk and region_risk sub-objects.

    Args:
        state: UnderwritingState with intake_complete

    Returns:
        Updated UnderwritingState with actuarial pricing and Cambodia risk sub-objects
    """

    # ========== GUARD ==========
    if not state.is_intake_complete:
        state.add_error("Cannot run life_pricing: intake not complete")
        state.status = "error"
        return state

    extracted = state.extracted_data

    # ========== BUILD REQUEST ==========
    req = CambodiaLifePricingRequest(
        age=extracted.age or 45,
        gender=extracted.gender or "M",
        bmi=extracted.bmi or 25.0,
        smoker=extracted.smoker or False,
        alcohol_use=extracted.alcohol_use or "None",
        diabetes=extracted.diabetes or False,
        hypertension=extracted.hypertension or False,
        hyperlipidemia=extracted.hyperlipidemia or False,
        family_history_chd=extracted.family_history_chd or False,
        systolic=extracted.blood_pressure_systolic or 120,
        diastolic=extracted.blood_pressure_diastolic or 80,
        face_amount=extracted.face_amount or 50_000.0,
        policy_term_years=extracted.policy_term_years or 10,
        occupation_type=extracted.occupation_type or "office_desk",
        motorbike_usage=extracted.motorbike_usage or "never",
        province=extracted.province or "phnom_penh",
        healthcare_tier=extracted.healthcare_tier or "unknown",
    )

    # ========== CALCULATE ==========
    result = calculate_cambodia_life_premium(req, ASSUMPTIONS)
    base = result.base

    # ========== MAP TO STATE ==========
    # Occupation risk sub-object
    state.occupation_risk = CambodiaOccupationRisk(
        occupation_type=req.occupation_type,
        motorbike_usage=req.motorbike_usage,
        risk_multiplier=result.occupation_multiplier,
        risk_notes=result.occupation_notes,
    )

    # Region risk sub-object
    state.region_risk = CambodiaRegionRisk(
        province=req.province,
        healthcare_tier=req.healthcare_tier,
        endemic_risk_multiplier=result.endemic_multiplier,
        healthcare_reliability_discount=result.healthcare_discount,
        region_notes=f"{result.endemic_notes} | {result.healthcare_notes}",
    )

    # Actuarial fields
    state.actuarial.face_amount = req.face_amount
    state.actuarial.policy_term_years = req.policy_term_years
    state.actuarial.base_mortality_rate = base.base_mortality_rate
    state.actuarial.mortality_ratio = result.adjusted_mortality_ratio
    state.actuarial.pure_premium = result.adjusted_pure_premium
    state.actuarial.expense_loading = result.adjusted_pure_premium * ASSUMPTIONS["loading"].expense_ratio
    state.actuarial.commission_loading = result.adjusted_pure_premium * ASSUMPTIONS["loading"].commission_ratio
    state.actuarial.profit_loading = result.adjusted_pure_premium * ASSUMPTIONS["loading"].profit_margin
    state.actuarial.contingency_loading = result.adjusted_pure_premium * ASSUMPTIONS["loading"].contingency
    state.actuarial.total_loading_amount = (
        state.actuarial.expense_loading + state.actuarial.commission_loading
        + state.actuarial.profit_loading + state.actuarial.contingency_loading
    )
    state.actuarial.gross_premium = result.final_gross_premium
    state.actuarial.monthly_premium = result.final_monthly_premium
    state.actuarial.final_premium = result.final_gross_premium
    state.actuarial.factor_breakdown = result.factor_breakdown

    # Risk level
    risk_level_map = {
        "LOW": RiskLevel.LOW,
        "MEDIUM": RiskLevel.MEDIUM,
        "HIGH": RiskLevel.HIGH,
        "DECLINE": RiskLevel.DECLINE,
    }
    state.risk_level = risk_level_map.get(result.risk_tier, RiskLevel.MEDIUM)
    state.risk_score = min(result.adjusted_mortality_ratio * 50.0, 100.0)

    # Metadata
    state.status = "pricing"
    state.current_node = "life_pricing"
    state.actuarial.model_version = result.model_version
    state.actuarial.assumption_version = result.assumption_version
    state.actuarial.calculation_notes = (
        f"Cambodia Life Insurance Pricing. "
        f"Base MR={base.mortality_ratio:.2f}, "
        f"Occupational={result.occupation_multiplier:.2f}, "
        f"Endemic={result.endemic_multiplier:.2f}, "
        f"Healthcare Tier Discount={result.healthcare_discount:.2f}. "
        f"Final MR={result.adjusted_mortality_ratio:.2f}. "
        f"Premium: ${result.final_gross_premium:,.2f}/year (${result.final_monthly_premium:,.2f}/month)"
    )

    # Audit trail
    state.add_audit_entry(
        node="life_pricing",
        action="calculated_life_premium",
        details={
            "face_amount": req.face_amount,
            "base_mortality_rate": base.base_mortality_rate,
            "base_mortality_ratio": base.mortality_ratio,
            "occupational_multiplier": result.occupation_multiplier,
            "endemic_multiplier": result.endemic_multiplier,
            "adjusted_mortality_ratio": result.adjusted_mortality_ratio,
            "pure_premium": result.adjusted_pure_premium,
            "gross_premium": result.final_gross_premium,
            "monthly_premium": result.final_monthly_premium,
            "risk_level": state.risk_level.value,
            "risk_score": round(state.risk_score, 1),
            "factor_breakdown": {k: round(v, 4) for k, v in result.factor_breakdown.items()},
            "assumption_version": result.assumption_version,
        },
        confidence=0.95,
    )

    return state
