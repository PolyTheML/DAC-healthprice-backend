"""
Auto Pricing Lab v2 — Feature Extraction (Step 12, used by Steps 3-5)

Single source of truth for feature engineering.
Used identically in GLM pricing, ML training, and ML inference.
Prevents training-serving skew.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.COEFF_AUTO import (
    get_vehicle_age_bracket,
    get_driver_age_bracket,
    VEHICLE_AGE_MULTIPLIERS,
    DRIVER_AGE_MULTIPLIERS,
    REGION_MULTIPLIERS,
    ACCIDENT_HISTORY_MULTIPLIERS,
    COVERAGE_MULTIPLIERS,
    BASE_RATES,
)


@dataclass
class VehicleProfile:
    """Input profile for auto pricing."""
    vehicle_type: str           # motorcycle | sedan | suv | truck
    year_of_manufacture: int    # e.g. 2019
    region: str                 # phnom_penh | hanoi | ...
    driver_age: int             # 18-75
    accident_history: bool      # any prior claim
    coverage: str               # ctpl_only | full
    tier: str                   # basic | standard | premium | full
    family_size: int = 1        # 1-6
    reference_year: int = 2024


@dataclass
class ExtractedFeatures:
    """Flat numeric features for ML model."""
    # Raw inputs
    vehicle_type_enc: int       # 0-3 label encoding
    year_of_manufacture: int
    driver_age: int
    accident_history: int       # 0/1
    family_size: int

    # Derived multipliers (same as GLM uses — shared)
    vehicle_age_mult: float
    driver_age_mult: float
    region_mult: float
    accident_mult: float
    coverage_mult: float

    # Base rates
    base_frequency: float
    base_severity: float

    # Computed GLM pure premium (before loading/tier) — key residual target feature
    glm_pure_premium: float

    def to_list(self) -> list[float]:
        return [
            self.vehicle_type_enc,
            self.year_of_manufacture,
            self.driver_age,
            self.accident_history,
            self.family_size,
            self.vehicle_age_mult,
            self.driver_age_mult,
            self.region_mult,
            self.accident_mult,
            self.coverage_mult,
            self.base_frequency,
            self.base_severity,
            self.glm_pure_premium,
        ]

    @classmethod
    def feature_names(cls) -> list[str]:
        return [
            "vehicle_type_enc",
            "year_of_manufacture",
            "driver_age",
            "accident_history",
            "family_size",
            "vehicle_age_mult",
            "driver_age_mult",
            "region_mult",
            "accident_mult",
            "coverage_mult",
            "base_frequency",
            "base_severity",
            "glm_pure_premium",
        ]


_VEHICLE_TYPE_INDEX = {"motorcycle": 0, "sedan": 1, "suv": 2, "truck": 3}


def extract_features(profile: VehicleProfile) -> ExtractedFeatures:
    """Extract flat numeric features from a VehicleProfile."""
    vt = profile.vehicle_type
    age_bracket = get_vehicle_age_bracket(profile.year_of_manufacture, profile.reference_year)
    drv_bracket = get_driver_age_bracket(profile.driver_age)

    vehicle_age_mult = VEHICLE_AGE_MULTIPLIERS[vt][age_bracket]
    driver_age_mult = DRIVER_AGE_MULTIPLIERS[drv_bracket]
    region_mult = REGION_MULTIPLIERS[profile.region]
    accident_mult = ACCIDENT_HISTORY_MULTIPLIERS[profile.accident_history]
    coverage_mult = COVERAGE_MULTIPLIERS[profile.coverage]

    base_freq = BASE_RATES[vt]["frequency"]
    base_sev = BASE_RATES[vt]["severity"]

    # Pure premium = freq × sev × all multipliers (no loading/tier yet)
    glm_pure = (
        base_freq * base_sev
        * vehicle_age_mult
        * driver_age_mult
        * region_mult
        * accident_mult
        * coverage_mult
    )

    return ExtractedFeatures(
        vehicle_type_enc=_VEHICLE_TYPE_INDEX[vt],
        year_of_manufacture=profile.year_of_manufacture,
        driver_age=profile.driver_age,
        accident_history=int(profile.accident_history),
        family_size=profile.family_size,
        vehicle_age_mult=vehicle_age_mult,
        driver_age_mult=driver_age_mult,
        region_mult=region_mult,
        accident_mult=accident_mult,
        coverage_mult=coverage_mult,
        base_frequency=base_freq,
        base_severity=base_sev,
        glm_pure_premium=glm_pure,
    )
