# Pabbly Medical Data Extraction AI Agent

**Source**: Pabbly YouTube Channel  
**Title**: How to Build an AI Agent to Extract Data from Medical Report  
**Channel**: Pabbly (62.1K subscribers)  
**Published**: March 12, 2025  
**Duration**: ~20 minutes  
**Views**: 966

---

## Overview

Practical tutorial demonstrating a no-code/low-code approach to building an AI agent that automatically extracts patient data from medical reports and populates a structured database (Google Sheets). Shows a production-ready workflow using Pabbly Connect, OpenAI GPT-4 Vision, and Google Drive/Sheets integration.

---

## Use Case

**Problem**: Medical reports (lab results, radiology findings, doctor's notes) arrive regularly as PDFs/images, requiring manual data entry into EHR or spreadsheet systems.

**Solution**: Automated AI agent that:
1. Monitors Google Drive folder for new medical reports (PDFs or images)
2. Sends files to OpenAI for intelligent extraction
3. Structures extracted data using JSON schema
4. Automatically populates Google Sheets with results
5. Can further distribute results via WhatsApp, email, or CRM systems

**Benefit**: Diagnostic center can extract test results from PDFs, send to doctors/patients automatically, reducing administrative delays and manual error.

---

## Architecture (Trigger-Action Model)

### Workflow Steps

```
Google Drive Trigger (new medical report PDF)
    ↓ [File URL captured]
OpenAI Extraction (GPT-4 Vision + structured output)
    ↓ [JSON response mapped to schema]
Google Sheets Action (new row with extracted data)
    ↓
Optional: Distribute via WhatsApp/Email/CRM
```

---

## Technical Implementation

### 1. Trigger: Google Drive Connection

**Configuration**:
- Select "new file in specific folder" trigger
- Connect Google Drive account (OAuth)
- Specify folder where medical reports will be uploaded
- Note: Folder must have "anyone with link" sharing permission for API access
- Polling interval: 10 minutes (default for Pabbly Connect)

**Output**:
- File web view link
- File download URL
- File name and metadata

### 2. Action: OpenAI Extraction

**Model**: GPT-4 Vision (gpt-4-turbo-with-vision, or similar)

**Setup**:
- Create OpenAI API key in account settings
- Connect API key to Pabbly workflow

**Input Parameters**:
- **PDF/Image URL**: Mapped from Google Drive trigger response (download URL)
- **Prompt**: "Extract the details from the medical report of the patient"
- **Structured Output**: JSON schema defining expected fields

**Structured Output (JSON Schema)**

Must specify expected fields and types for consistent extraction. Example schema:

```json
{
  "type": "object",
  "properties": {
    "patient_name": {"type": "string"},
    "contact_number": {"type": "string"},
    "date_of_birth": {"type": "string"},
    "gender": {"type": "string"},
    "primary_diagnosis": {"type": "string"},
    "current_medication": {"type": "string"},
    "allergies": {"type": "string"},
    "blood_group": {"type": "string"},
    "last_visit_date": {"type": "string"},
    "doctor_name": {"type": "string"},
    "hospital_clinic_name": {"type": "string"},
    "next_appointment_date": {"type": "string"},
    "notes": {"type": "string"}
  },
  "required": ["patient_name", "date_of_birth"]
}
```

**Key Insight**: Structured output ensures consistent JSON response format every time, regardless of source document variation. OpenAI schema can be generated automatically via OpenAI's structured output builder.

**Output**: Extracted patient data in JSON format matching the specified schema.

### 3. Data Mapping

**Concept**: Connect data fields from OpenAI response to Google Sheets columns:
- Map `patient_name` from OpenAI response → "Patient Name" column in Sheets
- Map `date_of_birth` → "Date of Birth" column
- Map `primary_diagnosis` → "Primary Diagnosis" column
- etc.

**Purpose**: Automation maps structured JSON fields to spreadsheet columns automatically, ensuring no manual entry.

### 4. Action: Google Sheets Integration

**Configuration**:
- Connect Google Sheets account (OAuth)
- Select spreadsheet containing medical records table
- Select sheet (tab) within spreadsheet
- System auto-detects column headers

**Mapping**: One-to-one mapping of OpenAI extracted fields to Sheets columns

**Action**: Adds new row with extracted data

**Result**: New patient record created in spreadsheet within seconds of file upload

---

## Real-World Validation

**Testing Procedure**:
1. Created sample medical report PDF (patient: "Demy User")
2. Changed Google Drive folder sharing to "anyone with link"
3. Built workflow with all three steps (Google Drive → OpenAI → Google Sheets)
4. Manually uploaded first test PDF
5. Verified response in Pabbly and data row appeared in Sheets within seconds
6. Uploaded second test PDF (patient: "Test User")
7. Waited for 10-minute polling interval
8. Verified second record automatically added to Sheets with all fields correctly extracted

**Results**:
- ✅ Medical report data extraction successful
- ✅ All patient fields extracted correctly
- ✅ Structured output consistency verified
- ✅ Google Sheets updated automatically
- ✅ Workflow fully automated end-to-end

---

## Technical Insights

### 1. Structured Output is Critical

Without a JSON schema, OpenAI responses vary in format and completeness. With structured output:
- Every response has same field names
- Type consistency (strings, dates, etc.)
- Easy mapping to spreadsheet columns
- No post-processing needed

**Comparison to medical_reader prototype**:
- Both use structured schemas (Pabbly: OpenAI native, medical_reader: Pydantic)
- Both validate extracted fields
- Pabbly delegates extraction to OpenAI; medical_reader adds custom validation layer

### 2. File Sharing for API Access

Key constraint: OpenAI needs public/shared URLs to access PDFs. Pabbly provides web view and download links, but **folder sharing permission must allow external access** for API calls to work.

**Security consideration**: Trade-off between API functionality and document privacy. Solution shown: "anyone with link" (no search indexing, requires explicit URL).

### 3. Polling-Based Triggers

Pabbly uses 10-minute polling intervals (free plan limitation). Means:
- Delay between file upload and workflow execution
- Not real-time, but acceptable for batch processing (diagnostic labs, clinics)
- Alternative: Webhook triggers (may require paid plan)

**vs. medical_reader prototype**: Medical reader was synchronous (instant); Pabbly is asynchronous (10-min delay)

### 4. Distributed Data Flow

Shown in description:
- After Google Sheets update, can trigger additional actions:
  - Send results to doctors via email
  - Send to patients via WhatsApp
  - Sync to CRM (Salesforce, HubSpot)
  - Alert via Slack/Teams

This is a **fan-out pattern**: one extraction → multiple downstream destinations.

---

## Comparison to DAC-UW-Agent Architecture

| Aspect | Pabbly Video | DAC-UW-Agent Medical Reader |
|--------|---|---|
| **Extraction Model** | OpenAI GPT-4 Vision | Claude Vision (hybrid LlamaParse + Claude) |
| **Structured Output** | OpenAI native JSON schema | Pydantic models |
| **Validation** | Relies on OpenAI schema | 3-layer validation (schema, domain, consistency) |
| **Orchestration** | Pabbly workflow (trigger-action) | LangGraph (state machine, pure functions) |
| **Execution Model** | Asynchronous polling (10 min) | Synchronous (invoke on demand) |
| **Error Handling** | Basic (step success/failure) | Custom routing (STP/human_review/reject) |
| **Audit Trail** | Limited (Pabbly logs) | Comprehensive (UnderwritingState immutable logs) |
| **Confidence Scoring** | None shown | Explicit 0.0-1.0 confidence scoring |

---

## Relevance to DAC-UW-Agent

### 1. **Document Processing Validation**

Pabbly approach confirms our strategy:
- ✅ LLM vision models (Claude/GPT-4V) are effective for medical PDFs
- ✅ Structured output (JSON schema) essential for consistency
- ✅ Need file sharing/URL access for API integration
- ✅ Confidence in approach: major platforms (Pabbly, OpenAI) use this pattern

### 2. **Operational Consideration: Polling vs. Real-Time**

Pabbly's 10-minute polling is a trade-off. For DAC-UW-Agent:
- Medical reader prototype handles files synchronously
- Phase 3 (Control Layer) should consider trigger mechanism:
  - Option A: Real-time webhook (when underwriter uploads doc)
  - Option B: Batch polling (periodic scan of intake folder)
  - Option C: Hybrid (high-priority webhook, background polling)

### 3. **Distributed Downstream Actions**

Pabbly shows fan-out pattern (extract → email/SMS/CRM). For DAC-UW-Agent:
- Phase 4 (Trust Layer) could implement:
  - Decision notification to underwriter (email/dashboard)
  - Applicant communication (SMS/email of decision)
  - CRM sync (store case outcome)
  - Audit log export (regulatory compliance)

### 4. **No Custom Validation Shown**

Pabbly relies entirely on OpenAI's structured output schema. DAC-UW-Agent goes further:
- Domain validation (BMI 10-60, BP 70-200)
- Consistency rules (Diabetes → glucose lab required)
- Custom confidence scoring
- Explicit rejection criteria

This suggests our 3-layer validation approach is a **competitive advantage** vs. simpler no-code solutions.

---

## Limitations & Gaps

### What Pabbly Video Doesn't Cover

1. **Data Quality Issues**
   - No handling of OCR failures or malformed PDFs
   - No fallback if OpenAI extraction is incomplete
   - No confidence scoring or retry logic

2. **Validation Beyond Schema**
   - Schema ensures types match, not medical plausibility
   - No checking for out-of-range values
   - No consistency checks between fields

3. **Regulatory Compliance**
   - No mention of audit trails or decision logging
   - No explainability (why did extraction succeed/fail?)
   - Limited error handling for sensitive medical data

4. **Scalability**
   - 10-minute polling not suitable for high-volume processing
   - No load balancing or async queue management
   - No mention of API rate limits or quota management

5. **Human Oversight**
   - No human-in-the-loop for uncertain extractions
   - Auto-updates Sheets with no review step
   - Assumes 100% accuracy (unrealistic for medical data)

**These gaps align with DAC-UW-Agent's Phases 3-4 (Control & Trust layers).**

---

## Key Takeaways

1. **Structured output is essential**: Define JSON schema upfront to get consistent extraction results
2. **File sharing required**: APIs need public URLs to access documents
3. **Validation critical**: Schema ensures type consistency, but domain validation (medical ranges, consistency rules) is separate concern
4. **No-code vs. code trade-off**: Pabbly is quick to build, but lacks custom validation and error handling needed for regulated industries
5. **Distributed architecture**: Extraction is one step; results flow to multiple destinations (Sheets → Email → CRM → Audit Log)

---

## Recommendations for DAC-UW-Agent

### Short-term (Before Friday)
- ✅ Validates our Claude Vision + structured output strategy
- ✅ Confirms medical data extraction via LLM is reliable
- ✅ Provides reference architecture for orchestration alternatives

### Medium-term (Phase 3-4)
- Consider webhook trigger pattern (more responsive than 10-min polling)
- Implement fan-out actions (notify underwriter, log decision, sync to CRM)
- Document trade-offs: real-time vs. polling, custom validation vs. schema-only
- Compare error handling: Pabbly's auto-retry vs. DAC-UW-Agent's explicit routing

### Research Angles
- **How do major insurers handle OCR failures?** Pabbly doesn't show this
- **What validation rules are needed beyond schema?** Medical domain expertise required
- **How to handle partial extraction?** (e.g., 8/12 fields extracted successfully)

---

## Related Wiki Topics

- [Document Extraction & Medical Parsing](../topics/document-extraction.md) — Practical example of extraction workflow
- [Medical Data Validation](../topics/medical-data-validation.md) — Gaps shown in Pabbly: need domain validation
- [Medical Reader Prototype](./medical-reader-prototype.md) — Our synchronous approach vs. Pabbly's async
- [Intelligent Document Processing](../topics/intelligent-document-processing.md) — IDP platforms compared
- [Agent Orchestration & Frameworks](../topics/agent-orchestration.md) — Pabbly's trigger-action vs. LangGraph's state machine

---

**Ingestion Date**: 2026-04-09  
**Status**: ✅ Validates existing architecture, highlights control/trust layer importance  
**Relevance**: HIGH (practical reference implementation for medical data extraction)
