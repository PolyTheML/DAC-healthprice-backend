"""
Actuarial Assumptions Module

All configurable rate tables, mortality tables, and risk factors for life insurance pricing.
Designed for IRC (Insurance Regulator of Cambodia) compliance and auditability.

These assumptions are versioned and recorded in every premium calculation's audit trail.
To change pricing behavior, modify this file and increment ASSUMPTION_VERSION.

Sources:
- Mortality: WHO South-East Asia Region life tables, adapted for Cambodia
- Risk factors: Standard actuarial practice (1994 GAM, RP-2000 with standard adjustments)
"""

from dataclasses import dataclass, field
from typing import Dict

# ============= VERSION =============
ASSUMPTION_VERSION = "v3.0-cambodia-2026-04-14"
"""
Increment this whenever assumptions change.
Format: vMAJOR.MINOR-YYYY-MM-DD
- MAJOR: Structural change (e.g., new risk factor table)
- MINOR: Parameter tuning (e.g., mortality rate adjustment)
- v3.0: Added Cambodia-specific occupational, endemic, and healthcare tier risk multipliers
"""

# ============= CAMBODIA CALIBRATION CONSTANT =============
CAMBODIA_MORTALITY_ADJ = 0.85
"""
Cambodia-observed mortality adjustment factor.
Applied to base mortality rates to reflect that observed claims experience
is ~15% below WHO South-East Asia Region baseline assumptions.
Calibrated from portfolio A/E analysis (portfolio/calibration.py).
"""


# ============= MORTALITY TABLES =============
@dataclass(frozen=True)
class MortalityAssumptions:
    """
    Age/gender-specific base mortality rates per 1,000 lives per year.

    q(x) = mortality rate for age x
    These are the foundation of the pure premium calculation.

    Source: WHO South-East Asia Region life tables (2020), adapted for Cambodia.
    Calibrated to 2019 demographic data.

    Construction:
    - Grouped by 10-year age bands for simplicity
    - Gender-differentiated per actuarial tables
    - Reflects post-pandemic mortality assumptions (2023+)
    """

    base_rate_male: Dict[str, float] = field(default_factory=lambda: {
        "18-24": 0.80,    # Young adult, low risk
        "25-34": 1.10,
        "35-44": 2.20,
        "45-54": 4.80,    # Mortality doubles at 45
        "55-64": 10.50,   # Significant increase
        "65+": 22.00,     # High risk
    })
    """Male mortality rates (per 1,000 per year). Used to calculate q(x) base."""

    base_rate_female: Dict[str, float] = field(default_factory=lambda: {
        "18-24": 0.50,    # 38% lower than males
        "25-34": 0.70,
        "35-44": 1.40,    # 36% lower than males
        "45-54": 3.20,    # 33% lower than males
        "55-64": 7.80,    # 26% lower than males
        "65+": 17.50,     # 20% lower than males
    })
    """Female mortality rates (per 1,000 per year). ~20-38% lower than males."""


