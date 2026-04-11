# Medical Document → Health Insurance Pricing Bridge

**Created**: 2026-04-12  
**Last updated**: 2026-04-12  
**Status**: ✅ Built — `medical_reader/nodes/health_pricing_bridge.py` + `POST /cases/{id}/health-quote`  
**Related**: [Augmented Underwriter Workflow](./augmented-underwriter-workflow.md) · [Actuarial Scenario Agent](./actuarial-scenario-agent.md) · [Intelligent Document Processing](./intelligent-document-processing.md) · [Pricing Engine Phases](./pricing-engine-phases.md)

---

## The Problem It Solves

Before this bridge, the two main subsystems did not talk to each other:

| Subsystem | Input | Output | Engine |
|---|---|---|---|
| `medical_reader/` | PDF document | Life insurance premium | Mortality Ratio method |
| `app/pricing_engine/` | JSON profile | Health insurance premium | Poisson-Gamma GLM |

An actuary reviewing a submitted PDF could see the life insurance result from the intake
workflow, but had no way to get a health insurance quote from the same extracted data
without manually re-entering all the fields.

The bridge closes this loop.

---

## Architecture

```
PDF upload
    │
    ▼
intake_node (Claude Vision)
    │  ExtractedMedicalData
    ▼
bridge_extracted_to_health_quote()     ← NEW (health_pricing_bridge.py)
    │
    ├── field mapping (direct where schemas overlap)
    ├── clinical defaults (for fields absent from medical PDFs)
    └── stress inference (from medication count)
    │
    ▼
compute_health_glm_price(MedicalProfile)
    │
    ▼
POST /cases/{case_id}/health-quote
    │
    ▼
{ life_insurance: {...}, health_insurance: {...}, mapping_notes: [...] }
```

---

## Field Mapping Table

| `ExtractedMedicalData` field | → | `MedicalProfile` field | Notes |
|---|---|---|---|
| `age` | → | `age` | Direct |
| `gender` (M/F) | → | `gender` (Male/Female) | Normalised |
| `smoker` (bool) | → | `smoking_status` | True→Current, False→Never |
| `alcohol_use` | → | `alcohol_use` | Schema normalised |
| `bmi` | → | `bmi` | Direct |
| `blood_pressure_systolic` | → | `systolic_bp` | Direct |
| `blood_pressure_diastolic` | → | `diastolic_bp` | Direct |
| `diabetes` | → | `pre_existing_conditions` | Adds "Diabetes" |
| `hypertension` | → | `pre_existing_conditions` | Adds "Hypertension" |
| `hyperlipidemia` | → | `pre_existing_conditions` | Adds "High Cholesterol" |
| `family_history_chd` | → | `family_history` | Adds CHD entry |
| `medications` count | → | `stress_level` | Heuristic: ≥4 meds → High, ≥2 → Moderate |
| — | → | `exercise_frequency` | Default: Moderate |
| — | → | `occupation_type` | Default: Office/Desk |
| — | → | `diet_quality` | Default: Balanced |
| — | → | `sleep_hours_per_night` | Default: Fair (5-7h) |
| — | → | `motorbike_use` | Default: No |
| — | → | `distance_to_hospital_km` | Default: 5.0 (urban) |

Fields marked "—" cannot be extracted from medical PDFs; conservative clinical defaults are
applied and flagged in `inferred_fields`.

---

## Pricing Confidence

`pricing_confidence` (0.30–1.0) penalises the quote when many fields were inferred rather
than extracted:

```python
pricing_confidence = max(0.30, extracted_count / total_extractable_fields)
```

An actuary sees this number alongside the quote. A confidence of 0.75 means 75% of the
fields that *could* be extracted from a PDF *were* extracted — the remaining 25% used defaults.

This matters for IRC audit trail compliance: the actuary knows which risk factors were
evidence-based and which were assumed.

---

## Endpoint: `POST /cases/{case_id}/health-quote`

**Location**: `api/routers/cases.py`  
**Auth**: standard case API auth

**Request body** (all optional — overrides applied on top of extracted data):

```json
{
  "country": "cambodia",
  "region": "Phnom Penh",
  "ipd_tier": "Silver",
  "coverage_types": ["ipd"],
  "face_amount": 50000.0,
  "policy_term_years": 1
}
```

**Response structure**:

```json
{
  "case_id": "CASE-20260412-120000",
  "life_insurance": {
    "gross_annual_premium": 1240.00,
    "monthly_premium": 103.33,
    "mortality_ratio": 1.85,
    "risk_tier": "high",
    "factor_breakdown": { "smoking": 1.50, "diabetes": 1.45, ... }
  },
  "health_insurance": {
    "profile": { ... },
    "quote": {
      "gross_annual_premium": 1000.00,
      "mortality_ratio": 2.35,
      "risk_tier": "HIGH",
      "factor_breakdown": { "smoking": 1.50, "diabetes": 1.45, "bp_stage1": 1.20 }
    },
    "pricing_confidence": 0.75,
    "inferred_fields": ["exercise_frequency", "occupation_type", ...],
    "mapping_notes": ["age=45 (extracted, conf=0.97)", "smoking_status=Current (extracted)", ...]
  },
  "note": "Life insurance uses Mortality Ratio method. Health insurance uses Poisson-Gamma GLM."
}
```

---

## Why Two Pricing Methods Side-by-Side?

The two engines serve different actuarial purposes:

| | Life Insurance | Health Insurance |
|---|---|---|
| **Engine** | Mortality Ratio | Poisson-Gamma GLM |
| **Formula** | Face × q(x) × MR | freq × sev × loadings |
| **What it prices** | Death benefit | Medical claim cost |
| **Primary risk driver** | Mortality | Morbidity + utilisation |
| **Location** | `medical_reader/pricing/calculator.py` | `app/pricing_engine/health_pricing.py` |

Showing both side-by-side from the same extracted data gives the actuary a complete risk
picture from a single PDF submission — and makes it easy to spot cases where the two engines
diverge (e.g. a HIGH life risk that is MEDIUM health risk, suggesting acute vs. chronic condition).

---

## Audit Trail Integration

All mapping decisions are recorded in `mapping_notes` (one entry per field). This satisfies
IRC Prakas 093 transparency requirements: every premium component traces back to either
an extracted value (with confidence score) or a named default with actuarial rationale.

See [Underwriting Audit Trail](./underwriting-audit-trail.md) for the broader audit trail framework.
