"""
Intake Node: Extract medical data from PDF documents.

Reads source PDFs and extracts structured medical information using Claude Vision API.
Populates ExtractedMedicalData with confidence scores for each field.

Based on: wiki/topics/medical-data-extraction.md
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
import base64

import anthropic

from ..state import UnderwritingState, ExtractedMedicalData, RiskLevel


def read_pdf_as_base64(filepath: str) -> str:
    """Read PDF file and encode as base64 for Claude API."""
    with open(filepath, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def extract_medical_data(pdf_path: str) -> Dict[str, Any]:
    """
    Extract medical data from PDF using Claude Vision API.

    Returns dict with extracted fields and confidence scores.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Read PDF as base64
    pdf_base64 = read_pdf_as_base64(pdf_path)

    # Construct extraction prompt (Cambodia-aware, bilingual)
    extraction_prompt = """Analyze this medical document (may be bilingual Khmer-English) and extract medical data.

KHMER MEDICAL TERMS — If present in document:
- 'សម្ពាធឈាម' = blood pressure | 'ទឹកនោមផ្អែម' = diabetes | 'ជំងឺបេះដូង' = heart disease
- 'ថ្នាំ' = medication | 'ខ្លាញ់ក្នុងឈាម' = cholesterol | 'ជំងឺសួត' = lung disease
- 'ជំងឺថ្លើម' = liver disease | 'ភ្លើងចត' = dengue | 'គ្រុនចាញ់' = malaria
- 'ជក់បារី' = smoker | 'វ័យ' = age | 'ផ្ទៃខ្ពស់' = height | 'ទំងន់' = weight

Return ONLY a JSON object with this exact structure (no markdown, no extra text):

{
    "age": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "gender": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "bmi": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "blood_pressure_systolic": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "blood_pressure_diastolic": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "smoker": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "diabetes": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "hypertension": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "hyperlipidemia": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "family_history_chd": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "medications": {"value": [], "confidence": 0.0, "method": "not_found", "source": ""},
    "alcohol_use": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "province": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "occupation_type": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "motorbike_usage": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""},
    "healthcare_tier": {"value": null, "confidence": 0.0, "method": "not_found", "source": ""}
}

For each field found in the document:
- Set value to the extracted value
- Set confidence (0.0-1.0): higher = more certain, 0.95+ if explicitly stated
- Set method to: "exact", "inferred", "estimated", or "not_found"
- Set source to: "page N", "table N", "section name", or "" if not found

Cambodia-specific fields (if in document):
- province: Cambodian province/region name
- occupation_type: Job type (Office/Desk | Retail/Service | Manual Labor | Construction | Healthcare | Motorbike Courier | Retired)
- motorbike_usage: Never | Occasional | Daily
- healthcare_tier: Where exam was done (TierA hospital | TierB | Clinic | Unknown)

If field not in document, leave as null with confidence 0.0."""

    # Call Claude API with vision
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": extraction_prompt,
                    },
                ],
            }
        ],
    )

    # Parse response
    response_text = message.content[0].text

    # Try to extract JSON from response (in case it's wrapped in markdown)
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    try:
        extracted = json.loads(response_text)
    except json.JSONDecodeError as e:
        # If JSON parsing fails, return error
        return {"extraction_error": f"JSON parse failed: {str(e)}", "confidence": 0.0}

    return extracted


def intake_node(state: UnderwritingState) -> UnderwritingState:
    """
    Intake node: Extract medical data from source PDF.

    1. Read PDF from source_document_path
    2. Call Claude API for extraction
    3. Populate extracted_data with confidence scores
    4. Log audit trail
    5. Determine if human review required

    Args:
        state: UnderwritingState with source_document_path set

    Returns:
        Updated UnderwritingState with extracted_data populated
    """

    if not state.source_document_path:
        state.add_error("No source_document_path provided")
        state.status = "error"
        return state

    pdf_path = state.source_document_path
    if not Path(pdf_path).exists():
        state.add_error(f"PDF not found: {pdf_path}")
        state.status = "error"
        return state

    # Extract medical data from PDF
    try:
        extracted_dict = extract_medical_data(pdf_path)
    except Exception as e:
        state.add_error(f"Extraction failed: {str(e)}")
        state.status = "error"
        return state

    # Check for extraction error
    if "extraction_error" in extracted_dict:
        state.add_error(extracted_dict.get("extraction_error", "Unknown extraction error"))
        state.status = "error"
        return state

    # Build ExtractedMedicalData
    extracted_data = ExtractedMedicalData()
    confidence_scores = {}
    extraction_methods = {}

    for field, field_info in extracted_dict.items():
        if isinstance(field_info, dict):
            value = field_info.get("value")
            confidence = field_info.get("confidence", 0.0)
            method = field_info.get("method", "unknown")

            # Set field if it has a value
            if value is not None:
                if field == "medications":
                    # Handle list specially
                    extracted_data.medications = value if isinstance(value, list) else [value]
                elif hasattr(extracted_data, field):
                    setattr(extracted_data, field, value)

            confidence_scores[field] = confidence
            extraction_methods[field] = method

    extracted_data.confidence_scores = confidence_scores

    # Calculate overall confidence
    overall_confidence = (
        sum(confidence_scores.values()) / len(confidence_scores)
        if confidence_scores
        else 0.0
    )

    # Update state
    state.extracted_data = extracted_data
    state.overall_confidence = overall_confidence
    state.status = "intake"
    state.current_node = "intake"

    # Add audit trail entry
    state.add_audit_entry(
        node="intake",
        action="extracted_medical_data",
        details={
            "fields_extracted": len([c for c in confidence_scores.values() if c > 0.0]),
            "pdf_path": pdf_path,
            "extraction_methods": extraction_methods,
            "missing_critical_fields": extracted_data.missing_fields(),
        },
        confidence=overall_confidence,
    )

    # Flag for human review if confidence too low or critical fields missing
    if overall_confidence < state.min_confidence_threshold:
        state.add_error(
            f"Low extraction confidence: {overall_confidence:.2f} < {state.min_confidence_threshold:.2f}"
        )

    if extracted_data.missing_fields():
        state.add_error(
            f"Missing critical fields: {', '.join(extracted_data.missing_fields())}"
        )

    return state
