"""
Health Insurance Pricing Engine — GLM-based pricing

Converts medical profiles into health insurance premiums using:
1. Age-gender mortality tables (base rate)
2. Risk factor multipliers (smoking, conditions, etc.)
3. Loading factors (expense, commission, profit)
4. Tier adjustments (Bronze/Silver/Gold/Platinum)

Formula:
  Base Premium = Face Amount × [q(x) / 1000] × Mortality Ratio
  Loaded Premium = Base Premium × (1 + Total Loading)
  Final Premium = Loaded Premium × Tier Multiplier
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from app.data.health_features import MedicalProfile, ExtractedHealthFeatures, extract_health_features


# ═══════════════════════════════════════════════════════════════════════════
# MORTALITY TABLES & RISK FACTORS (COEFF equivalent for health)
# ═══════════════════════════════════════════════════════════════════════════

HEALTH_COEFF = {
    "version": "v1.0.0",
    "last_updated": "2026-04-10",

    # Base mortality rates per 1,000 per year (age/gender specific)
    "base_rate_male": {
        "18-24": 0.80,
        "25-34": 0.95,
        "35-44": 1.35,
        "45-54": 2.20,
        "55-64": 4.50,
        "65+": 10.00
    },
    "base_rate_female": {
        "18-24": 0.50,
        "25-34": 0.60,
        "35-44": 0.90,
        "45-54": 1.50,
        "55-64": 3.20,
        "65+": 7.50
    },

    # Risk multipliers (additive: MR = 1.0 + sum(multiplier - 1.0))
    "risk_multipliers": {
        "smoking_current": 1.50,           # +50% additional risk
        "smoking_former": 1.15,            # +15% (higher than never)
        "exercise_sedentary": 1.20,        # +20% for no exercise
        "alcohol_heavy": 1.35,             # +35% for heavy drinking
        "diet_high_processed": 1.12,       # +12% for poor diet
        "sleep_poor": 1.18,                # +18% for poor sleep
        "stress_high": 1.10,               # +10% for high stress
        "motorbike_daily": 1.40,           # +40% for daily motorbike use
        "distance_hospital_far": 1.15,     # +15% if >20km from hospital
        "condition_hypertension": 1.35,    # +35% if HTN diagnosed
        "condition_diabetes": 1.45,        # +45% if diabetes
        "condition_heart_disease": 1.80,   # +80% if heart disease
        "condition_cancer_remission": 1.60, # +60% even in remission
        "condition_copd": 1.55,            # +55% if lung disease
        "condition_kidney_disease": 1.50,  # +50% if kidney disease
        "condition_other": 0.95,           # most other conditions minor
        "family_history_per_case": 1.08,   # +8% per family case
        "bmi_underweight": 1.15,           # +15% (indicates poor health)
        "bmi_overweight": 1.12,            # +12% BMI 25-30
        "bmi_obese_class1": 1.25,          # +25% BMI 30-35
        "bmi_obese_class2": 1.45,          # +45% BMI >35
        "bp_elevated": 1.08,               # +8% (120-129 systolic)
        "bp_stage1": 1.20,                 # +20% (130-139 systolic)
        "bp_stage2": 1.35,                 # +35% (≥140 systolic)
        "bp_crisis": 2.00,                 # +100% (emergency BP)
        "occupation_manual_labor": 1.10,   # +10% for manual jobs
        "occupation_high_risk": 1.25,      # +25% for industrial
    },

    # Loading factors (as % of pure premium)
    "loading": {
        "expense_ratio": 0.15,             # 15% for claims handling, etc.
        "commission_ratio": 0.10,          # 10% agent commission
        "profit_margin": 0.20,             # 20% profit target
        "contingency": 0.05,               # 5% contingency reserve
        "total_loading_ratio": 0.50        # Total = 50% of pure
    },

    # Tier multipliers (apply to loaded premium)
    "tier_multipliers": {
        "Bronze": 0.70,                    # Basic coverage, lower premium
        "Silver": 1.00,                    # Standard (baseline)
        "Gold": 1.45,                      # Enhanced
        "Platinum": 2.10,                  # Premium all-inclusive
    },

    # Risk classification thresholds (based on mortality ratio)
    "risk_tiers": {
        "low_max": 1.20,                   # MR ≤ 1.20 = LOW
        "medium_max": 1.80,                # 1.20 < MR ≤ 1.80 = MEDIUM
        "high_max": 3.00,                  # 1.80 < MR ≤ 3.00 = HIGH
        # MR > 3.00 = DECLINE (uninsurable)
    },

    # Premium bounds
    "min_annual_premium": 1000,            # Floor annual premium
    "max_mortality_ratio": 5.00,           # Cap MR to avoid extreme pricing
}


@dataclass
class HealthGLMMultipliers:
    """Risk multipliers applied in health pricing."""
    smoking: float
    exercise: float
    alcohol: float
    diet: float
    sleep: float
    stress: float
    motorbike: float
    distance: float
    conditions: float
    family_history: float
    bmi: float
    blood_pressure: float
    occupation: float

    @property
    def combined(self) -> float:
        """Combine all multipliers (additive to avoid double-counting)."""
        # Additive: ratio = 1.0 + sum(mult - 1.0) for each factor
        ratio = 1.0
        for mult in [self.smoking, self.exercise, self.alcohol, self.diet,
                     self.sleep, self.stress, self.motorbike, self.distance,
                     self.conditions, self.family_history, self.bmi,
                     self.blood_pressure, self.occupation]:
            if mult > 1.0:
                ratio += (mult - 1.0)
        # Cap to avoid extreme outliers
        return min(ratio, HEALTH_COEFF["risk_tiers"]["high_max"] * 1.7)


@dataclass
class HealthGLMResult:
    """Complete GLM breakdown for health premium."""

    # Inputs (for audit)
    age: int
    gender: str
    ipd_tier: str
    coverage_types: list

    # Base rate (q(x) from mortality table)
    base_mortality_rate: float         # per 1,000 per year

    # Risk adjustment
    mortality_ratio: float             # Cumulative adjustment (1.0 = standard)
    factor_breakdown: Dict[str, float] # {factor: multiplier_applied}
    multipliers: HealthGLMMultipliers

    # Pure premium (before loading/tier)
    pure_annual_premium: float

    # Loading components
    expense_loading: float
    commission_loading: float
    profit_loading: float
    contingency_loading: float
    total_loading_amount: float

    # Final premiums
    loaded_premium: float
    tier_multiplier: float
    tiered_premium: float
    gross_annual_premium: float
    gross_monthly_premium: float

    # Risk classification
    risk_tier: str                     # LOW | MEDIUM | HIGH | DECLINE
    assumption_version: str


def get_base_mortality_rate(age: int, gender: str) -> float:
    """Look up q(x) from mortality table."""
    if age < 0 or age > 150:
        age = 45  # Default

    # Determine age band
    if age < 25:
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
    if gender.lower() == "female":
        rates = HEALTH_COEFF["base_rate_female"]
    else:
        rates = HEALTH_COEFF["base_rate_male"]

    return rates.get(age_band, 1.0)


def calculate_mortality_ratio(features: ExtractedHealthFeatures) -> tuple[float, Dict[str, float]]:
    """
    Calculate cumulative mortality ratio from all risk factors.

    Additive approach avoids double-counting:
    MR = 1.0 + sum(mult - 1.0) for each applied factor
    """
    breakdown = {}
    ratio = 1.0
    coeff = HEALTH_COEFF["risk_multipliers"]

    # Smoking
    if features.smoking_current:
        mult = coeff["smoking_current"]
    else:
        mult = 1.0  # Never or Former — assume already reflected in base rate
    breakdown["smoking"] = mult
    if mult > 1.0:
        ratio += (mult - 1.0)

    # Exercise
    if features.exercise_level_enc == 0:  # Sedentary
        mult = coeff["exercise_sedentary"]
        breakdown["exercise_sedentary"] = mult
        ratio += (mult - 1.0)

    # Alcohol
    if features.alcohol_heavy:
        mult = coeff["alcohol_heavy"]
        breakdown["alcohol_heavy"] = mult
        ratio += (mult - 1.0)

    # Diet
    if features.diet_processed:
        mult = coeff["diet_high_processed"]
        breakdown["diet_poor"] = mult
        ratio += (mult - 1.0)

    # Sleep
    if features.sleep_poor:
        mult = coeff["sleep_poor"]
        breakdown["sleep_poor"] = mult
        ratio += (mult - 1.0)

    # Stress
    if features.stress_high:
        mult = coeff["stress_high"]
        breakdown["stress_high"] = mult
        ratio += (mult - 1.0)

    # Motorbike
    if features.motorbike_daily:
        mult = coeff["motorbike_daily"]
        breakdown["motorbike_daily"] = mult
        ratio += (mult - 1.0)

    # Distance to hospital
    if features.distance_to_hospital > 20:
        mult = coeff["distance_hospital_far"]
        breakdown["distance_far"] = mult
        ratio += (mult - 1.0)

    # Medical conditions (add individually)
    conditions_applied = 0
    if features.has_condition_htn:
        mult = coeff["condition_hypertension"]
        breakdown["hypertension"] = mult
        ratio += (mult - 1.0)
        conditions_applied += 1

    if features.has_condition_diabetes:
        mult = coeff["condition_diabetes"]
        breakdown["diabetes"] = mult
        ratio += (mult - 1.0)
        conditions_applied += 1

    if features.has_condition_heart:
        mult = coeff["condition_heart_disease"]
        breakdown["heart_disease"] = mult
        ratio += (mult - 1.0)
        conditions_applied += 1

    if features.has_condition_other:
        mult = coeff["condition_other"]
        breakdown["other_condition"] = mult
        if mult > 1.0:
            ratio += (mult - 1.0)

    # Family history (per case)
    if features.family_history_count > 0:
        mult = coeff["family_history_per_case"] ** features.family_history_count
        breakdown["family_history"] = mult
        ratio += (mult - 1.0)

    # BMI
    if features.bmi_class == "underweight":
        mult = coeff["bmi_underweight"]
        breakdown["bmi_underweight"] = mult
        ratio += (mult - 1.0)
    elif features.bmi_class == "overweight":
        mult = coeff["bmi_overweight"]
        breakdown["bmi_overweight"] = mult
        ratio += (mult - 1.0)
    elif features.bmi_class == "obese_class1":
        mult = coeff["bmi_obese_class1"]
        breakdown["bmi_obese1"] = mult
        ratio += (mult - 1.0)
    elif features.bmi_class == "obese_class2":
        mult = coeff["bmi_obese_class2"]
        breakdown["bmi_obese2"] = mult
        ratio += (mult - 1.0)

    # Blood pressure
    if features.bp_classification == "crisis":
        mult = coeff["bp_crisis"]
        breakdown["bp_crisis"] = mult
        ratio += (mult - 1.0)
    elif features.bp_classification == "stage2":
        mult = coeff["bp_stage2"]
        breakdown["bp_stage2"] = mult
        ratio += (mult - 1.0)
    elif features.bp_classification == "stage1":
        mult = coeff["bp_stage1"]
        breakdown["bp_stage1"] = mult
        ratio += (mult - 1.0)
    elif features.bp_classification == "elevated":
        mult = coeff["bp_elevated"]
        breakdown["bp_elevated"] = mult
        ratio += (mult - 1.0)

    # Occupation
    if features.occupation_risk_enc == 4:  # Industrial/High-Risk
        mult = coeff["occupation_high_risk"]
        breakdown["occupation_high_risk"] = mult
        ratio += (mult - 1.0)
    elif features.occupation_risk_enc == 3:  # Manual Labor
        mult = coeff["occupation_manual_labor"]
        breakdown["occupation_manual"] = mult
        ratio += (mult - 1.0)

    # Cap at max ratio
    ratio = min(ratio, HEALTH_COEFF["risk_tiers"]["high_max"] * 1.7)

    return ratio, breakdown


def compute_health_glm_price(profile: MedicalProfile) -> HealthGLMResult:
    """
    Main pricing function: MedicalProfile → HealthGLMResult with full breakdown.
    """

    # Step 1: Extract features
    features = extract_health_features(profile)

    # Step 2: Get base mortality rate
    base_mortality_rate = get_base_mortality_rate(profile.age, profile.gender)

    # Step 3: Calculate mortality ratio and factors
    mortality_ratio, factor_breakdown = calculate_mortality_ratio(features)

    # Step 4: Calculate pure premium
    # Formula: Face Amount × [q(x) / 1000] × Mortality Ratio
    annual_q_x = base_mortality_rate / 1000.0
    pure_annual_premium = profile.face_amount * annual_q_x * mortality_ratio

    # Step 5: Calculate loading components
    loading = HEALTH_COEFF["loading"]
    expense = pure_annual_premium * loading["expense_ratio"]
    commission = pure_annual_premium * loading["commission_ratio"]
    profit = pure_annual_premium * loading["profit_margin"]
    contingency = pure_annual_premium * loading["contingency"]
    total_loading = expense + commission + profit + contingency

    # Step 6: Apply tier multiplier
    tier_mult = HEALTH_COEFF["tier_multipliers"].get(profile.ipd_tier, 1.0)
    loaded_premium = pure_annual_premium + total_loading
    tiered_premium = loaded_premium * tier_mult
    gross_annual = tiered_premium
    gross_monthly = gross_annual / 12.0

    # Floor and ceil
    gross_annual = max(gross_annual, HEALTH_COEFF["min_annual_premium"])

    # Step 7: Risk tier classification
    if mortality_ratio <= HEALTH_COEFF["risk_tiers"]["low_max"]:
        risk_tier = "LOW"
    elif mortality_ratio <= HEALTH_COEFF["risk_tiers"]["medium_max"]:
        risk_tier = "MEDIUM"
    elif mortality_ratio <= HEALTH_COEFF["risk_tiers"]["high_max"]:
        risk_tier = "HIGH"
    else:
        risk_tier = "DECLINE"

    # Build multipliers object
    multipliers = HealthGLMMultipliers(
        smoking=factor_breakdown.get("smoking", 1.0),
        exercise=factor_breakdown.get("exercise_sedentary", 1.0),
        alcohol=factor_breakdown.get("alcohol_heavy", 1.0),
        diet=factor_breakdown.get("diet_poor", 1.0),
        sleep=factor_breakdown.get("sleep_poor", 1.0),
        stress=factor_breakdown.get("stress_high", 1.0),
        motorbike=factor_breakdown.get("motorbike_daily", 1.0),
        distance=factor_breakdown.get("distance_far", 1.0),
        conditions=1.0,  # Combined in breakdown
        family_history=factor_breakdown.get("family_history", 1.0),
        bmi=factor_breakdown.get("bmi_overweight", factor_breakdown.get("bmi_obese1", 1.0)),
        blood_pressure=factor_breakdown.get("bp_stage2", factor_breakdown.get("bp_elevated", 1.0)),
        occupation=factor_breakdown.get("occupation_high_risk", factor_breakdown.get("occupation_manual", 1.0)),
    )

    return HealthGLMResult(
        age=profile.age,
        gender=profile.gender,
        ipd_tier=profile.ipd_tier,
        coverage_types=profile.coverage_types,
        base_mortality_rate=base_mortality_rate,
        mortality_ratio=mortality_ratio,
        factor_breakdown=factor_breakdown,
        multipliers=multipliers,
        pure_annual_premium=pure_annual_premium,
        expense_loading=expense,
        commission_loading=commission,
        profit_loading=profit,
        contingency_loading=contingency,
        total_loading_amount=total_loading,
        loaded_premium=loaded_premium,
        tier_multiplier=tier_mult,
        tiered_premium=tiered_premium,
        gross_annual_premium=gross_annual,
        gross_monthly_premium=gross_monthly,
        risk_tier=risk_tier,
        assumption_version=HEALTH_COEFF["version"],
    )
