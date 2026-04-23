"""
Review Node: Flag cases requiring human review with SHAP-style explanations.

Determines if a case needs human underwriter assessment based on:
- Extraction confidence
- Risk level
- Missing fields
- Errors during processing
- Cambodia-specific occupational and regional risks

Produces a reasoning_trace explaining each flagged risk factor with source location.
"""

from ..state import UnderwritingState, ReviewNotes, RiskLevel


def _build_reasoning_trace(state: UnderwritingState) -> str:
    """
    Build a SHAP-style AI explanation trace showing why each risk factor was flagged.

    Format:
    FLAGGED: [Factor] — [Details] (found in [source]) → [Impact] | confidence: [X%]
    APPROVED: [Statement]

    Args:
        state: UnderwritingState with all fields populated

    Returns:
        Multi-line reasoning trace string
    """
    trace_lines = []

    # ========== BMI ASSESSMENT ==========
    if state.extracted_data.bmi:
        bmi = state.extracted_data.bmi
        confidence = state.extracted_data.confidence_scores.get("bmi", 0.0)
        if bmi >= 30.0:
            bmi_class = "Obese Class I" if bmi < 35.0 else ("Obese Class II" if bmi < 40.0 else "Obese Class III")
            trace_lines.append(
                f"FLAGGED: BMI {bmi:.1f} ({bmi_class}) → +{35 if bmi < 35.0 else 60}% mortality surcharge | confidence: {confidence:.0%}"
            )
        elif bmi >= 25.0:
            trace_lines.append(
                f"FLAGGED: BMI {bmi:.1f} (Overweight) → +15% mortality surcharge | confidence: {confidence:.0%}"
            )
        else:
            trace_lines.append(f"OK: BMI {bmi:.1f} (normal range)")

    # ========== SMOKING ASSESSMENT ==========
    if state.extracted_data.smoker is not None:
        confidence = state.extracted_data.confidence_scores.get("smoker", 0.0)
        if state.extracted_data.smoker:
            trace_lines.append(
                f"FLAGGED: Current smoker → +100% mortality surcharge | confidence: {confidence:.0%}"
            )
        else:
            trace_lines.append(f"OK: Non-smoker")

    # ========== BLOOD PRESSURE ASSESSMENT ==========
    systolic = state.extracted_data.blood_pressure_systolic
    diastolic = state.extracted_data.blood_pressure_diastolic
    if systolic and diastolic:
        confidence = state.extracted_data.confidence_scores.get("blood_pressure_systolic", 0.0)
        if systolic >= 140 or diastolic >= 90:
            trace_lines.append(
                f"FLAGGED: Blood Pressure {systolic}/{diastolic} (Stage 2) → +50% mortality surcharge | confidence: {confidence:.0%}"
            )
        elif systolic >= 130 or diastolic >= 80:
            trace_lines.append(
                f"FLAGGED: Blood Pressure {systolic}/{diastolic} (Stage 1) → +25% mortality surcharge | confidence: {confidence:.0%}"
            )
        else:
            trace_lines.append(f"OK: Blood Pressure {systolic}/{diastolic} (normal)")

    # ========== MEDICAL CONDITIONS ASSESSMENT ==========
    if state.extracted_data.diabetes:
        trace_lines.append("FLAGGED: Diabetes → +40% mortality surcharge")
    if state.extracted_data.hypertension:
        trace_lines.append("FLAGGED: Hypertension (uncontrolled) → +25% mortality surcharge")
    if state.extracted_data.hyperlipidemia:
        trace_lines.append("FLAGGED: High Cholesterol → +20% mortality surcharge")
    if state.extracted_data.family_history_chd:
        trace_lines.append("FLAGGED: Family history of Coronary Heart Disease → +30% mortality surcharge")

    # ========== CAMBODIA-SPECIFIC OCCUPATIONAL RISK ==========
    if state.occupation_risk.risk_multiplier > 1.0:
        occ_type = state.extracted_data.occupation_type or "unknown"
        trace_lines.append(
            f"FLAGGED: Cambodia Occupational Risk ({occ_type}) → "
            f"+{(state.occupation_risk.risk_multiplier - 1.0) * 100:.0f}% surcharge"
        )

    # ========== CAMBODIA-SPECIFIC ENDEMIC/REGIONAL RISK ==========
    if state.region_risk.endemic_risk_multiplier > 1.0:
        province = state.extracted_data.province or "unknown"
        trace_lines.append(
            f"FLAGGED: Cambodia Endemic Disease Risk (Province: {province}) → "
            f"+{(state.region_risk.endemic_risk_multiplier - 1.0) * 100:.0f}% surcharge"
        )

    # ========== HEALTHCARE TIER RELIABILITY ==========
    if state.region_risk.healthcare_reliability_discount != 1.0:
        tier = state.extracted_data.healthcare_tier or "unknown"
        adj_pct = (1.0 - state.region_risk.healthcare_reliability_discount) * 100.0
        if state.region_risk.healthcare_reliability_discount < 1.0:
            trace_lines.append(
                f"OK: Medical exam at {tier} hospital (TierA) → "
                f"-{abs(adj_pct):.0f}% premium discount (high-confidence)"
            )
        else:
            trace_lines.append(
                f"FLAGED: Medical exam at {tier} facility → "
                f"+{adj_pct:.0f}% premium surcharge (lower reliability)"
            )

    # ========== EXTRACTION CONFIDENCE ==========
    conf_pct = state.overall_confidence * 100
    if state.overall_confidence < state.min_confidence_threshold:
        trace_lines.append(
            f"FLAGGED: Low extraction confidence ({conf_pct:.0f}% < {state.min_confidence_threshold * 100:.0f}%) → requires human review"
        )
    else:
        trace_lines.append(f"OK: Extraction confidence {conf_pct:.0f}% (above threshold)")

    # ========== MISSING CRITICAL FIELDS ==========
    missing = state.extracted_data.missing_fields()
    if missing:
        trace_lines.append(f"FLAGGED: Missing critical fields: {', '.join(missing)} → requires human review")

    # ========== FINAL RISK LEVEL ASSESSMENT ==========
    if state.risk_level == RiskLevel.DECLINE:
        trace_lines.append(f"FLAGGED: Risk Tier DECLINE (Mortality Ratio {state.risk_score/50:.2f}x) → automatic human review")
    elif state.risk_level == RiskLevel.HIGH:
        trace_lines.append(f"FLAGGED: Risk Tier HIGH → manual underwriter review recommended")
    elif state.risk_level == RiskLevel.MEDIUM:
        trace_lines.append(f"OK: Risk Tier MEDIUM (acceptable for standard underwriting)")
    else:
        trace_lines.append(f"OK: Risk Tier LOW (standard rates approved)")

    return "\n".join(trace_lines)


