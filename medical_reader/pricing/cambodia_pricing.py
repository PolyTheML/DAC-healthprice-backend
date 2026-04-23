"""
Cambodia-specific life insurance pricing — pure functions.

Wraps the base life insurance calculator with Cambodia-specific adjustments:
- Occupational mortality surcharges (motorbike, construction, etc.)
- Provincial endemic disease multipliers (dengue, malaria)
- Healthcare-tier reliability discounts

This module is the single entry point for Cambodia life pricing.
The LangGraph `life_pricing_node` delegates to this module; the API routes
also call these functions directly.

IRC Compliance: Every result includes assumption_version and full factor_breakdown.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from .calculator import PremiumBreakdown, calculate_annual_premium
from .assumptions import (
    ASSUMPTIONS,
    ASSUMPTION_VERSION,
    CAMBODIA_MORTALITY_ADJ,
    CambodiaOccupationalMultipliers,
    CambodiaEndemicMultipliers,
    CambodiaHealthcareTierDiscount,
)


@dataclass
class CambodiaLifePricingRequest:
    age: Optional[int] = 45
    gender: str = "M"
    bmi: Optional[float] = 25.0
    smoker: bool = False
    alcohol_use: str = "None"
    diabetes: bool = False
    hypertension: bool = False
    hyperlipidemia: bool = False
    family_history_chd: bool = False
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    face_amount: float = 50_000.0
    policy_term_years: int = 10
    # Cambodia-specific
    occupation_type: str = "office_desk"
    motorbike_usage: str = "never"
    province: str = "phnom_penh"
    healthcare_tier: str = "unknown"


@dataclass
class CambodiaLifePricingResult:
    # Base premium breakdown (from calculate_annual_premium)
    base: PremiumBreakdown = None
    # Cambodia adjustments
    occupation_multiplier: float = 1.0
    occupation_notes: str = ""
    endemic_multiplier: float = 1.0
    endemic_notes: str = ""
    healthcare_discount: float = 1.0
    healthcare_notes: str = ""
    # Adjusted results
    adjusted_mortality_ratio: float = 1.0
    adjusted_pure_premium: float = 0.0
    adjusted_gross_premium: float = 0.0
    final_gross_premium: float = 0.0
    final_monthly_premium: float = 0.0
    # Full factor breakdown (base + Cambodia)
    factor_breakdown: Dict[str, float] = field(default_factory=dict)
    # Risk classification
    risk_tier: str = "MEDIUM"
    # Metadata
    assumption_version: str = ASSUMPTION_VERSION
    model_version: str = "v3.0-cambodia-life"


def _lookup_occupation_multiplier(
    occupation_type: str,
    motorbike_usage: str,
    occupational_mult: CambodiaOccupationalMultipliers,
) -> tuple[float, str]:
    mu = motorbike_usage.lower()
    ot = occupation_type.lower()

    if mu == "daily":
        return occupational_mult.motorbike_daily, f"Daily motorbike usage → {(occupational_mult.motorbike_daily - 1.0) * 100:+.0f}% mortality surcharge"
    if mu == "occasional":
        return occupational_mult.motorbike_occasional, f"Occasional motorbike usage → {(occupational_mult.motorbike_occasional - 1.0) * 100:+.0f}% mortality surcharge"
    if ot == "motorbike_courier":
        return occupational_mult.motorbike_courier, f"Motorbike courier → {(occupational_mult.motorbike_courier - 1.0) * 100:+.0f}% mortality surcharge"
    if ot == "construction":
        return occupational_mult.construction, f"Construction worker → {(occupational_mult.construction - 1.0) * 100:+.0f}% mortality surcharge"
    if ot == "manual_labor":
        return occupational_mult.manual_labor, f"Manual labor → {(occupational_mult.manual_labor - 1.0) * 100:+.0f}% mortality surcharge"
    if ot == "healthcare":
        return occupational_mult.healthcare, f"Healthcare worker → {(occupational_mult.healthcare - 1.0) * 100:+.0f}% infection risk surcharge"
    if ot in ("retail", "service"):
        return occupational_mult.retail_service, f"Retail/Service → {(occupational_mult.retail_service - 1.0) * 100:+.0f}% surcharge"
    if ot == "retired":
        return occupational_mult.retired, f"Retired → {(occupational_mult.retired - 1.0) * 100:+.0f}% reduction"
    return occupational_mult.office_desk, "Office/Desk work (baseline occupation risk)"


def _lookup_endemic_multiplier(
    province: str,
    endemic_mult: CambodiaEndemicMultipliers,
) -> tuple[float, str]:
    key = province.lower().replace(" ", "_")
    mult = getattr(endemic_mult, key, endemic_mult.rural_default)
    return mult, f"Province: {province} → {(mult - 1.0) * 100:+.0f}% endemic disease surcharge"


def _lookup_healthcare_discount(
    healthcare_tier: str,
    tier_obj: CambodiaHealthcareTierDiscount,
) -> tuple[float, str]:
    t = healthcare_tier.lower()
    if t in ("tier_a", "tiera", "a"):
        return tier_obj.tier_a, "TierA hospital exam → -3% premium (high-confidence)"
    if t in ("tier_b", "tierb", "b"):
        return tier_obj.tier_b, "TierB hospital exam → no adjustment"
    if t in ("clinic", "local"):
        return tier_obj.clinic, "Local clinic exam → +5% premium (lower reliability)"
    return tier_obj.unknown, "Unknown exam facility → +3% premium (conservative)"


def calculate_cambodia_life_premium(
    req: CambodiaLifePricingRequest,
    assumptions: dict = ASSUMPTIONS,
) -> CambodiaLifePricingResult:
    """
    Calculate Cambodia-specific life insurance premium.

    Pipeline:
    1. calculate_annual_premium() → base PremiumBreakdown
    2. Look up occupational multiplier
    3. Look up endemic disease multiplier
    4. Adjust mortality ratio additively
    5. Recompute pure premium and loadings with adjusted MR
    6. Apply healthcare-tier discount
    7. Classify risk tier
    """
    # Step 1: Base premium
    base = calculate_annual_premium(
        face_amount=req.face_amount,
        policy_term_years=req.policy_term_years,
        age=req.age,
        gender=req.gender,
        bmi=req.bmi,
        smoker=req.smoker,
        alcohol_use=req.alcohol_use,
        diabetes=req.diabetes,
        hypertension=req.hypertension,
        hyperlipidemia=req.hyperlipidemia,
        family_history_chd=req.family_history_chd,
        systolic=req.systolic,
        diastolic=req.diastolic,
        assumptions=assumptions,
    )

    # Step 2: Occupational risk
    occupational_mult = assumptions.get("cambodia_occupational", CambodiaOccupationalMultipliers())
    occ_mult, occ_notes = _lookup_occupation_multiplier(
        req.occupation_type, req.motorbike_usage, occupational_mult,
    )

    # Step 3: Endemic disease
    endemic_mult = assumptions.get("cambodia_endemic", CambodiaEndemicMultipliers())
    end_mult, end_notes = _lookup_endemic_multiplier(req.province, endemic_mult)

    # Step 4: Adjust mortality ratio
    adjusted_mr = base.mortality_ratio + (occ_mult - 1.0) + (end_mult - 1.0)

    # Step 5: Recompute pure premium and loadings
    q_x = base.base_mortality_rate
    adjusted_pure = req.face_amount * (q_x / 1000.0) * adjusted_mr

    loading = assumptions.get("loading")
    expense = adjusted_pure * loading.expense_ratio
    commission = adjusted_pure * loading.commission_ratio
    profit = adjusted_pure * loading.profit_margin
    contingency = adjusted_pure * loading.contingency
    total_loading = expense + commission + profit + contingency
    adjusted_gross = adjusted_pure + total_loading

    # Step 6: Healthcare-tier discount
    tier_obj = assumptions.get("cambodia_healthcare_tier", CambodiaHealthcareTierDiscount())
    hc_discount, hc_notes = _lookup_healthcare_discount(req.healthcare_tier, tier_obj)
    final_gross = adjusted_gross * hc_discount
    final_monthly = final_gross / 12.0

    # Step 7: Risk tier
    tiers = assumptions.get("tiers")
    if adjusted_mr <= tiers.low_max:
        risk_tier = "LOW"
    elif adjusted_mr <= tiers.medium_max:
        risk_tier = "MEDIUM"
    elif adjusted_mr <= tiers.high_max:
        risk_tier = "HIGH"
    else:
        risk_tier = "DECLINE"

    # Factor breakdown
    factor_breakdown = dict(base.factor_breakdown)
    factor_breakdown["cambodia_occupational"] = occ_mult
    factor_breakdown["cambodia_endemic"] = end_mult
    factor_breakdown["cambodia_healthcare_tier"] = hc_discount
    factor_breakdown["cambodia_mortality_adj"] = CAMBODIA_MORTALITY_ADJ

    return CambodiaLifePricingResult(
        base=base,
        occupation_multiplier=occ_mult,
        occupation_notes=occ_notes,
        endemic_multiplier=end_mult,
        endemic_notes=end_notes,
        healthcare_discount=hc_discount,
        healthcare_notes=hc_notes,
        adjusted_mortality_ratio=adjusted_mr,
        adjusted_pure_premium=adjusted_pure,
        adjusted_gross_premium=adjusted_gross,
        final_gross_premium=final_gross,
        final_monthly_premium=final_monthly,
        factor_breakdown=factor_breakdown,
        risk_tier=risk_tier,
        assumption_version=assumptions.get("version", ASSUMPTION_VERSION),
    )
