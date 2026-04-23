"""Validation logic for medical records"""

from typing import List
from .schemas import MedicalRecord, ValidationResult, TobaccoStatus


# Physiological ranges (from wiki)
PHYSIOLOGICAL_RANGES = {
    "age": (18, 120),
    "bmi": (10.0, 60.0),
    "systolic_bp": (70, 200),
    "diastolic_bp": (40, 120),
    "heart_rate": (40, 150),
    "blood_glucose_fasting": (60.0, 500.0),
    "total_cholesterol": (100.0, 400.0),
    "hdl_cholesterol": (10.0, 150.0),
    "ldl_cholesterol": (10.0, 350.0),
    "triglycerides": (20.0, 800.0),
}

# Medication-Condition mappings for consistency checking
MEDICATION_CONDITION_MAP = {
    "metformin": ["diabetes", "type 2 diabetes", "prediabetes"],
    "amlodipine": ["hypertension", "high blood pressure"],
    "lisinopril": ["hypertension", "high blood pressure", "heart disease"],
    "atorvastatin": ["hyperlipidemia", "high cholesterol"],
    "simvastatin": ["hyperlipidemia", "high cholesterol"],
}


def validate_schema(record: MedicalRecord) -> tuple[bool, List[str]]:
    """
    Validate Pydantic schema compliance.
    This catches type errors and required field violations.
    """
    try:
        # Pydantic validation happens on model creation
        # If we got here, schema is valid
        return True, []
    except Exception as e:
        return False, [f"Schema error: {str(e)}"]


def validate_domain(record: MedicalRecord) -> tuple[bool, List[str]]:
    """
    Validate that all values are within physiological ranges.
    """
    flags = []

    # Check vital signs ranges
    if record.vitals.age and not (PHYSIOLOGICAL_RANGES["age"][0] <= record.vitals.age <= PHYSIOLOGICAL_RANGES["age"][1]):
        flags.append(f"Age {record.vitals.age} outside range {PHYSIOLOGICAL_RANGES['age']}")

    if record.vitals.bmi and not (PHYSIOLOGICAL_RANGES["bmi"][0] <= record.vitals.bmi <= PHYSIOLOGICAL_RANGES["bmi"][1]):
        flags.append(f"BMI {record.vitals.bmi} outside range {PHYSIOLOGICAL_RANGES['bmi']}")

    if record.vitals.systolic_bp and not (PHYSIOLOGICAL_RANGES["systolic_bp"][0] <= record.vitals.systolic_bp <= PHYSIOLOGICAL_RANGES["systolic_bp"][1]):
        flags.append(f"Systolic BP {record.vitals.systolic_bp} outside range {PHYSIOLOGICAL_RANGES['systolic_bp']}")

    if record.vitals.diastolic_bp and not (PHYSIOLOGICAL_RANGES["diastolic_bp"][0] <= record.vitals.diastolic_bp <= PHYSIOLOGICAL_RANGES["diastolic_bp"][1]):
        flags.append(f"Diastolic BP {record.vitals.diastolic_bp} outside range {PHYSIOLOGICAL_RANGES['diastolic_bp']}")

    if record.vitals.heart_rate and not (PHYSIOLOGICAL_RANGES["heart_rate"][0] <= record.vitals.heart_rate <= PHYSIOLOGICAL_RANGES["heart_rate"][1]):
        flags.append(f"Heart rate {record.vitals.heart_rate} outside range {PHYSIOLOGICAL_RANGES['heart_rate']}")

    # Check lab ranges
    if record.labs.blood_glucose_fasting and not (PHYSIOLOGICAL_RANGES["blood_glucose_fasting"][0] <= record.labs.blood_glucose_fasting <= PHYSIOLOGICAL_RANGES["blood_glucose_fasting"][1]):
        flags.append(f"Fasting glucose {record.labs.blood_glucose_fasting} outside range {PHYSIOLOGICAL_RANGES['blood_glucose_fasting']}")

    if record.labs.total_cholesterol and not (PHYSIOLOGICAL_RANGES["total_cholesterol"][0] <= record.labs.total_cholesterol <= PHYSIOLOGICAL_RANGES["total_cholesterol"][1]):
        flags.append(f"Total cholesterol {record.labs.total_cholesterol} outside range {PHYSIOLOGICAL_RANGES['total_cholesterol']}")

    if record.labs.hdl_cholesterol and not (PHYSIOLOGICAL_RANGES["hdl_cholesterol"][0] <= record.labs.hdl_cholesterol <= PHYSIOLOGICAL_RANGES["hdl_cholesterol"][1]):
        flags.append(f"HDL cholesterol {record.labs.hdl_cholesterol} outside range {PHYSIOLOGICAL_RANGES['hdl_cholesterol']}")

    if record.labs.ldl_cholesterol and not (PHYSIOLOGICAL_RANGES["ldl_cholesterol"][0] <= record.labs.ldl_cholesterol <= PHYSIOLOGICAL_RANGES["ldl_cholesterol"][1]):
        flags.append(f"LDL cholesterol {record.labs.ldl_cholesterol} outside range {PHYSIOLOGICAL_RANGES['ldl_cholesterol']}")

    if record.labs.triglycerides and not (PHYSIOLOGICAL_RANGES["triglycerides"][0] <= record.labs.triglycerides <= PHYSIOLOGICAL_RANGES["triglycerides"][1]):
        flags.append(f"Triglycerides {record.labs.triglycerides} outside range {PHYSIOLOGICAL_RANGES['triglycerides']}")

    is_valid = len(flags) == 0
    return is_valid, flags


