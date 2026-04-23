"""
Pricing Calculator Module

Pure calculation functions for life insurance premium pricing.
No dependencies on LangGraph, state objects, or API layers.

Formula:
    Gross Premium = Face Amount × q(x) × Mortality Ratio × (1 + Total Loading)

Where:
    q(x) = age/gender-specific base mortality rate (per 1,000/year)
    Mortality Ratio = cumulative adjustment from risk factors
    Total Loading = expense + commission + profit + contingency ratios
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional
from .assumptions import MortalityAssumptions, RiskFactorMultipliers, LoadingFactors, RiskTierThresholds


# ============= DATA MODELS =============
@dataclass
class PremiumBreakdown:
    """
    Complete breakdown of a premium calculation.

    Returned by calculate_annual_premium() to provide full transparency.
    Suitable for API responses and audit trail recording.
    """

    # Input parameters
    face_amount: float                      # Coverage amount (USD)
    policy_term_years: int                  # Policy term length
    age: int
    gender: str

    # Actuarial components
    base_mortality_rate: float              # q(x) per 1,000 per year
    mortality_ratio: float                  # Cumulative risk adjustment (1.0 = standard)
    factor_breakdown: Dict[str, float]      # {factor_name: multiplier_applied}

    # Pure premium (before loadings)
    pure_annual_premium: float              # Face × q(x) × mortality_ratio

    # Loading breakdown
    expense_loading: float                  # Dollar amount for expenses
    commission_loading: float               # Dollar amount for commissions
    profit_loading: float                   # Dollar amount for profit
    contingency_loading: float              # Dollar amount for contingency
    total_loading_amount: float             # Sum of all loadings

    # Final premiums
    gross_annual_premium: float             # Final annual premium (pure + loadings)
    gross_monthly_premium: float            # Annual ÷ 12

    # Metadata
    assumption_version: str
    risk_tier: str                          # LOW/MEDIUM/HIGH/DECLINE


# ============= HELPER FUNCTIONS =============
def classify_blood_pressure(systolic: Optional[int], diastolic: Optional[int]) -> str:
    """
    Classify blood pressure using JNC-8 guidelines.

    Args:
        systolic: Systolic BP in mmHg
        diastolic: Diastolic BP in mmHg

    Returns:
        One of: "normal", "elevated", "stage1", "stage2", "crisis", "unknown"

    JNC-8 Categories:
    - Normal: < 120 systolic AND < 80 diastolic
    - Elevated: 120–129 systolic AND < 80 diastolic
    - Stage 1: 130–139 systolic OR 80–89 diastolic
    - Stage 2: ≥ 140 systolic OR ≥ 90 diastolic
    - Crisis (emergency): > 180 systolic OR > 120 diastolic
    """
    if systolic is None or diastolic is None:
        return "unknown"

    if systolic > 180 or diastolic > 120:
        return "crisis"
    elif systolic >= 140 or diastolic >= 90:
        return "stage2"
    elif systolic >= 130 or diastolic >= 80:
        return "stage1"
    elif systolic >= 120 and diastolic < 80:
        return "elevated"
    else:
        return "normal"


def classify_bmi(bmi: Optional[float]) -> str:
    """
    Classify BMI using WHO standards.

    Args:
        bmi: Body Mass Index

    Returns:
        One of: "underweight", "normal", "overweight", "obese1", "obese2", "unknown"
    """
    if bmi is None:
        return "unknown"
    if bmi < 18.5:
        return "underweight"
    elif bmi < 25.0:
        return "normal"
    elif bmi < 30.0:
        return "overweight"
    elif bmi < 35.0:
        return "obese1"
    else:
        return "obese2"


def get_base_mortality_rate(
    age: Optional[int],
    gender: Optional[str],
    assumptions: MortalityAssumptions,
) -> float:
    """
    Look up q(x) from mortality table.

    Args:
        age: Age in years
        gender: "M" or "F" (or None for unisex default)
        assumptions: MortalityAssumptions object

    Returns:
        Mortality rate per 1,000 per year
    """
    if age is None or age < 0 or age > 150:
        # Default: healthy 45yo male
        return assumptions.base_rate_male.get("45-54", 4.80)

    # Determine age band
    if age < 18:
        age_band = "18-24"
    elif age < 25:
        age_band = "18-24"
    elif age < 35:
        age_band = "25-34"
    elif age < 45:
        age_band = "35-44"
    elif age < 55:
        age_band = "45-54"
    elif age < 65:
        age_band = "55-64"
    else:
        age_band = "65+"

    # Select gender table
    if gender and gender.upper() == "F":
        rates = assumptions.base_rate_female
    else:
        rates = assumptions.base_rate_male

    return rates.get(age_band, 4.80)  # Default to 45-54 male if lookup fails


def calculate_mortality_ratio(
    age: Optional[int],
    gender: Optional[str],
    bmi: Optional[float],
    smoker: bool,
    alcohol_use: Optional[str],
    diabetes: bool,
    hypertension: bool,
    hyperlipidemia: bool,
    family_history_chd: bool,
    systolic: Optional[int],
    diastolic: Optional[int],
    assumptions: RiskFactorMultipliers,
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate cumulative mortality ratio from risk factors.

    Uses additive approach: MR = 1.0 + sum of (multiplier - 1.0) for each factor
    This avoids multiplicative compounding that would double-count risk.

    Args:
        age, gender, bmi, smoker, etc.: Medical data fields
        assumptions: RiskFactorMultipliers object

    Returns:
        (mortality_ratio, factor_breakdown)
        - mortality_ratio: Cumulative adjustment (1.0 = standard, 2.0 = +100%)
        - factor_breakdown: {factor_name: multiplier_applied} for audit trail
    """
    breakdown = {}
    ratio = 1.0

    # Smoking (highest single risk factor)
    if smoker:
        adjustment = assumptions.smoking - 1.0
        ratio += adjustment
        breakdown["smoking"] = assumptions.smoking

    # BMI classification
    bmi_class = classify_bmi(bmi)
    if bmi_class == "underweight":
        adjustment = assumptions.bmi_underweight - 1.0
        ratio += adjustment
        breakdown["bmi_underweight"] = assumptions.bmi_underweight
    elif bmi_class == "overweight":
        adjustment = assumptions.bmi_overweight - 1.0
        ratio += adjustment
        breakdown["bmi_overweight"] = assumptions.bmi_overweight
    elif bmi_class == "obese1":
        adjustment = assumptions.bmi_obese_1 - 1.0
        ratio += adjustment
        breakdown["bmi_obese_1"] = assumptions.bmi_obese_1
    elif bmi_class == "obese2":
        adjustment = assumptions.bmi_obese_2 - 1.0
        ratio += adjustment
        breakdown["bmi_obese_2"] = assumptions.bmi_obese_2

    # Blood pressure classification (takes precedence over hypertension flag)
    bp_class = classify_blood_pressure(systolic, diastolic)
    if bp_class == "elevated":
        adjustment = assumptions.bp_elevated - 1.0
        ratio += adjustment
        breakdown["bp_elevated"] = assumptions.bp_elevated
    elif bp_class == "stage1":
        adjustment = assumptions.bp_stage1 - 1.0
        ratio += adjustment
        breakdown["bp_stage1"] = assumptions.bp_stage1
    elif bp_class == "stage2":
        adjustment = assumptions.bp_stage2 - 1.0
        ratio += adjustment
        breakdown["bp_stage2"] = assumptions.bp_stage2
    elif bp_class == "crisis":
        # Very high BP: apply Stage 2 + extra factor
        adjustment = (assumptions.bp_stage2 - 1.0) + 0.10
        ratio += adjustment
        breakdown["bp_crisis"] = assumptions.bp_stage2 + 0.10
    elif hypertension and bp_class == "normal":
        # Hypertension diagnosed but current BP normal (controlled)
        adjustment = assumptions.hypertension - 1.0
        ratio += adjustment
        breakdown["hypertension_controlled"] = assumptions.hypertension

    # Medical conditions (not already captured by BP staging)
    if diabetes:
        adjustment = assumptions.diabetes - 1.0
        ratio += adjustment
        breakdown["diabetes"] = assumptions.diabetes

    if hyperlipidemia:
        adjustment = assumptions.hyperlipidemia - 1.0
        ratio += adjustment
        breakdown["hyperlipidemia"] = assumptions.hyperlipidemia

    if family_history_chd:
        adjustment = assumptions.family_history_chd - 1.0
        ratio += adjustment
        breakdown["family_history_chd"] = assumptions.family_history_chd

    # Alcohol (only if heavy)
    if alcohol_use and alcohol_use.lower() == "heavy":
        adjustment = assumptions.alcohol_heavy - 1.0
        ratio += adjustment
        breakdown["alcohol_heavy"] = assumptions.alcohol_heavy

    # Cap mortality ratio at reasonable maximum (prevents extreme outliers)
    # Capping at 5.0x (500% above standard) ensures declining rates are still insurable
    ratio = min(ratio, 5.0)

    return ratio, breakdown


