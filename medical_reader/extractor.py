"""Extract medical data from PDFs using LlamaParse + Claude"""

import json
import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import anthropic

# ========== KHMER MEDICAL GLOSSARY ==========
KHMER_MEDICAL_GLOSSARY = {
    "សម្ពាធឈាម": "blood_pressure",
    "ទឹកនោមផ្អែម": "diabetes",
    "ជំងឺបេះដូង": "heart_disease",
    "ថ្នាំ": "medication",
    "ខ្លាញ់ក្នុងឈាម": "cholesterol",
    "ជំងឺសួត": "lung_disease",
    "ជំងឺថ្លើម": "liver_disease",
    "ភ្លើងចត": "dengue",
    "គ្រុនចាញ់": "malaria",
    "ជក់បារី": "smoker",
    "វ័យ": "age",
    "ផ្ទៃខ្ពស់": "height",
    "ទំងន់": "weight",
    "ស្ត្រី": "female",
    "បុរស": "male",
}

from .schemas import (
    MedicalRecord,
    ExtractionMeta,
    VitalSigns,
    LabValues,
    MedicalHistory,
    TobaccoStatus,
)

# Set stdout encoding to UTF-8 to handle unicode properly on Windows
if sys.platform == "win32":
    import io
    if sys.stdout.encoding != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def extract_medical_record(
    pdf_path: str,
    policy_id: str = "POL-2026-0001",
    use_llamaparse: bool = False,  # Set to True if LlamaParse API available
) -> MedicalRecord:
    """
    Extract medical data from PDF using hybrid approach:
    1. Parse PDF structure (LlamaParse or raw text)
    2. Interpret extracted content with Claude
    3. Return MedicalRecord
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Step 1: Extract raw content
    if use_llamaparse:
        raw_content = _extract_with_llamaparse(pdf_path)
    else:
        raw_content = _extract_with_pypdf(pdf_path)

    # Step 2: Interpret with Claude
    extraction_result = _interpret_with_claude(raw_content, pdf_path.name)

    # Step 3: Package into MedicalRecord
    record = MedicalRecord(
        policy_id=policy_id,
        extraction_meta=ExtractionMeta(
            method="hybrid_llamaparse_claude" if use_llamaparse else "pypdf_claude",
            confidence=extraction_result.get("confidence", 0.85),
            extracted_at=datetime.utcnow(),
            source_document=pdf_path.name,
        ),
        vitals=VitalSigns(
            age=extraction_result.get("age"),
            bmi=extraction_result.get("bmi"),
            systolic_bp=extraction_result.get("systolic_bp"),
            diastolic_bp=extraction_result.get("diastolic_bp"),
            heart_rate=extraction_result.get("heart_rate"),
        ),
        labs=LabValues(
            blood_glucose_fasting=extraction_result.get("blood_glucose_fasting"),
            total_cholesterol=extraction_result.get("total_cholesterol"),
            hdl_cholesterol=extraction_result.get("hdl_cholesterol"),
            ldl_cholesterol=extraction_result.get("ldl_cholesterol"),
            triglycerides=extraction_result.get("triglycerides"),
            lab_date=extraction_result.get("lab_date"),
        ),
        history=MedicalHistory(
            conditions=extraction_result.get("conditions", []),
            medications=extraction_result.get("medications", []),
            tobacco_status=TobaccoStatus(extraction_result.get("tobacco_status", "unknown")),
            family_history=extraction_result.get("family_history", []),
        ),
    )

    return record


def _extract_with_llamaparse(pdf_path: Path) -> str:
    """
    Extract text/tables from PDF using LlamaParse API.
    Requires LLAMA_CLOUD_API_KEY environment variable.
    """
    try:
        from llama_parse import LlamaParse
    except ImportError:
        print("[WARNING] LlamaParse not installed, falling back to pypdf")
        return _extract_with_pypdf(pdf_path)

    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        print("[WARNING] LLAMA_CLOUD_API_KEY not set, falling back to pypdf")
        return _extract_with_pypdf(pdf_path)

    try:
        parser = LlamaParse(api_key=api_key)
        result = parser.load_data(str(pdf_path))
        # LlamaParse returns Document objects; extract text
        content = "\n".join([doc.get_content() for doc in result])
        return content
    except Exception as e:
        print(f"[WARNING] LlamaParse extraction failed: {e}, falling back to pypdf")
        return _extract_with_pypdf(pdf_path)


def _extract_with_pypdf(pdf_path: Path) -> str:
    """
    Fallback: Extract text from PDF using pypdf.
    Simple text extraction; loses table structure but captures content.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        print("[WARNING] pypdf not installed, installing...")
        os.system("pip install pypdf")
        from pypdf import PdfReader

    try:
        reader = PdfReader(str(pdf_path))
        content = ""
        for page in reader.pages:
            content += page.extract_text() + "\n"
        return content
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF: {e}")


