"""
Health Insurance Pricing Lab — Validation

Validates medical profiles for health insurance pricing.
Checks demographic ranges, physiological bounds, and logical consistency.
"""


def validate_health_profile(profile_dict: dict) -> str:
    """
    Validate a health insurance profile.

    Returns: Error message (empty string if valid)
    """

    # Required fields
    required = ["age", "gender", "country", "region", "smoking_status",
                "exercise_frequency", "occupation_type", "alcohol_use",
                "diet_quality", "sleep_hours_per_night", "stress_level",
                "motorbike_use", "distance_to_hospital_km",
                "pre_existing_conditions", "family_history"]

    for field in required:
        if field not in profile_dict or profile_dict[field] is None:
            return f"Missing required field: {field}"

    # Age validation
    age = profile_dict.get("age")
    if not isinstance(age, int) or age < 18 or age > 100:
        return f"Age must be between 18 and 100, got {age}"

    # Gender validation
    valid_genders = ["Male", "Female", "Other"]
    if profile_dict["gender"] not in valid_genders:
        return f"Invalid gender: {profile_dict['gender']}"

    # Country validation
    valid_countries = ["cambodia", "vietnam"]
    if profile_dict["country"].lower() not in valid_countries:
        return f"Invalid country: {profile_dict['country']}"

    # Region validation
    valid_regions = {
        "cambodia": {"Phnom Penh", "Siem Reap", "Battambang", "Sihanoukville", "Kampong Cham", "Rural Areas"},
        "vietnam": {"Ho Chi Minh City", "Hanoi", "Da Nang", "Can Tho", "Hai Phong", "Rural Areas"}
    }
    country = profile_dict["country"].lower()
    if profile_dict["region"] not in valid_regions.get(country, set()):
        return f"Invalid region for {country}: {profile_dict['region']}"

    # Smoking validation
    valid_smoking = ["Never", "Former", "Current"]
    if profile_dict["smoking_status"] not in valid_smoking:
        return f"Invalid smoking_status: {profile_dict['smoking_status']}"

    # Exercise validation
    valid_exercise = ["Sedentary", "Light", "Moderate", "Active"]
    if profile_dict["exercise_frequency"] not in valid_exercise:
        return f"Invalid exercise_frequency: {profile_dict['exercise_frequency']}"

    # Occupation validation
    valid_occ = ["Office/Desk", "Retail/Service", "Healthcare", "Manual Labor", "Industrial/High-Risk", "Retired"]
    if profile_dict["occupation_type"] not in valid_occ:
        return f"Invalid occupation_type: {profile_dict['occupation_type']}"

    # Alcohol validation
    valid_alcohol = ["Never", "Occasional", "Regular", "Heavy"]
    if profile_dict["alcohol_use"] not in valid_alcohol:
        return f"Invalid alcohol_use: {profile_dict['alcohol_use']}"

    # Diet validation
    valid_diet = ["Healthy", "Balanced", "High Processed"]
    if profile_dict["diet_quality"] not in valid_diet:
        return f"Invalid diet_quality: {profile_dict['diet_quality']}"

    # Sleep validation
    valid_sleep = ["Good (7-9h)", "Fair (5-7h)", "Poor (<5h)"]
    if profile_dict["sleep_hours_per_night"] not in valid_sleep:
        return f"Invalid sleep_hours_per_night: {profile_dict['sleep_hours_per_night']}"

    # Stress validation
    valid_stress = ["Low", "Moderate", "High"]
    if profile_dict["stress_level"] not in valid_stress:
        return f"Invalid stress_level: {profile_dict['stress_level']}"

    # Motorbike validation
    valid_motorbike = ["No", "Never", "Occasional", "Daily"]
    if profile_dict["motorbike_use"] not in valid_motorbike:
        return f"Invalid motorbike_use: {profile_dict['motorbike_use']}"

    # Distance to hospital
    distance = profile_dict.get("distance_to_hospital_km")
    if not isinstance(distance, (int, float)) or distance < 0 or distance > 200:
        return f"Distance to hospital must be 0-200 km, got {distance}"

    # Pre-existing conditions (should be list)
    if not isinstance(profile_dict.get("pre_existing_conditions"), list):
        return "pre_existing_conditions must be a list"

    # Family history (should be list)
    if not isinstance(profile_dict.get("family_history"), list):
        return "family_history must be a list"

    # Optional clinical fields
    if "bmi" in profile_dict and profile_dict["bmi"] is not None:
        bmi = profile_dict["bmi"]
        if not isinstance(bmi, (int, float)) or bmi < 10 or bmi > 60:
            return f"BMI must be 10-60, got {bmi}"

    if "systolic_bp" in profile_dict and profile_dict["systolic_bp"] is not None:
        sbp = profile_dict["systolic_bp"]
        if not isinstance(sbp, int) or sbp < 70 or sbp > 200:
            return f"Systolic BP must be 70-200 mmHg, got {sbp}"

    if "diastolic_bp" in profile_dict and profile_dict["diastolic_bp"] is not None:
        dbp = profile_dict["diastolic_bp"]
        if not isinstance(dbp, int) or dbp < 40 or dbp > 120:
            return f"Diastolic BP must be 40-120 mmHg, got {dbp}"

    # IPD tier validation
    valid_tiers = ["Bronze", "Silver", "Gold", "Platinum"]
    if "ipd_tier" in profile_dict and profile_dict["ipd_tier"] not in valid_tiers:
        return f"Invalid ipd_tier: {profile_dict['ipd_tier']}"

    # Coverage types validation
    valid_coverage = ["ipd", "opd", "dental", "maternity"]
    if "coverage_types" in profile_dict and profile_dict["coverage_types"]:
        for cov in profile_dict["coverage_types"]:
            if cov not in valid_coverage:
                return f"Invalid coverage type: {cov}"

    # Face amount validation
    if "face_amount" in profile_dict:
        face = profile_dict["face_amount"]
        if not isinstance(face, (int, float)) or face < 10000 or face > 500000:
            return f"Face amount must be 10,000-500,000, got {face}"

    # Policy term validation
    if "policy_term_years" in profile_dict:
        term = profile_dict["policy_term_years"]
        if not isinstance(term, int) or term < 1 or term > 40:
            return f"Policy term must be 1-40 years, got {term}"

    return ""  # Valid


