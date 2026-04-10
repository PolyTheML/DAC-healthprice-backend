"""
Health Insurance Pricing Lab — Feature Extraction

Single source of truth for health insurance feature engineering.
Converts medical profiles into numeric features for GLM and ML models.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class MedicalProfile:
    """Input profile for health insurance pricing."""

    # Applicant demographics
    age: int                           # 18-100
    gender: str                        # Male | Female | Other
    country: str                       # cambodia | vietnam
    region: str                        # Phnom Penh, Hanoi, etc.

    # Lifestyle factors
    smoking_status: str                # Never | Former | Current
    exercise_frequency: str            # Sedentary | Light | Moderate | Active
    occupation_type: str               # Office/Desk | Retail/Service | Healthcare | Manual Labor | Industrial/High-Risk | Retired
    alcohol_use: str                   # Never | Occasional | Regular | Heavy
    diet_quality: str                  # Healthy | Balanced | High Processed
    sleep_hours_per_night: str         # Good (7-9h) | Fair (5-7h) | Poor (<5h)
    stress_level: str                  # Low | Moderate | High

    # Transportation risk
    motorbike_use: str                 # No | Never | Occasional | Daily
    distance_to_hospital_km: float     # 0-50

    # Medical history
    pre_existing_conditions: List[str] # e.g., ["Hypertension", "Diabetes"]
    family_history: List[str]          # e.g., ["Father had heart disease"]

    # Clinical vitals (optional, may be extracted from PDF)
    age_range: Optional[str] = None    # Derived from age
    bmi: Optional[float] = None        # Body Mass Index
    systolic_bp: Optional[int] = None  # Systolic blood pressure
    diastolic_bp: Optional[int] = None # Diastolic blood pressure

    # Coverage preferences
    ipd_tier: str = "Silver"           # Bronze | Silver | Gold | Platinum (hospital coverage)
    coverage_types: List[str] = None   # ipd | opd | dental | maternity
    face_amount: float = 50000.0       # Annual coverage limit
    policy_term_years: int = 1

    def __post_init__(self):
        if self.coverage_types is None:
            self.coverage_types = ["ipd"]  # Default to inpatient
        if self.age_range is None:
            self.age_range = _get_age_bracket(self.age)


def _get_age_bracket(age: int) -> str:
    """Map age to bracket for risk scoring."""
    if age < 25:
        return "18-24"
    elif age < 35:
        return "25-34"
    elif age < 45:
        return "35-44"
    elif age < 55:
        return "45-54"
    elif age < 65:
        return "55-64"
    else:
        return "65+"


def _classify_bmi(bmi: Optional[float]) -> str:
    """Classify BMI using WHO standards."""
    if bmi is None:
        return "unknown"
    if bmi < 18.5:
        return "underweight"
    elif bmi < 25.0:
        return "normal"
    elif bmi < 30.0:
        return "overweight"
    elif bmi < 35.0:
        return "obese_class1"
    else:
        return "obese_class2"


def _classify_blood_pressure(systolic: Optional[int], diastolic: Optional[int]) -> str:
    """Classify BP using JNC-8 guidelines."""
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


@dataclass
class ExtractedHealthFeatures:
    """Flat numeric features for ML model."""

    # Demographics
    age: int
    gender_enc: int                    # 0=Male, 1=Female, 2=Other
    age_bracket: str
    region_code: int                   # 0-11 region encoding

    # Lifestyle (one-hot or numeric)
    smoking_current: int               # 1 if current smoker
    exercise_level_enc: int            # 0-3
    occupation_risk_enc: int           # 0-5
    alcohol_heavy: int                 # 1 if heavy drinker
    diet_processed: int                # 1 if high processed
    sleep_poor: int                    # 1 if poor sleep
    stress_high: int                   # 1 if high stress

    # Transportation risk
    motorbike_daily: int               # 1 if daily use
    distance_to_hospital: float        # km

    # Medical risk factors
    has_condition_htn: int             # 1 if hypertension
    has_condition_diabetes: int        # 1 if diabetes
    has_condition_heart: int           # 1 if heart disease
    has_condition_other: int           # 1 if other condition
    family_history_count: int          # number of known cases

    # Clinical indicators
    bmi_class: str                     # underweight | normal | overweight | obese*
    bp_classification: str             # normal | elevated | stage1 | stage2 | crisis | unknown

    # Coverage
    ipd_tier_enc: int                  # 0-3 (Bronze to Platinum)
    coverage_count: int                # 1-4 (how many riders)
    face_amount: float
    policy_term_years: int

    def to_list(self) -> list[float]:
        """Convert to feature vector for ML."""
        return [
            float(self.age),
            float(self.gender_enc),
            float(self.smoking_current),
            float(self.exercise_level_enc),
            float(self.occupation_risk_enc),
            float(self.alcohol_heavy),
            float(self.diet_processed),
            float(self.sleep_poor),
            float(self.stress_high),
            float(self.motorbike_daily),
            self.distance_to_hospital,
            float(self.has_condition_htn),
            float(self.has_condition_diabetes),
            float(self.has_condition_heart),
            float(self.has_condition_other),
            float(self.family_history_count),
            float(self.ipd_tier_enc),
            float(self.coverage_count),
            self.face_amount,
            float(self.policy_term_years),
        ]


def extract_health_features(profile: MedicalProfile) -> ExtractedHealthFeatures:
    """Convert MedicalProfile to ExtractedHealthFeatures for modeling."""

    # Gender encoding
    gender_map = {"Male": 0, "Female": 1, "Other": 2}
    gender_enc = gender_map.get(profile.gender, 0)

    # Exercise encoding
    exercise_map = {"Sedentary": 0, "Light": 1, "Moderate": 2, "Active": 3}
    exercise_enc = exercise_map.get(profile.exercise_frequency, 1)

    # Occupation risk encoding
    occ_map = {
        "Office/Desk": 0,
        "Retail/Service": 1,
        "Healthcare": 2,
        "Manual Labor": 3,
        "Industrial/High-Risk": 4,
        "Retired": 5
    }
    occ_enc = occ_map.get(profile.occupation_type, 0)

    # Region encoding (map to same regions as in main.py)
    region_codes = {
        "Phnom Penh": 0, "Siem Reap": 1, "Battambang": 2, "Sihanoukville": 3,
        "Kampong Cham": 4, "Rural Areas": 5, "Ho Chi Minh City": 6, "Hanoi": 7,
        "Da Nang": 8, "Can Tho": 9, "Hai Phong": 10
    }
    region_code = region_codes.get(profile.region, 5)

    # Tier encoding
    tier_map = {"Bronze": 0, "Silver": 1, "Gold": 2, "Platinum": 3}
    ipd_tier_enc = tier_map.get(profile.ipd_tier, 1)

    # Binary flags
    smoking_current = 1 if profile.smoking_status == "Current" else 0
    alcohol_heavy = 1 if profile.alcohol_use == "Heavy" else 0
    diet_processed = 1 if profile.diet_quality == "High Processed" else 0
    sleep_poor = 1 if "Poor" in profile.sleep_hours_per_night else 0
    stress_high = 1 if profile.stress_level == "High" else 0
    motorbike_daily = 1 if profile.motorbike_use == "Daily" else 0

    # Medical condition flags
    cond_lower = [c.lower() for c in profile.pre_existing_conditions]
    has_htn = 1 if any("hypertension" in c or "htn" in c for c in cond_lower) else 0
    has_diabetes = 1 if any("diabetes" in c for c in cond_lower) else 0
    has_heart = 1 if any("heart" in c or "chd" in c or "coronary" in c for c in cond_lower) else 0
    has_other = 1 if len(cond_lower) > sum([has_htn, has_diabetes, has_heart]) else 0

    # BMI and BP classification
    bmi_class = _classify_bmi(profile.bmi)
    bp_class = _classify_blood_pressure(profile.systolic_bp, profile.diastolic_bp)

    return ExtractedHealthFeatures(
        age=profile.age,
        gender_enc=gender_enc,
        age_bracket=profile.age_range,
        region_code=region_code,
        smoking_current=smoking_current,
        exercise_level_enc=exercise_enc,
        occupation_risk_enc=occ_enc,
        alcohol_heavy=alcohol_heavy,
        diet_processed=diet_processed,
        sleep_poor=sleep_poor,
        stress_high=stress_high,
        motorbike_daily=motorbike_daily,
        distance_to_hospital=profile.distance_to_hospital_km,
        has_condition_htn=has_htn,
        has_condition_diabetes=has_diabetes,
        has_condition_heart=has_heart,
        has_condition_other=has_other,
        family_history_count=len(profile.family_history),
        bmi_class=bmi_class,
        bp_classification=bp_class,
        ipd_tier_enc=ipd_tier_enc,
        coverage_count=len(profile.coverage_types),
        face_amount=profile.face_amount,
        policy_term_years=profile.policy_term_years,
    )