def _interpret_with_claude(raw_content: str, source_filename: str) -> dict:
    """
    Send raw PDF content to Claude and ask it to extract structured medical data.
    Uses JSON mode for reliable structured output.
    """
    client = anthropic.Anthropic()

    extraction_prompt = f"""
You are a medical data extraction specialist. Extract structured medical data from the following medical record document.

MEDICAL RECORD CONTENT:
{raw_content}

Extract and return ONLY valid JSON (no markdown, no code blocks) with the following schema:
{{
    "age": <integer or null>,
    "bmi": <float or null>,
    "systolic_bp": <integer mmHg or null>,
    "diastolic_bp": <integer mmHg or null>,
    "heart_rate": <integer bpm or null>,
    "blood_glucose_fasting": <float mg/dL or null>,
    "total_cholesterol": <float mg/dL or null>,
    "hdl_cholesterol": <float mg/dL or null>,
    "ldl_cholesterol": <float mg/dL or null>,
    "triglycerides": <float mg/dL or null>,
    "lab_date": "<YYYY-MM-DD or null>",
    "conditions": ["<condition1>", "<condition2>"],
    "medications": ["<med1 with dosage>", "<med2 with dosage>"],
    "tobacco_status": "<never|former|current|unknown>",
    "family_history": ["<item1>", "<item2>"],
    "confidence": <0.0 to 1.0 representing extraction confidence>
}}

Rules:
- Only extract values that are explicitly stated in the document
- Do NOT hallucinate or infer values
- Use null for any missing data
- For numeric values, extract the actual number (e.g., "120" not "120/80" for systolic)
- Confidence should be high (0.9+) only if all major fields are clearly present
- Confidence should be medium (0.7-0.9) if some fields are missing or unclear
- Confidence should be low (<0.7) if document is heavily damaged or unreadable
- Return valid JSON that can be parsed

IMPORTANT: Return ONLY the JSON object, nothing else.
"""

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": extraction_prompt,
                }
            ],
        )

        response_text = message.content[0].text.strip()

        # Try to parse JSON
        try:
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            extracted_data = json.loads(response_text)
            return extracted_data
        except json.JSONDecodeError as e:
            print(f"[WARNING] Failed to parse Claude response as JSON: {e}")
            print(f"Response was: {response_text[:200]}...")
            # Return empty structure with low confidence
            return {
                "age": None,
                "bmi": None,
                "systolic_bp": None,
                "diastolic_bp": None,
                "heart_rate": None,
                "blood_glucose_fasting": None,
                "total_cholesterol": None,
                "hdl_cholesterol": None,
                "ldl_cholesterol": None,
                "triglycerides": None,
                "lab_date": None,
                "conditions": [],
                "medications": [],
                "tobacco_status": "unknown",
                "family_history": [],
                "confidence": 0.0,
            }

    except anthropic.APIError as e:
        print(f"[WARNING] Claude API error: {e}")
        # Return empty structure with low confidence
        return {
            "age": None,
            "bmi": None,
            "systolic_bp": None,
            "diastolic_bp": None,
            "heart_rate": None,
            "blood_glucose_fasting": None,
            "total_cholesterol": None,
            "hdl_cholesterol": None,
            "ldl_cholesterol": None,
            "triglycerides": None,
            "lab_date": None,
            "conditions": [],
            "medications": [],
            "tobacco_status": "unknown",
            "family_history": [],
            "confidence": 0.0,
        }
