"""
Pricing module: Modular, auditable actuarial calculations for life insurance.

This module exports:
- assumptions: MortalityAssumptions, RiskFactorMultipliers, LoadingFactors, etc.
- calculator: Pure calculation functions (no state dependency)
- escalation_calculator: Automatic coverage escalation product pricing
"""

from .assumptions import (
    ASSUMPTION_VERSION,
    MortalityAssumptions,
    RiskFactorMultipliers,
    LoadingFactors,
    RiskTierThresholds,
    ASSUMPTIONS,
)
from .calculator import (
    PremiumBreakdown,
    classify_blood_pressure,
    classify_bmi,
    get_base_mortality_rate,
    calculate_mortality_ratio,
    calculate_annual_premium,
)
from .escalation_calculator import (
    EscalationParameters,
    EscalationSchedule,
    YearProjection,
    ESCALATION_PARAMS,
    ESCALATION_VERSION,
    compute_cost_factor,
    calculate_escalation_schedule,
)
from .cambodia_pricing import (
    CambodiaLifePricingRequest,
    CambodiaLifePricingResult,
    calculate_cambodia_life_premium,
)

__all__ = [
    "ASSUMPTION_VERSION",
    "MortalityAssumptions",
    "RiskFactorMultipliers",
    "LoadingFactors",
    "RiskTierThresholds",
    "ASSUMPTIONS",
    "PremiumBreakdown",
    "classify_blood_pressure",
    "classify_bmi",
    "get_base_mortality_rate",
    "calculate_mortality_ratio",
    "calculate_annual_premium",
    "EscalationParameters",
    "EscalationSchedule",
    "YearProjection",
    "ESCALATION_PARAMS",
    "ESCALATION_VERSION",
    "compute_cost_factor",
    "calculate_escalation_schedule",
    "CambodiaLifePricingRequest",
    "CambodiaLifePricingResult",
    "calculate_cambodia_life_premium",
]
