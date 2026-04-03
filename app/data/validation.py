"""
Auto Pricing Lab v2 — Input Validation

Checks VehicleProfile values against allowed constants before pricing.
"""
from __future__ import annotations
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.COEFF_AUTO import (
    BASE_RATES, REGION_MULTIPLIERS, COVERAGE_MULTIPLIERS, TIER_MULTIPLIERS
)

VALID_VEHICLE_TYPES = list(BASE_RATES.keys())
VALID_REGIONS = list(REGION_MULTIPLIERS.keys())
VALID_COVERAGE_TYPES = list(COVERAGE_MULTIPLIERS.keys())
VALID_TIERS = list(TIER_MULTIPLIERS.keys())

MIN_DRIVER_AGE = 18
MAX_DRIVER_AGE = 75
MIN_VEHICLE_YEAR = 1980
MAX_FAMILY_SIZE = 6


def validate_profile(data: dict) -> Optional[str]:
    """Return error string if invalid, None if valid."""
    vt = data.get("vehicle_type")
    if vt not in VALID_VEHICLE_TYPES:
        return f"vehicle_type must be one of {VALID_VEHICLE_TYPES}, got '{vt}'"

    yom = data.get("year_of_manufacture")
    if not isinstance(yom, int) or yom < MIN_VEHICLE_YEAR or yom > 2025:
        return f"year_of_manufacture must be {MIN_VEHICLE_YEAR}–2025, got '{yom}'"

    region = data.get("region")
    if region not in VALID_REGIONS:
        return f"region must be one of {VALID_REGIONS}, got '{region}'"

    age = data.get("driver_age")
    if not isinstance(age, int) or age < MIN_DRIVER_AGE or age > MAX_DRIVER_AGE:
        return f"driver_age must be {MIN_DRIVER_AGE}–{MAX_DRIVER_AGE}, got '{age}'"

    if not isinstance(data.get("accident_history"), bool):
        return "accident_history must be true or false"

    cov = data.get("coverage")
    if cov not in VALID_COVERAGE_TYPES:
        return f"coverage must be one of {VALID_COVERAGE_TYPES}, got '{cov}'"

    tier = data.get("tier")
    if tier not in VALID_TIERS:
        return f"tier must be one of {VALID_TIERS}, got '{tier}'"

    fs = data.get("family_size", 1)
    if not isinstance(fs, int) or fs < 1 or fs > MAX_FAMILY_SIZE:
        return f"family_size must be 1–{MAX_FAMILY_SIZE}, got '{fs}'"

    return None
