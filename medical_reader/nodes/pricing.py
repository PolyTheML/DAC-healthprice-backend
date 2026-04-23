"""
Pricing Node: Calculate actuarial premium using Mortality Ratio method.

Integrates with the pricing.calculator module for pure premium calculation.
Handles data extraction from UnderwritingState and population of ActuarialCalculation.

Based on: medical_reader/pricing/assumptions.py and calculator.py (v2.0)
"""

from ..state import UnderwritingState, RiskLevel, ActuarialCalculation
from ..pricing import (
    calculate_annual_premium,
    ASSUMPTIONS,
)


def pricing_node(state: UnderwritingState) -> UnderwritingState:
    """
    Pricing node: Calculate actuarial premium using Mortality Ratio method.

    Workflow:
    1. Validate intake is complete
    2. Extract medical data from state
    3. Call calculator to get PremiumBreakdown
    4. Populate ActuarialCalculation with transparent breakdown
    5. Determine risk tier and audit trail
    6. Return updated state

    Args:
        state: UnderwritingState with extracted_data populated

    Returns:
        Updated UnderwritingState with actuarial calculation
    """

    if not state.is_intake_complete:
        state.add_error("Cannot price: intake node not complete")
        return state

    data = state.extracted_data

    # Extract required fields (with sensible defaults)
    age = data.age or 45
    gender = data.gender or "M"
    bmi = data.bmi or 25.0
    smoker = data.smoker or False
    alcohol_use = data.alcohol_use or "None"
    diabetes = data.diabetes or False
    hypertension = data.hypertension or False
    hyperlipidemia = data.hyperlipidemia or False
    family_history_chd = data.family_history_chd or False
    systolic = data.blood_pressure_systolic
    diastolic = data.blood_pressure_diastolic

    # Product defaults: $50k face, 10-year term
    face_amount = data.face_amount or 50_000.0
    policy_term_years = data.policy_term_years or 10

    try:
        # Call the calculator
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
        state.add_error(f"Premium calculation failed: {str(e)}")
        return state

    # Map risk_tier from calculator to RiskLevel enum
    risk_tier_map = {
        "LOW": RiskLevel.LOW,
        "MEDIUM": RiskLevel.MEDIUM,
        "HIGH": RiskLevel.HIGH,
        "DECLINE": RiskLevel.DECLINE,
    }
    risk_level = risk_tier_map.get(breakdown.risk_tier, RiskLevel.MEDIUM)

    # Build human-readable calculation notes
    factors_applied = ", ".join(breakdown.factor_breakdown.keys()) if breakdown.factor_breakdown else "none"
    calculation_notes = (
        f"Mortality Ratio: {breakdown.mortality_ratio:.2f}x (risk factors: {factors_applied}). "
        f"Pure Premium: ${breakdown.pure_annual_premium:.2f}/year. "
        f"Gross Premium: ${breakdown.gross_annual_premium:.2f}/year "
        f"(Expense: ${breakdown.expense_loading:.2f}, "
        f"Commission: ${breakdown.commission_loading:.2f}, "
        f"Profit: ${breakdown.profit_loading:.2f}, "
        f"Contingency: ${breakdown.contingency_loading:.2f}). "
        f"Risk Tier: {breakdown.risk_tier}."
    )

    # Populate ActuarialCalculation with full breakdown
    state.actuarial = ActuarialCalculation(
        # New v2.0 fields
        face_amount=breakdown.face_amount,
        policy_term_years=breakdown.policy_term_years,
        base_mortality_rate=breakdown.base_mortality_rate,
        mortality_ratio=breakdown.mortality_ratio,
        pure_premium=breakdown.pure_annual_premium,
        expense_loading=breakdown.expense_loading,
        commission_loading=breakdown.commission_loading,
        profit_loading=breakdown.profit_loading,
        contingency_loading=breakdown.contingency_loading,
        total_loading_amount=breakdown.total_loading_amount,
        gross_premium=breakdown.gross_annual_premium,
        monthly_premium=breakdown.gross_monthly_premium,
        factor_breakdown=breakdown.factor_breakdown,
        # Backwards compatibility (v1.0 fields stay as 0.0)
        base_frequency=0.0,
        frequency_score=0.0,
        adjusted_frequency=0.0,
        base_severity=0.0,
        severity_score=0.0,
        adjusted_severity=0.0,
        base_premium=0.0,
        # Final premium (both versions)
        final_premium=breakdown.gross_annual_premium,
        # Metadata
        model_version="v2.0-mortality-ratio",
        assumption_version=breakdown.assumption_version,
        calculation_notes=calculation_notes,
    )

    # Update state workflow fields
    state.risk_level = risk_level
    state.risk_score = min(breakdown.mortality_ratio * 50.0, 100.0)  # Scale MR to 0-100
    state.status = "pricing"
    state.current_node = "pricing"

    # Add comprehensive audit trail entry
    state.add_audit_entry(
        node="pricing",
        action="calculated_premium",
        details={
            "mortality_ratio": breakdown.mortality_ratio,
            "risk_factors_applied": list(breakdown.factor_breakdown.keys()),
            "pure_premium": breakdown.pure_annual_premium,
            "gross_premium": breakdown.gross_annual_premium,
            "monthly_premium": breakdown.gross_monthly_premium,
            "risk_tier": breakdown.risk_tier,
            "assumption_version": breakdown.assumption_version,
        },
        confidence=0.95,
    )

    return state