# ============= RISK FACTOR MULTIPLIERS =============
@dataclass(frozen=True)
class RiskFactorMultipliers:
    """
    Multiplicative adjustments applied to the base mortality rate.

    If a person has multiple risk factors, they combine additively
    (see calculate_mortality_ratio() for the formula).

    Philosophy: Each multiplier represents the elevated mortality risk
    from that factor. For example, smoking increases mortality by 100%.
    """

    # Lifestyle factors
    smoking: float = 2.00              # +100% mortality risk (standard actuarial)
    alcohol_heavy: float = 1.25        # +25% for heavy alcohol use

    # BMI categories (per WHO/CDC standards)
    bmi_underweight: float = 1.20      # BMI < 18.5 (+20%)
    bmi_overweight: float = 1.15       # BMI 25-29.9 (+15%)
    bmi_obese_1: float = 1.35          # BMI 30-34.9 (+35%)
    bmi_obese_2: float = 1.60          # BMI 35+ (+60%)

    # Blood pressure (JNC-8 guidelines)
    bp_elevated: float = 1.10          # SBP 120-129, DBP < 80 (+10%)
    bp_stage1: float = 1.25            # SBP 130-139 or DBP 80-89 (+25%)
    bp_stage2: float = 1.50            # SBP ≥ 140 or DBP ≥ 90 (+50%)

    # Medical conditions
    diabetes: float = 1.40             # +40% (Type 2; Type 1 higher in practice)
    hypertension: float = 1.25         # +25% (if not already captured by BP staging)
    hyperlipidemia: float = 1.20       # +20% (high cholesterol)
    family_history_chd: float = 1.30   # +30% (coronary heart disease in 1st degree relatives)

    # Notes
    # - Smoking is the highest single factor
    # - Multiple conditions compound additively, not multiplicatively
    # - Blood pressure staging may overlap with hypertension diagnosis

    @classmethod
    def from_calibration(cls, overrides: dict) -> "RiskFactorMultipliers":
        """
        Create a calibrated RiskFactorMultipliers by applying proposed overrides.

        Args:
            overrides: dict mapping factor name → proposed multiplier value.
                       Only keys present are overridden; others keep current defaults.

        Example:
            calibrated = RiskFactorMultipliers.from_calibration({"smoking": 1.70, "diabetes": 1.35})
        """
        defaults = cls()
        return cls(
            smoking=overrides.get("smoking", defaults.smoking),
            alcohol_heavy=overrides.get("alcohol_heavy", defaults.alcohol_heavy),
            bmi_underweight=overrides.get("bmi_underweight", defaults.bmi_underweight),
            bmi_overweight=overrides.get("bmi_overweight", defaults.bmi_overweight),
            bmi_obese_1=overrides.get("bmi_obese_1", defaults.bmi_obese_1),
            bmi_obese_2=overrides.get("bmi_obese_2", defaults.bmi_obese_2),
            bp_elevated=overrides.get("bp_elevated", defaults.bp_elevated),
            bp_stage1=overrides.get("bp_stage1", defaults.bp_stage1),
            bp_stage2=overrides.get("bp_stage2", defaults.bp_stage2),
            diabetes=overrides.get("diabetes", defaults.diabetes),
            hypertension=overrides.get("hypertension", defaults.hypertension),
            hyperlipidemia=overrides.get("hyperlipidemia", defaults.hyperlipidemia),
            family_history_chd=overrides.get("family_history_chd", defaults.family_history_chd),
        )


# ============= LOADING FACTORS =============
@dataclass(frozen=True)
class LoadingFactors:
    """
    Breakdown of profit and cost loadings as percentage of pure premium.

    Gross Premium = Pure Premium × (1 + Total Loading)
    Total Loading = expense_ratio + commission_ratio + profit_margin + contingency

    Industry benchmarks:
    - Expense ratio: 10-15% (admin, underwriting, claims processing)
    - Commission: 8-12% (agent/broker compensation)
    - Profit margin: 3-7% (ROE target)
    - Contingency: 3-5% (catastrophe buffer, reserve for adverse claims experience)

    IRC reporting requirement: All four components must be disclosed.
    """

    expense_ratio: float = 0.12         # 12% — administration, underwriting, claims cost
    commission_ratio: float = 0.10      # 10% — agent commission (standard Cambodia rate)
    profit_margin: float = 0.05         # 5%  — target return on equity
    contingency: float = 0.05           # 5%  — catastrophe/adverse experience buffer

    @property
    def total_loading(self) -> float:
        """Total loading multiplicative factor.

        E.g., 0.12 + 0.10 + 0.05 + 0.05 = 0.32 → multiply by 1.32
        """
        return 1.0 + self.expense_ratio + self.commission_ratio + self.profit_margin + self.contingency


# ============= RISK TIER THRESHOLDS =============
@dataclass(frozen=True)
class RiskTierThresholds:
    """
    Mortality ratio thresholds for underwriting risk classification.

    Risk Tier = f(Mortality Ratio)
    Mortality Ratio = 1.0 (standard) + sum of (multiplier - 1.0) per risk factor

    Example:
    - Standard 30yo male, no risk factors: MR = 1.00 → LOW
    - 55yo smoker, Stage 2 BP: MR ≈ 1.00 + (2.00-1.00) + (1.50-1.00) = 2.50 → MEDIUM
    - 65yo smoker, diabetic, Stage 2 BP: MR ≈ 4.40 → DECLINE
    """

    low_max: float = 1.50              # Mortality Ratio ≤ 1.50 (≤50% above standard) → LOW
    medium_max: float = 2.50           # MR ≤ 2.50 (≤150% above standard) → MEDIUM
    high_max: float = 4.00             # MR ≤ 4.00 (≤300% above standard) → HIGH
    # MR > 4.00 → DECLINE (uninsurable at standard rates)


