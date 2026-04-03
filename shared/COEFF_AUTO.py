"""
Auto Pricing Lab v2 — Actuarial Coefficient Table (Python)
Python mirror of src/shared/COEFF_AUTO.ts — keep in sync.

All VND amounts. 1 USD ≈ 25,000 VND (2024 rate).
"""

# ─── Base rates ──────────────────────────────────────────────────────────────
# frequency: expected claims/vehicle/year
# severity:  expected cost per claim (VND)
# Source: Vietnam Insurance Registry 2024 Table 3.1; ABeam SE Asia Motor 2023 p.47-49

BASE_RATES = {
    "motorcycle": {"frequency": 0.18, "severity": 70_000_000},
    "sedan":      {"frequency": 0.08, "severity": 87_500_000},
    "suv":        {"frequency": 0.07, "severity": 105_000_000},
    "truck":      {"frequency": 0.12, "severity": 145_000_000},
}

# ─── Vehicle age multipliers ─────────────────────────────────────────────────
# Brackets: new(0-2yr), young(3-5), mid(6-10), mature(11-15), old(16-20), vintage(21+)
# Source: ABeam SE Asia Motor Insurance Report 2023 Table 5.3

VEHICLE_AGE_MULTIPLIERS = {
    "motorcycle": {"new": 0.85, "young": 0.95, "mid": 1.00, "mature": 1.20, "old": 1.45, "vintage": 1.75},
    "sedan":      {"new": 0.88, "young": 0.95, "mid": 1.00, "mature": 1.18, "old": 1.40, "vintage": 1.65},
    "suv":        {"new": 0.87, "young": 0.94, "mid": 1.00, "mature": 1.16, "old": 1.38, "vintage": 1.60},
    "truck":      {"new": 0.90, "young": 0.96, "mid": 1.00, "mature": 1.22, "old": 1.50, "vintage": 1.85},
}

def get_vehicle_age_bracket(year_of_manufacture: int, reference_year: int = 2024) -> str:
    age = reference_year - year_of_manufacture
    if age <= 2:  return "new"
    if age <= 5:  return "young"
    if age <= 10: return "mid"
    if age <= 15: return "mature"
    if age <= 20: return "old"
    return "vintage"

# ─── Driver age multipliers ──────────────────────────────────────────────────
# U-shaped risk curve. Source: ABeam SE Asia 2023 Table 5.4; Statista Cambodia 2024

DRIVER_AGE_MULTIPLIERS = {
    "under25":   1.35,
    "age25to34": 1.00,
    "age35to44": 0.95,
    "age45to54": 1.05,
    "age55to64": 1.15,
    "over65":    1.30,
}

def get_driver_age_bracket(age: int) -> str:
    if age < 25: return "under25"
    if age < 35: return "age25to34"
    if age < 45: return "age35to44"
    if age < 55: return "age45to54"
    if age < 65: return "age55to64"
    return "over65"

# ─── Region multipliers ───────────────────────────────────────────────────────
# Source: Vietnam Insurance Registry 2024 Table 6.1; Statista Cambodia 2024; ABeam 2023

REGION_MULTIPLIERS = {
    "phnom_penh":    1.20,
    "siem_reap":     1.05,
    "battambang":    0.90,
    "sihanoukville": 1.15,
    "kampong_cham":  0.85,
    "rural_cambodia":0.70,
    "ho_chi_minh":   1.25,
    "hanoi":         1.20,
    "da_nang":       1.00,
    "can_tho":       0.88,
    "hai_phong":     0.95,
}

# ─── Accident history multipliers ────────────────────────────────────────────
# Source: ABeam SE Asia 2023 Table 5.6; DirectAsia Vietnam tariffs 2024

ACCIDENT_HISTORY_MULTIPLIERS = {
    False: 0.85,   # no prior claim → good-driver discount
    True:  1.45,   # prior claim → loading
}

# ─── Coverage type multipliers ────────────────────────────────────────────────
# Source: Vietnam Insurance Registry 2024; Cambodia MOLVT regs 2023

COVERAGE_MULTIPLIERS = {
    "ctpl_only": 0.60,
    "full":      1.00,
}

# ─── Loading factors ──────────────────────────────────────────────────────────
# Source: ABeam SE Asia 2023; Vietnam Insurance Registry 2024

LOADING_FACTORS = {
    "motorcycle": 0.32,
    "sedan":      0.25,
    "suv":        0.28,
    "truck":      0.35,
}

# ─── Tier multipliers ─────────────────────────────────────────────────────────
# Source: DirectAsia VN, Bao Viet, PTI tariffs 2024; ABeam 2023 appendix

TIER_MULTIPLIERS = {
    "basic":    0.70,
    "standard": 1.00,
    "premium":  1.40,
    "full":     2.00,
}

# ─── Deductible credits (VND) ─────────────────────────────────────────────────
# Source: Bao Viet published tariff schedule 2024; PTI Vietnam policy terms

DEDUCTIBLE_CREDITS = {
    "basic":    5_000_000,
    "standard": 2_000_000,
    "premium":  1_000_000,
    "full":     0,
}

# ─── Combined export ──────────────────────────────────────────────────────────
COEFF_AUTO = {
    "base": BASE_RATES,
    "multipliers": {
        "vehicleAge":      VEHICLE_AGE_MULTIPLIERS,
        "driverAge":       DRIVER_AGE_MULTIPLIERS,
        "region":          REGION_MULTIPLIERS,
        "accidentHistory": ACCIDENT_HISTORY_MULTIPLIERS,
        "coverage":        COVERAGE_MULTIPLIERS,
    },
    "loading":    LOADING_FACTORS,
    "tier":       TIER_MULTIPLIERS,
    "deductible": DEDUCTIBLE_CREDITS,
}