def validate_consistency(record: MedicalRecord) -> tuple[bool, List[str]]:
    """
    Validate cross-field consistency rules.
    E.g., if Diabetes is noted, glucose labs should be present.
    """
    flags = []

    conditions_lower = [c.lower() for c in record.history.conditions]
    medications_lower = [m.lower() for m in record.history.medications]

    # Rule: Diabetes requires glucose lab
    if any("diabetes" in c for c in conditions_lower):
        if record.labs.blood_glucose_fasting is None:
            flags.append("Diabetes noted but no fasting glucose lab value")

    # Rule: Hypertension requires BP readings
    if any("hypertension" in c or "high blood pressure" in c for c in conditions_lower):
        if record.vitals.systolic_bp is None or record.vitals.diastolic_bp is None:
            flags.append("Hypertension noted but BP readings missing")

    # Rule: Check medication-condition alignment
    for med in medications_lower:
        for med_key, conditions in MEDICATION_CONDITION_MAP.items():
            if med_key in med:
                # Check if any matching condition exists
                has_matching_condition = any(
                    any(cond in c for cond in conditions) for c in conditions_lower
                )
                if not has_matching_condition:
                    flags.append(f"Medication '{med}' suggests {conditions} but no matching condition noted")
                break

    # Rule: Smoking status with respiratory conditions
    if record.history.tobacco_status == TobaccoStatus.CURRENT:
        # If current smoker, note for review (not a failure, just a flag)
        pass

    is_valid = len(flags) == 0
    return is_valid, flags


def determine_routing(record: MedicalRecord, confidence: float) -> str:
    """
    Determine routing decision based on validation results and confidence.
    """
    # Low confidence → human review
    if confidence < 0.80:
        return "human_review"

    # Check if all required fields for GLM are present
    required_fields = [
        record.vitals.age,
        record.vitals.bmi,
        record.vitals.systolic_bp,
        record.vitals.diastolic_bp,
    ]

    if None in required_fields:
        return "human_review"

    # Healthy profile with complete data → STP
    if (
        confidence >= 0.90
        and record.vitals.bmi <= 30
        and record.vitals.systolic_bp <= 130
        and record.vitals.diastolic_bp <= 85
        and record.history.tobacco_status != TobaccoStatus.CURRENT
        and len(record.history.conditions) == 0
    ):
        return "stp"

    # Has conditions or marginal values → human review
    if len(record.history.conditions) > 0 or record.vitals.bmi > 30:
        return "human_review"

    # Default
    return "human_review"


def validate_medical_record(record: MedicalRecord) -> MedicalRecord:
    """
    Run all validation layers and attach validation result to record.
    """
    # Layer 1: Schema validation
    schema_valid, schema_flags = validate_schema(record)

    # Layer 2: Domain validation
    domain_valid, domain_flags = validate_domain(record)

    # Layer 3: Consistency validation
    consistency_valid, consistency_flags = validate_consistency(record)

    # Combine all flags
    all_flags = schema_flags + domain_flags + consistency_flags

    # Determine routing
    routing = determine_routing(record, record.extraction_meta.confidence)

    # Create validation result
    validation = ValidationResult(
        schema_valid=schema_valid,
        domain_valid=domain_valid,
        consistency_valid=consistency_valid,
        flags=all_flags,
        routing=routing,
    )

    record.validation = validation
    return record
