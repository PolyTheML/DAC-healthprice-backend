# Medical Underwriting Agent - Quick Start

AI-powered medical risk assessment and premium calculation using Claude Vision and GLM actuarial models.

**Status**: ✅ Phase 2 Working Prototype (2026-04-09)

---

## Architecture

```
medical_reader/
├── state.py              # UnderwritingState: canonical state model (Pydantic)
├── nodes/
│   ├── intake.py         # Extract medical data from PDFs (Claude Vision)
│   ├── pricing.py        # Calculate premium using Frequency-Severity GLM
│   └── review.py         # Flag cases for human review
├── app.py                # Streamlit dashboard (interactive UI)
├── test_workflow.py      # CLI test runner
├── test_data/
│   ├── healthy.pdf       # Sample: 45yo, good vitals
│   ├── high_risk.pdf     # Sample: 62yo, multiple conditions
│   └── unreadable.pdf    # Sample: Poor quality scan
└── generate_test_pdfs.py # Script to generate test PDFs
```

---

## Quick Test (CLI)

Run the full workflow on all test PDFs:

```bash
python -m medical_reader.test_workflow
```

Expected output:
```
Processing: healthy.pdf
[1/3] Initialized state: pending
[2/3] Running intake node...
      Status: intake
      Extraction confidence: 99%
      Extracted fields: 12
[3/3] Running pricing node...
      Status: pricing
      Risk level: medium
      Final premium: $15,431
[4/4] Running review node...
      Status: review
      Requires human review: False
```

---

## Interactive Dashboard (Streamlit)

Run the web interface:

```bash
streamlit run medical_reader/app.py
```

Then open: **http://localhost:8501**

### Features:
- **📄 Upload or select test PDFs** — Process real medical records
- **📋 View extracted data** — See all fields with confidence scores
- **💰 Premium calculation** — Risk-based GLM pricing
- **👥 Human review flags** — Automated triage
- **📜 Audit trail** — Full compliance traceability
- **📥 Export reports** — Download audit trail and case summary

---

## Workflow Pipeline

```
PDF Input
    ↓
┌─────────────────────────────────────────┐
│ INTAKE NODE (intake.py)                 │
│ - Read PDF using Claude Vision API     │
│ - Extract: age, BMI, BP, vitals, etc.  │
│ - Assign confidence scores (0.0-1.0)   │
│ - Validate critical fields             │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ PRICING NODE (pricing.py)               │
│ - Calculate frequency score (GLM)       │
│ - Calculate severity score (GLM)        │
│ - Apply Gamma-Poisson model            │
│ - Determine risk tier & final premium   │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ REVIEW NODE (review.py)                 │
│ - Flag cases for human review:         │
│   • Low confidence                     │
│   • Missing critical fields            │
│   • High/Decline risk tier            │
│   • Processing errors                  │
└─────────────────────────────────────────┘
    ↓
Underwriting Decision (approved/declined/review)
```

---

## State Management

All nodes operate on a single immutable `UnderwritingState` object:

```python
from medical_reader.state import UnderwritingState

state = UnderwritingState(
    case_id="CASE-2025-001",
    source_document_path="test_data/healthy.pdf"
)

# Each node reads state, processes, returns updated state
state = intake_node(state)
state = pricing_node(state)
state = review_node(state)

# Audit trail captures every decision
for entry in state.audit_trail:
    print(f"[{entry.timestamp}] {entry.node}/{entry.action}")

# Export for compliance/reporting
print(state.to_audit_report())
print(state.to_summary())  # JSON-safe dict
```

---

## GLM Model

**Frequency-Severity Gamma-Poisson GLM**

Frequency (claims/year adjustment):
```
frequency_score = base_freq × (age_factor × bmi_factor × smoking_factor × condition_factors)
```

- Base: 0.15 claims/year (45yo standard)
- Age: (age - 25) / 25
- BMI: 1.0 + (|BMI - 25| / 25) × 0.5
- Smoking: 2.0 if smoker, else 1.0
- Conditions: 1.0 + (condition_count × 0.20)

Severity (claim cost adjustment):
```
severity_score = 1.0 × (condition_severity × age_severity × lifestyle_severity)
```

Premium:
```
final_premium = (freq × severity × 5000 × 1.35 × 100) × risk_multiplier
```

Risk tiers:
- 🟢 **LOW** (score < 20): 0.80x multiplier
- 🟡 **MEDIUM** (20-80): 1.00x multiplier
- 🔴 **HIGH** (80-110): 1.50x multiplier
- 🚫 **DECLINE** (> 110): 2.50x multiplier or decline offer

---

## API Key Setup

Export your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

The agents use `claude-opus-4-6` for medical data extraction.

---

## File Reference

| File | Purpose |
|------|---------|
| `state.py` | Pydantic models: UnderwritingState, ExtractedMedicalData, ActuarialCalculation |
| `nodes/intake.py` | Claude Vision extraction + confidence scoring |
| `nodes/pricing.py` | GLM calculation, risk tier assignment |
| `nodes/review.py` | Human review triage logic |
| `app.py` | Streamlit dashboard + interactive workflow |
| `test_workflow.py` | CLI test runner (no Streamlit needed) |
| `generate_test_pdfs.py` | Create sample PDFs for testing |

---

## Knowledge Base Grounding

All decision logic is grounded in source documents:

- **Frequency-Severity Model**: `wiki/topics/frequency-severity-glm.md`
- **Compliance & Governance**: `wiki/topics/compliance-governance.md`
- **IRC Cambodia Standards**: `wiki/sources/IRC-Cambodia-guidelines.pdf`
- **Medical Data**: 50+ ingested sources (see `wiki/index.md`)

Each code comment references the wiki page backing the logic.

---

## For Friday Demo

**Talking Points**:
1. Show the wiki folder → "All AI decisions are grounded in 50+ industry sources"
2. Run test workflow → "Processes PDFs in < 5 seconds"
3. Upload healthy.pdf → "See real-time extraction with confidence scores"
4. Scroll audit trail → "Every decision is logged for regulatory audit"
5. Show pricing code → "Gamma-Poisson GLM, traced back to thesis"

**Time estimates**:
- Test workflow: ~5 sec (3 PDFs)
- Streamlit dashboard startup: ~2 sec
- PDF upload & process: ~3 sec per document

---

## Troubleshooting

**Module not found**:
```bash
cd /path/to/DAC-UW-Agent
python -m medical_reader.test_workflow
```

**API key missing**:
```bash
echo $ANTHROPIC_API_KEY  # Check if set
export ANTHROPIC_API_KEY="sk-ant-..."
```

**PDF extraction returns nulls**:
- Low-quality scans (like `unreadable.pdf`) will have low confidence
- System flags these for human review
- This is intended behavior

**Streamlit port already in use**:
```bash
streamlit run medical_reader/app.py --server.port=8502
```

---

## Next Steps

- [ ] Integrate with LangGraph for explicit workflow orchestration
- [ ] Add human review UI (approval/decline/notes)
- [ ] Store case history in database
- [ ] Backtesting against historical underwriting decisions
- [ ] Model calibration & performance metrics

---

**Built with**: Claude API (Vision + Text), Pydantic, Streamlit, LangGraph  
**For**: UW Agent thesis demo (April 2026)  
**Status**: Working prototype, ready for Friday presentation