def calculate_annual_premium(
    face_amount: float,
    policy_term_years: int,
    age: Optional[int],
    gender: Optional[str],
    bmi: Optional[float],
    smoker: bool,
    alcohol_use: Optional[str],
    diabetes: bool,
    hypertension: bool,
    hyperlipidemia: bool,
    family_history_chd: bool,
    systolic: Optional[int],
    diastolic: Optional[int],
    assumptions: Dict,
) -> PremiumBreakdown:
    """
    Calculate a complete premium breakdown.

    This is the main entry point for premium calculation.

    Formula:
        Pure Premium (annual) = Face Amount × [q(x) / 1000] × Mortality Ratio
        Gross Premium = Pure Premium × (1 + Total Loading)

    Args:
        face_amount: Coverage amount in USD
        policy_term_years: Policy term (1–40 years)
        age, gender, ...: Medical underwriting data
        assumptions: Dict with keys "mortality", "risk_factors", "loading", "tiers", "version"

    Returns:
        PremiumBreakdown with full calculation details
    """

    # Extract assumption objects
    mortality_assumptions = assumptions["mortality"]
    risk_factor_assumptions = assumptions["risk_factors"]
    loading_assumptions = assumptions["loading"]
    tier_assumptions = assumptions["tiers"]
    version = assumptions["version"]

    # Step 1: Get base mortality rate q(x)
    base_mortality_rate = get_base_mortality_rate(age, gender, mortality_assumptions)

    # Step 2: Calculate mortality ratio and factor breakdown
    mortality_ratio, factor_breakdown = calculate_mortality_ratio(
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
        assumptions=risk_factor_assumptions,
    )

    # Step 3: Calculate pure premium
    # Formula: Face Amount × [q(x) / 1000] × Mortality Ratio
    # Note: base_mortality_rate is per 1,000, so we divide by 1000
    annual_q_x = base_mortality_rate / 1000.0
    pure_annual_premium = face_amount * annual_q_x * mortality_ratio

    # Step 4: Calculate loading components (as percentages of pure premium)
    expense_loading = pure_annual_premium * loading_assumptions.expense_ratio
    commission_loading = pure_annual_premium * loading_assumptions.commission_ratio
    profit_loading = pure_annual_premium * loading_assumptions.profit_margin
    contingency_loading = pure_annual_premium * loading_assumptions.contingency
    total_loading_amount = expense_loading + commission_loading + profit_loading + contingency_loading

    # Step 5: Calculate gross premium
    gross_annual_premium = pure_annual_premium + total_loading_amount
    gross_monthly_premium = gross_annual_premium / 12.0

    # Step 6: Determine risk tier from mortality ratio
    if mortality_ratio <= tier_assumptions.low_max:
        risk_tier = "LOW"
    elif mortality_ratio <= tier_assumptions.medium_max:
        risk_tier = "MEDIUM"
    elif mortality_ratio <= tier_assumptions.high_max:
        risk_tier = "HIGH"
    else:
        risk_tier = "DECLINE"

    # Step 7: Assemble breakdown
    return PremiumBreakdown(
        face_amount=face_amount,
        policy_term_years=policy_term_years,
        age=age or 45,
        gender=gender or "U",
        base_mortality_rate=base_mortality_rate,
        mortality_ratio=mortality_ratio,
        factor_breakdown=factor_breakdown,
        pure_annual_premium=pure_annual_premium,
        expense_loading=expense_loading,
        commission_loading=commission_loading,
        profit_loading=profit_loading,
        contingency_loading=contingency_loading,
        total_loading_amount=total_loading_amount,
        gross_annual_premium=gross_annual_premium,
        gross_monthly_premium=gross_monthly_premium,
        assumption_version=version,
        risk_tier=risk_tier,
    )
