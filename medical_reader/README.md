# Medical Reader: OCR → JSON → GLM-Ready Extraction

A Python prototype for extracting medical data from PDF documents and producing clean, validated JSON suitable for actuarial pricing models.

## Architecture

```
Medical PDF
    ↓
[pypdf or LlamaParse] ← Raw text/table extraction
    ↓
[Claude API] ← Interpret & structure to JSON
    ↓
[Pydantic Validation] ← Schema + Domain + Consistency checks
    ↓
Valid JSON → GLM Model
```

## What It Does

1. **PDF Extraction** (`extractor.py`)
   - Converts medical PDFs to text (using pypdf or LlamaParse)
   - Uses Claude API to structure extracted content into clean JSON
   - Returns `MedicalRecord` with confidence score

2. **Three-Layer Validation** (`validator.py`)
   - **Schema**: Ensures correct data types (via Pydantic)
   - **Domain**: Checks physiological ranges (BMI 10-60, BP 70-200, etc.)
   - **Consistency**: Cross-field rules (Diabetes → glucose required, etc.)

3. **Smart Routing** 
   - `stp`: Auto-approve (healthy profile, high confidence, complete data)
   - `human_review`: Medium complexity or flags detected
   - `reject`: Critical data missing or hallucinations detected

4. **Audit Trail**
   - Confidence scores per extraction
   - Source document tracking
   - Validation flags for compliance

## Data Schema

### Input
Medical PDF with patient data (vitals, labs, history)

### Output JSON
```json
{
  "policy_id": "POL-2026-0001",
  "extraction_meta": {
    "method": "pypdf_claude",
    "confidence": 0.92,
    "extracted_at": "2026-04-09T09:49:30Z",
    "source_document": "medical_record.pdf"
  },
  "vitals": {
    "age": 35,
    "bmi": 24.5,
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "heart_rate": 72
  },
  "labs": {
    "blood_glucose_fasting": 95.0,
    "total_cholesterol": 185.0,
    "hdl_cholesterol": 55.0,
    "ldl_cholesterol": 110.0,
    "triglycerides": 100.0,
    "lab_date": "2026-03-15"
  },
  "history": {
    "conditions": ["Hypertension"],
    "medications": ["Amlodipine 5mg"],
    "tobacco_status": "never",
    "family_history": ["Father had heart disease"]
  },
  "validation": {
    "schema_valid": true,
    "domain_valid": true,
    "consistency_valid": true,
    "flags": [],
    "routing": "stp"
  }
}
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r medical_reader/requirements.txt
```

### 2. Set Up API Key
```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

### 3. Run Demo
```bash
# Generates 4 synthetic medical PDFs, extracts data, validates
python -m medical_reader.run_demo
```

Results saved to `test_outputs/` as JSON files.

### 4. Use in Your Code
```python
from medical_reader import extract_medical_record, validate_medical_record

# Extract from PDF
record = extract_medical_record("path/to/medical_record.pdf", policy_id="POL-2026-0001")

# Validate
record = validate_medical_record(record)

# Check routing decision
print(record.validation.routing)  # "stp" or "human_review"

# Convert to GLM input
glm_input = record.to_glm_input()
```

## File Structure

```
medical_reader/
├── __init__.py          # Package exports
├── schemas.py           # Pydantic models (MedicalRecord, VitalSigns, etc.)
├── generator.py         # Synthetic PDF generator for testing
├── extractor.py         # PDF → Claude → JSON extraction pipeline
├── validator.py         # Three-layer validation logic
├── run_demo.py          # End-to-end demo runner
└── requirements.txt     # Python dependencies
```

## Validation Rules

### Schema Validation
- Ensures all fields are correct data types (integers, floats, strings, enums)
- Catches type mismatches and missing required fields

### Domain Validation (Physiological Ranges)
| Variable | Min | Max | Unit |
|---|---|---|---|
| Age | 18 | 120 | years |
| BMI | 10 | 60 | kg/m² |
| Systolic BP | 70 | 200 | mmHg |
| Diastolic BP | 40 | 120 | mmHg |
| Heart Rate | 40 | 150 | bpm |
| Blood Glucose | 60 | 500 | mg/dL |
| Cholesterol | 100 | 400 | mg/dL |

### Consistency Validation
- If `Diabetes` noted → `blood_glucose_fasting` required
- If `Hypertension` noted → BP readings required
- Medications must align with conditions (e.g., Metformin → Diabetes)

## Routing Logic

```python
if confidence < 0.80:
    routing = "human_review"
elif missing_required_fields:
    routing = "human_review"
elif healthy_profile AND high_confidence:
    routing = "stp"
elif has_conditions OR elevated_metrics:
    routing = "human_review"
```

## Testing

### Generate Synthetic PDFs
```bash
python -m medical_reader.generator
```

Creates test PDFs:
- `healthy_applicant.pdf` - Clean vitals, normal labs
- `hypertensive_applicant.pdf` - Elevated BP, condition noted
- `diabetic_applicant.pdf` - High glucose, multiple comorbidities
- `high_risk_applicant.pdf` - Multiple flags, high intervention needed

### Run Full Demo
```bash
python -m medical_reader.run_demo
```

Outputs:
- Console summary with extraction status and routing
- JSON files in `test_outputs/` for each policy

## Error Handling

**Missing PDF**: Raises `FileNotFoundError`

**Claude API Failure**: Returns empty MedicalRecord with confidence=0.0, routes to `human_review`

**JSON Parse Error**: Falls back to empty structure, logs warning

**Invalid Data**: Validation catches out-of-range values and flags them

## Next Steps: Integration with LangGraph

This module is designed to plug into the larger orchestration workflow:

```
LangGraph Node: Extract
    ↓
[medical_reader.extract_medical_record()]
    ↓
LangGraph Node: Validate
    ↓
[medical_reader.validate_medical_record()]
    ↓
LangGraph Node: Score (GLM)
    ↓
[Risk Scoring Model]
```

## Development Notes

- **Claude Model**: Uses `claude-opus-4-6` for best extraction accuracy
- **PDF Library**: pypdf fallback if LlamaParse unavailable
- **Confidence Scoring**: Claude returns field-level confidence; aggregated to extract-level
- **Audit Trail**: All extractions include source document, method, timestamp
- **Extensibility**: Easy to add new validation rules or medical fields

## Compliance

For Cambodian IRC (Insurance Regulatory Commission) compliance:
- ✅ Audit trail: source document + extraction method + timestamp
- ✅ Validation: physiological bounds prevent hallucinations
- ✅ Human-in-loop: routing decision flags for underwriter review
- ✅ Explainability: validation flags explain why human review needed
