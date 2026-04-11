"""
Health Insurance Pricing Bridge

Maps ExtractedMedicalData (life insurance PDF intake) to health insurance GLM quote.

This closes the loop between:
  PDF extraction : medical_reader/nodes/intake.py   → ExtractedMedicalData
  Health pricing : app/pricing_engine/health_pricing.py → HealthGLMResult

Design decisions:
  - Extracted fields are mapped directly wherever schemas overlap.
  - Fields absent from medical PDFs (occupation, diet, etc.) receive conservative
    clinical defaults and are flagged in `inferred_fields`.
  - Medication count is used as a proxy for stress level — a recognised actuarial
    heuristic when lifestyle questionnaire data is unavailable.
  - `pricing_confidence` penalises the quote when many fields were inferred.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Resolve project root so imports work regardless of cwd
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from medical_reader.state import ExtractedMedicalData
from app.data.health_features import MedicalProfile
from app.pricing_engine.health_pricing import compute_health_glm_price


# ── Field mapping tables ──────────────────────────────────────────────────────

# medical_reader alcohol schema → MedicalProfile alcohol schema
_ALCOHOL_MAP: Dict[Optional[str], str] = {
    None:         "Never",
    "None":       "Never",
    "Never":      "Never",
    "Moderate":   "Occasional",
    "Occasional": "Occasional",
    "Regular":    "Regular",
    "Heavy":      "Heavy",
}

# ExtractedMedicalData boolean flags → human-readable condition names
_CONDITION_FLAGS: Dict[str, str] = {
    "diabetes":         "Diabetes",
    "hypertension":     "Hypertension",
    "hyperlipidemia":   "High Cholesterol",
}

# Number of extractable fields used to compute pricing_confidence
_EXTRACTABLE_FIELD_COUNT = len(_CONDITION_FLAGS) + 5  # age, gender, smoker, alcohol, bmi + conditions


# ── Main bridge function ──────────────────────────────────────────────────────

def bridge_extracted_to_health_quote(
    extracted: ExtractedMedicalData,
    country: str = "cambodia",
    region: str = "Phnom Penh",
    ipd_tier: str = "Silver",
    coverage_types: Optional[List[str]] = None,
    face_amount: float = 50_000.0,
    policy_term_years: int = 1,
) -> Dict[str, Any]:
    """
    Convert ExtractedMedicalData → health insurance premium quote.

    Args:
        extracted: Structured data produced by the intake node
        country: Insurance country (cambodia | vietnam)
        region: Region within country
        ipd_tier: IPD coverage tier (Bronze | Silver | Gold | Platinum)
        coverage_types: Coverage types to include (ipd | opd | dental | maternity)
        face_amount: Annual coverage limit in USD
        policy_term_years: Policy term in years

    Returns:
        dict with keys:
          profile          — the MedicalProfile used for pricing
          quote            — HealthGLMResult fields
          pricing_confidence — 0.0-1.0; lower when many fields were defaulted
          inferred_fields  — list of fields that used defaults (for audit trail)
          mapping_notes    — human-readable mapping decisions (one per field)
    """
    if coverage_types is None:
        coverage_types = ["ipd"]

    mapping_notes: List[str] = []
    inferred_fields: List[str] = []
    extracted_count = 0

    # ── Age ──────────────────────────────────────────────────────────────────
    if extracted.age is not None:
        age = extracted.age
        conf = extracted.confidence_scores.get("age", 0.0)
        mapping_notes.append(f"age={age} (extracted, conf={conf:.2f})")
        extracted_count += 1
    else:
        age = 40
        inferred_fields.append("age")
        mapping_notes.append("age=40 (default — not found in document)")

    # ── Gender ───────────────────────────────────────────────────────────────
    if extracted.gender:
        gender = "Female" if extracted.gender.upper() in ("F", "FEMALE") else "Male"
        mapping_notes.append(f"gender={gender} (extracted)")
        extracted_count += 1
    else:
        gender = "Male"
        inferred_fields.append("gender")
        mapping_notes.append("gender=Male (default)")

    # ── Smoking ──────────────────────────────────────────────────────────────
    if extracted.smoker is not None:
        smoking_status = "Current" if extracted.smoker else "Never"
        conf = extracted.confidence_scores.get("smoker", 0.0)
        mapping_notes.append(f"smoking_status={smoking_status} (extracted, conf={conf:.2f})")
        extracted_count += 1
    else:
        smoking_status = "Never"
        inferred_fields.append("smoking_status")
        mapping_notes.append("smoking_status=Never (default — not in document)")

    # ── Alcohol ──────────────────────────────────────────────────────────────
    alcohol_use = _ALCOHOL_MAP.get(extracted.alcohol_use, "Never")
    if extracted.alcohol_use:
        mapping_notes.append(f"alcohol_use={alcohol_use} (extracted)")
        extracted_count += 1
    else:
        inferred_fields.append("alcohol_use")
        mapping_notes.append("alcohol_use=Never (default)")

    # ── BMI (direct passthrough) ──────────────────────────────────────────────
    if extracted.bmi is not None:
        mapping_notes.append(f"bmi={extracted.bmi:.1f} (extracted)")
        extracted_count += 1
    else:
        mapping_notes.append("bmi=None (not extracted — engine will skip BMI adjustment)")

    # ── Pre-existing conditions ───────────────────────────────────────────────
    pre_existing: List[str] = []
    for flag, label in _CONDITION_FLAGS.items():
        if getattr(extracted, flag, False):
            pre_existing.append(label)
            extracted_count += 1
    if pre_existing:
        mapping_notes.append(f"pre_existing_conditions={pre_existing} (extracted)")
    else:
        mapping_notes.append("pre_existing_conditions=[] (none found in document)")

    # ── Family history ────────────────────────────────────────────────────────
    family_history: List[str] = []
    if extracted.family_history_chd:
        family_history.append("Coronary Heart Disease")
        mapping_notes.append("family_history: CHD (extracted)")
    else:
        mapping_notes.append("family_history=[] (none found)")

    # ── Stress level inferred from medication count ───────────────────────────
    med_count = len(extracted.medications) if extracted.medications else 0
    if med_count >= 4:
        stress_level = "High"
        mapping_notes.append(f"stress_level=High (inferred from {med_count} medications)")
    elif med_count >= 2:
        stress_level = "Moderate"
        mapping_notes.append(f"stress_level=Moderate (inferred from {med_count} medications)")
    else:
        stress_level = "Low"
        inferred_fields.append("stress_level")
        mapping_notes.append(f"stress_level=Low (default; {med_count} medications found)")

    # ── Lifestyle fields unavailable in medical PDFs → conservative defaults ──
    exercise_frequency = "Moderate"
    inferred_fields.append("exercise_frequency")
    mapping_notes.append("exercise_frequency=Moderate (default — not in medical records)")

    occupation_type = "Office/Desk"
    inferred_fields.append("occupation_type")
    mapping_notes.append("occupation_type=Office/Desk (default — not in medical records)")

    diet_quality = "Balanced"
    inferred_fields.append("diet_quality")
    mapping_notes.append("diet_quality=Balanced (default — not in medical records)")

    sleep_hours = "Fair (5-7h)"
    inferred_fields.append("sleep_hours_per_night")
    mapping_notes.append("sleep_hours_per_night=Fair (default — not in medical records)")

    motorbike_use = "No"
    inferred_fields.append("motorbike_use")
    mapping_notes.append("motorbike_use=No (conservative default)")

    distance_to_hospital = 5.0
    inferred_fields.append("distance_to_hospital_km")
    mapping_notes.append("distance_to_hospital_km=5.0 (urban default)")

    # ── Build MedicalProfile ──────────────────────────────────────────────────
    profile = MedicalProfile(
        age=age,
        gender=gender,
        country=country,
        region=region,
        smoking_status=smoking_status,
        exercise_frequency=exercise_frequency,
        occupation_type=occupation_type,
        alcohol_use=alcohol_use,
        diet_quality=diet_quality,
        sleep_hours_per_night=sleep_hours,
        stress_level=stress_level,
        motorbike_use=motorbike_use,
        distance_to_hospital_km=distance_to_hospital,
        pre_existing_conditions=pre_existing,
        family_history=family_history,
        bmi=extracted.bmi,
        systolic_bp=extracted.blood_pressure_systolic,
        diastolic_bp=extracted.blood_pressure_diastolic,
        ipd_tier=ipd_tier,
        coverage_types=coverage_types,
        face_amount=face_amount,
        policy_term_years=policy_term_years,
    )

    # ── Run health GLM pricing ────────────────────────────────────────────────
    result = compute_health_glm_price(profile)

    # ── Pricing confidence: penalise when many fields were inferred ───────────
    pricing_confidence = round(
        max(0.30, extracted_count / _EXTRACTABLE_FIELD_COUNT), 2
    )

    return {
        "profile": {
            "age": profile.age,
            "gender": profile.gender,
            "country": profile.country,
            "region": profile.region,
            "smoking_status": profile.smoking_status,
            "pre_existing_conditions": profile.pre_existing_conditions,
            "family_history": profile.family_history,
            "bmi": profile.bmi,
            "systolic_bp": profile.systolic_bp,
            "diastolic_bp": profile.diastolic_bp,
            "ipd_tier": profile.ipd_tier,
            "coverage_types": profile.coverage_types,
            "face_amount": profile.face_amount,
        },
        "quote": {
            "base_mortality_rate": round(result.base_mortality_rate, 4),
            "mortality_ratio": round(result.mortality_ratio, 4),
            "risk_tier": result.risk_tier,
            "pure_annual_premium": round(result.pure_annual_premium, 2),
            "gross_annual_premium": round(result.gross_annual_premium, 2),
            "gross_monthly_premium": round(result.gross_monthly_premium, 2),
            "factor_breakdown": {k: round(v, 4) for k, v in result.factor_breakdown.items()},
            "assumption_version": result.assumption_version,
        },
        "pricing_confidence": pricing_confidence,
        "inferred_fields": inferred_fields,
        "mapping_notes": mapping_notes,
    }