def validate_extracted_medical_data(extracted_data: dict) -> str:
    """
    Validate medical data extracted from PDF by our medical_reader.

    This is called after OCR extraction to ensure data quality.
    Returns: Error message (empty if valid)
    """

    required_fields = ["age", "smoking_status", "bmi"]

    for field in required_fields:
        if field not in extracted_data or extracted_data[field] is None:
            return f"Medical extraction missing required field: {field}"

    # Physiological range checks
    age = extracted_data.get("age")
    if not isinstance(age, int) or age < 18 or age > 100:
        return f"Extracted age out of range: {age}"

    bmi = extracted_data.get("bmi")
    if bmi is not None and (not isinstance(bmi, (int, float)) or bmi < 10 or bmi > 60):
        return f"Extracted BMI out of range: {bmi}"

    # Smoking validation
    smoking = extracted_data.get("smoking_status")
    valid_smoking = ["Never", "Former", "Current"]
    if smoking and smoking not in valid_smoking:
        return f"Invalid extracted smoking status: {smoking}"

    # Blood pressure checks
    systolic = extracted_data.get("systolic_bp")
    if systolic is not None and (not isinstance(systolic, int) or systolic < 70 or systolic > 200):
        return f"Extracted systolic BP out of range: {systolic}"

    diastolic = extracted_data.get("diastolic_bp")
    if diastolic is not None and (not isinstance(diastolic, int) or diastolic < 40 or diastolic > 120):
        return f"Extracted diastolic BP out of range: {diastolic}"

    return ""  # Valid
