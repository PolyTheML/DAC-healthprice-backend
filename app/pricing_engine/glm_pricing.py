"""
Auto Pricing Lab v2 — GLM Pricing Engine (Step 3)

compute_glm_price(profile) → GLMResult

Glass-box frequency-severity model. Every multiplier is visible
in the breakdown so actuaries can audit the price.

Formula:
  pure_premium = base_freq × base_sev × ∏(multipliers)
  loaded       = pure_premium × (1 + loading_factor)
  tiered       = loaded × tier_multiplier
  glm_price    = max(tiered - deductible_credit, min_premium)
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.COEFF_AUTO import (
    BASE_RATES,
    VEHICLE_AGE_MULTIPLIERS,
    DRIVER_AGE_MULTIPLIERS,
    REGION_MULTIPLIERS,
    ACCIDENT_HISTORY_MULTIPLIERS,
    COVERAGE_MULTIPLIERS,
    LOADING_FACTORS,
    TIER_MULTIPLIERS,
    DEDUCTIBLE_CREDITS,
    get_vehicle_age_bracket,
    get_driver_age_bracket,
)
from app.data.features import VehicleProfile

MIN_PREMIUM_VND = 500_000      # hard floor ~$20 USD


@dataclass
class GLMMultipliers:
    vehicle_age: float
    driver_age: float
    region: float
    accident_history: float
    coverage: float

    @property
    def combined(self) -> float:
        return (
            self.vehicle_age
            * self.driver_age
            * self.region
            * self.accident_history
            * self.coverage
        )


@dataclass
class GLMResult:
    # Inputs (echoed for transparency)
    vehicle_type: str
    region: str
    tier: str
    coverage: str

    # Base rates
    base_frequency: float       # claims/year
    base_severity: float        # VND/claim
    base_pure_premium: float    # = freq × sev (before multipliers)

    # Multipliers applied
    multipliers: GLMMultipliers
    combined_multiplier: float

    # Intermediate premiums
    risk_adjusted_premium: float   # base_pure × combined_multiplier
    loading_factor: float
    loaded_premium: float          # risk_adjusted × (1 + loading)
    tier_multiplier: float
    tiered_premium: float          # loaded × tier
    deductible_credit: float
    glm_price: float               # final GLM output (before ML adjustment)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["multipliers"] = asdict(self.multipliers)
        return d


def compute_glm_price(profile: VehicleProfile) -> GLMResult:
    """Compute the GLM-based auto insurance premium. Glass-box — no black box."""
    vt = profile.vehicle_type

    # 1. Base rates
    base_freq = BASE_RATES[vt]["frequency"]
    base_sev = BASE_RATES[vt]["severity"]
    base_pure = base_freq * base_sev

    # 2. Multipliers
    age_bracket = get_vehicle_age_bracket(profile.year_of_manufacture, profile.reference_year)
    drv_bracket = get_driver_age_bracket(profile.driver_age)

    mults = GLMMultipliers(
        vehicle_age=VEHICLE_AGE_MULTIPLIERS[vt][age_bracket],
        driver_age=DRIVER_AGE_MULTIPLIERS[drv_bracket],
        region=REGION_MULTIPLIERS[profile.region],
        accident_history=ACCIDENT_HISTORY_MULTIPLIERS[profile.accident_history],
        coverage=COVERAGE_MULTIPLIERS[profile.coverage],
    )

    # 3. Risk-adjusted pure premium
    risk_adj = base_pure * mults.combined

    # 4. Loading (expense + profit)
    load = LOADING_FACTORS[vt]
    loaded = risk_adj * (1.0 + load)

    # 5. Tier
    tier_mult = TIER_MULTIPLIERS[profile.tier]
    tiered = loaded * tier_mult

    # 6. Deductible credit
    ded_credit = DEDUCTIBLE_CREDITS[profile.tier]
    glm_price = max(tiered - ded_credit, MIN_PREMIUM_VND)

    return GLMResult(
        vehicle_type=vt,
        region=profile.region,
        tier=profile.tier,
        coverage=profile.coverage,
        base_frequency=base_freq,
        base_severity=base_sev,
        base_pure_premium=base_pure,
        multipliers=mults,
        combined_multiplier=mults.combined,
        risk_adjusted_premium=risk_adj,
        loading_factor=load,
        loaded_premium=loaded,
        tier_multiplier=tier_mult,
        tiered_premium=tiered,
        deductible_credit=ded_credit,
        glm_price=glm_price,
    )