# ============= CAMBODIA-SPECIFIC OCCUPATIONAL MULTIPLIERS =============
@dataclass(frozen=True)
class CambodiaOccupationalMultipliers:
    """
    Occupational mortality surcharges for Cambodian labor market (IRC 2026).

    Applied as additive adjustments to base mortality ratio:
    ratio += (multiplier - 1.0)

    Cambodia has high road trauma mortality due to motorbike prevalence,
    and occupational hazards vary significantly by sector.
    """
    motorbike_courier: float = 1.45     # +45% (courier/delivery jobs; high daily exposure)
    motorbike_daily: float = 1.25       # +25% (daily motorbike commuting)
    motorbike_occasional: float = 1.10  # +10% (occasional motorbike use)
    construction: float = 1.35          # +35% (falls, equipment, heat exposure)
    manual_labor: float = 1.20          # +20% (general manual labor)
    healthcare: float = 1.05            # +5% (infection exposure risk)
    retail_service: float = 1.05        # +5% (service sector)
    office_desk: float = 1.00           # baseline (sedentary, lowest risk)
    retired: float = 0.95               # -5% (retired, lower exposure risk)
    unknown: float = 1.00               # baseline (no data)


# ============= CAMBODIA-SPECIFIC ENDEMIC DISEASE MULTIPLIERS =============
@dataclass(frozen=True)
class CambodiaEndemicMultipliers:
    """
    Provincial endemic disease mortality multipliers (Dengue/Malaria/TB).

    Based on:
    - WHO disease surveillance data
    - CDC/Gavi vaccination coverage
    - Historical claims analysis per province

    Applied as additive adjustments to base mortality ratio.
    Urban provinces (Phnom Penh, Siem Reap) have lower endemic risk.
    Rural/forested provinces (Mondulkiri, Ratanakiri) have higher risk.
    """
    phnom_penh: float = 1.00            # Urban baseline (dengue/malaria risk low)
    siem_reap: float = 1.05             # +5% (tourist area, dengue exposure)
    sihanoukville: float = 1.08         # +8% (coastal, warm, dengue)
    battambang: float = 1.05            # +5% (north-west, moderate risk)
    kampong_cham: float = 1.07          # +7% (east-central, moderate-high)
    kampong_speu: float = 1.06          # +6%
    kandal: float = 1.03                # +3% (peri-urban, low risk)
    kratie: float = 1.15                # +15% (forested; high malaria/dengue)
    mondulkiri: float = 1.30            # +30% (forested; high malaria/dengue belt)
    ratanakiri: float = 1.28            # +28% (similar to Mondulkiri, forested)
    preah_vihear: float = 1.18          # +18% (forested north)
    kampong_thom: float = 1.08          # +8%
    takeo: float = 1.04                 # +4%
    pursat: float = 1.07                # +7%
    rural_default: float = 1.12         # Default for unrecognized rural provinces


# ============= CAMBODIA-SPECIFIC HEALTHCARE TIER DISCOUNT =============
@dataclass(frozen=True)
class CambodiaHealthcareTierDiscount:
    """
    Premium reliability discount/surcharge based on hospital tier where
    the medical examination was conducted.

    Medical exam reliability affects confidence in health findings.
    A TierA exam (major hospital) is more trustworthy → lower chance of missed findings.
    A local clinic exam carries higher uncertainty → conservative surcharge.

    Applied as multiplicative factor to gross premium:
    adjusted_premium = gross_premium * tier_discount
    """
    tier_a: float = 0.97         # -3% premium (high-confidence exam, major hospital)
    tier_b: float = 1.00         # no change (regional hospital)
    clinic: float = 1.05         # +5% (lower facility reliability; flag for human review)
    unknown: float = 1.03        # +3% (unknown facility → conservative)


# ============= GLOBAL ASSUMPTIONS DICT =============
ASSUMPTIONS = {
    "mortality": MortalityAssumptions(),
    "risk_factors": RiskFactorMultipliers(),
    "loading": LoadingFactors(),
    "tiers": RiskTierThresholds(),
    "cambodia_occupational": CambodiaOccupationalMultipliers(),
    "cambodia_endemic": CambodiaEndemicMultipliers(),
    "cambodia_healthcare_tier": CambodiaHealthcareTierDiscount(),
    "cambodia_mortality_adj": CAMBODIA_MORTALITY_ADJ,
    "version": ASSUMPTION_VERSION,
}
"""
Master assumptions dictionary. Passed to all calculator functions.
Enables scenario testing: swap out different assumption sets for sensitivity analysis.

v3.0 additions:
- cambodia_occupational: Occupational risk multipliers for Cambodia labor market
- cambodia_endemic: Provincial endemic disease risk multipliers
- cambodia_healthcare_tier: Medical exam facility reliability discounts
- cambodia_mortality_adj: 0.85 factor reflecting observed vs. expected mortality in Cambodia
"""