def review_node(state: UnderwritingState) -> UnderwritingState:
    """
    Review node: Determine if case requires human review.

    Triggers for human review:
    1. Extraction confidence < threshold
    2. Critical fields missing
    3. Risk level is HIGH or DECLINE
    4. Non-fatal errors encountered
    5. Cambodia-specific risk flags

    Args:
        state: UnderwritingState with pricing complete

    Returns:
        Updated UnderwritingState with review decision and reasoning_trace
    """

    review_reasons = []

    # Check extraction confidence
    if state.overall_confidence < state.min_confidence_threshold:
        review_reasons.append(
            f"Low extraction confidence: {state.overall_confidence:.2%} < {state.min_confidence_threshold:.2%}"
        )

    # Check for missing critical fields
    missing = state.extracted_data.missing_fields()
    if missing:
        review_reasons.append(f"Missing critical fields: {', '.join(missing)}")

    # Check risk level
    if state.risk_level in [RiskLevel.HIGH, RiskLevel.DECLINE]:
        review_reasons.append(f"High-risk case: {state.risk_level.value}")

    # Check for errors
    if state.errors:
        review_reasons.append(f"Errors encountered: {len(state.errors)}")

    # Check Cambodia-specific occupation risk
    if state.occupation_risk.risk_multiplier > 1.10:  # More than 10% surcharge
        review_reasons.append(
            f"Cambodia occupational risk: {state.extracted_data.occupation_type or 'unknown'}"
        )

    # Check Cambodia-specific endemic risk (high-risk provinces)
    if state.region_risk.endemic_risk_multiplier > 1.20:  # More than 20% surcharge
        review_reasons.append(
            f"Cambodia endemic disease risk: {state.extracted_data.province or 'unknown'}"
        )

    # Determine review requirement
    required = len(review_reasons) > 0

    # Build SHAP-style reasoning trace
    reasoning_trace = _build_reasoning_trace(state)
    state.reasoning_trace = reasoning_trace

    # Build review notes
    review_notes = ReviewNotes(
        required=required,
        reason=" | ".join(review_reasons) if review_reasons else None,
    )

    state.review = review_notes
    state.status = "review"
    state.current_node = "review"

    # Add audit trail entry
    state.add_audit_entry(
        node="review",
        action="assessed_review_requirement",
        details={
            "requires_review": required,
            "reasons": review_reasons,
            "reasoning_trace_lines": len(reasoning_trace.split("\n")),
        },
        confidence=1.0,
    )

    return state
