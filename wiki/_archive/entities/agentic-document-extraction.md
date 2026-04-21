# Agentic Document Extraction (ADE)

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Type**: Cloud API service for document understanding  
**Provider**: LandingAI  
**Website**: [va.landing.ai](https://va.landing.ai)

## Overview

ADE is a unified API service for parsing and understanding documents at production scale.

**Core thesis**: Instead of assembling complex multi-stage pipelines (OCR → Layout → Reading Order → VLM), use a single API that handles everything end-to-end with quality guarantees.

**Accuracy**: 99.15% on DocVQA benchmark (exceeds human performance and all published models)

---

## The Three Pillars of ADE

Per [Lesson 4](../topics/lesson-4-agentic-document-extraction.md):

### 1. Vision-First

Documents are **visual objects**. Meaning is encoded in layout, structure, spatial relationships.

- Foundation: Document-native vision models (DPT family)
- Approach: Learn visual patterns from high-quality document training data
- Not text-first; vision is primary

### 2. Data-Centric

Model architecture matters, but **data quality is paramount**.

- Trained on curated, representative documents
- Not just labeled data; high-quality, diverse, real-world documents
- Continuous improvement through data collection and refinement

### 3. Agentic

System **plans, acts, observes, and refines** iteratively.

- Not a rigid pipeline; adaptive reasoning
- Routes regions to appropriate specialized handlers
- Verifies consistency across extracted fields
- Iterates until quality threshold met

---

## Document Pretrained Transformer (DPT) Models

ADE is powered by DPT family, vision models trained specifically on documents:

### DPT-1
- Earlier generation
- Good general-purpose document understanding
- Faster inference

### DPT-2 (Current, 2025)
- State-of-the-art
- Handles complex layouts, dense tables, handwriting
- Better field extraction

### DPT-2-mini
- Lightweight variant
- Good for cost-sensitive applications
- Faster on edge devices

**What DPT does** (all in single model):
- Text detection
- Text recognition
- Layout detection (labels regions as table, figure, text, etc.)
- Reading order detection
- Figure captioning
- Confidence scoring

**Why single model better**: Components trained together → fewer handoff errors, better coordination.

---

## API Endpoints

### 1. Parse

**Input**: Document (PDF, image, spreadsheet)  
**Output**: Structured data

```json
{
  "chunks": [
    {
      "chunk_id": "abc123",
      "chunk_type": "table",
      "text": "[markdown content]",
      "bbox": [x1, y1, x2, y2],
      "page": 0,
      "confidence": 0.98
    }
  ],
  "markdown": "[complete document as markdown]",
  "splits": [...]  // per-page if requested
}
```

**Use cases**:
- Convert PDF to clean markdown
- Identify document structure
- Extract all content with visual grounding

### 2. Extract

**Input**: Document + JSON schema (field definitions)  
**Output**: Structured JSON matching schema

```json
{
  "account_number": "12345",
  "current_charges": 155.15,
  "due_date": "2025-05-01",
  "usage_peak_month": "January"
}
```

**Use cases**:
- Key-value pair extraction
- Form field extraction
- Structured data from variable documents

### 3. Split

**Input**: Large document (100s-1000s of pages)  
**Output**: Document broken into logical sections

**Use cases**:
- Pre-process massive PDFs before indexing
- Extract sections separately

---

## Output Features

### Rich Metadata

Every extracted chunk includes:
- `chunk_id`: Unique identifier
- `chunk_type`: Semantic label (text, table, figure, attestation, logo, margin, footer)
- `text`: Clean markdown
- `bbox`: Bounding box for visual grounding
- `page`: Page number
- `confidence`: Model confidence

### Visual Grounding

**Key differentiator**: Every chunk has bounding box → can generate cropped image.

```
Extracted text: "Net sales $383B"
Bounding box: [x1, y1, x2, y2]
Cropped image: [visual proof]
```

**Why crucial for regulated industries**:
- Compliance: Auditor asks "where did you get this?" → Show them the exact pixels
- Trust: Users can verify answers
- Liability: Documented decision trail

### Confidence Scores

Model returns confidence for each extraction.

- High confidence (0.95+): Trust it
- Medium confidence (0.7-0.95): Flag for review
- Low confidence (<0.7): Require human verification

---

## Benchmark Results

**DocVQA** (document question-answering):
- Task: Answer questions about real scanned documents (UCSF Industry Documents Library)
- ADE accuracy: **99.15%** (exceeds all published models and human performance)
- Importance: Real documents with occlusion, handwriting, low quality (not curated test set)

---

## Pricing Model

- **Per-page pricing**: $0.00075 per page parsed
- **Free tier**: 1,000 free pages/month (generous for evaluation)
- **Bulk discounts**: Available for high-volume users
- **No contract locks**: Pay as you go

**For DAC-UW**:
- 100 documents/month (~500 pages) → ~$0.38/month (minimal)
- 10,000 documents/month (~50K pages) → ~$37.50/month (very affordable)
- Includes all features (parse, extract, split, visual grounding)

---

## Use Cases

### 1. Field Extraction (Key-Value Pairs)

**Problem**: Documents arrive with variable formats; need specific fields.

**Example**: Extract from utility bills, loan applications, medical records

**ADE advantage**: 
- One API; handles variable layouts
- Returns extracted fields + visual grounding
- No hand-coded parsing logic needed

### 2. RAG for Knowledge Assistants

**Problem**: Answer questions on multi-document datasets (financial filings, medical records, research papers)

**ADE advantage**:
- Parse generates clean, structured text (not noisy OCR)
- Visual grounding links answers back to pixels
- Chunks have semantic boundaries (tables stay together, not scattered)

Per [Lesson 5](../topics/lesson-5-rag-for-document-understanding.md), clean parsing is **prerequisite** for reliable RAG.

### 3. Document Classification

**Problem**: Incoming documents are of unknown types; need to route to appropriate processing.

**Example**: Automatically detect "passport vs. driver license vs. national ID"

**ADE advantage**: Can extract document metadata (issuing country, issue date) to classify.

### 4. Automated Workflow

**Problem**: High-volume document processing (100K docs/year). Need to automate extraction.

**Example**: Insurance claims processing, bank account opening

**ADE advantage**:
- Integrates with Lambda (Lesson 6) for event-driven processing
- Scales automatically
- Provides audit trail (who extracted what, when)

---

## Relevance to DAC-UW: Application Scenarios

### Identity Document Processing

**Document types**: Passport, driver license, national ID, visa pages

**Extract**:
- Full name, date of birth, issue date, expiry date
- Issuing country/state
- Document number
- Photo verification (detect face in biometric section)

**ADE advantages**:
- Handles variable layouts (different countries' formats)
- Works on worn, scanned, mobile photos
- Returns visual grounding (exactly where birthdate came from)
- Confidence scores (flag low-confidence extractions)

### Medical History Extraction

**Document types**: Medical reports, lab results, prescription records, doctor's notes

**Extract**:
- Chief complaints, diagnoses, vital signs, lab values
- Medication list (name, dosage, frequency)
- Allergies, pre-existing conditions
- Risk factors (obesity, hypertension, diabetes)

**ADE advantages**:
- Handles mixed printed/handwritten
- Can extract from tables (vital signs) and narrative (diagnoses)
- Links each extraction to source page

### Financial Verification

**Document types**: Pay stubs, tax returns, bank statements, investment account statements

**Extract**:
- Income (gross, net, YTD)
- Account balances, transaction history
- Asset types and values
- Liabilities

**ADE advantages**:
- Handles complex tables (multi-account statements)
- Extracts across multiple pages
- Visual proof for audit

### Claims Assessment

**Document types**: Claim forms, medical reports, police reports, repair estimates, receipts

**Extract**:
- Incident date, claimant info, damage/injury description
- Medical findings, prognosis
- Estimated repairs/loss amount
- Supporting documentation references

**ADE advantages**:
- Handles variable form layouts
- Works on handwritten annotations
- Provides visual evidence for claim decisions

---

## Comparison: ADE vs. DIY Pipelines

| Aspect | ADE API | DIY (PaddleOCR + LayoutReader + VLM) |
|--------|---------|--------------------------------------|
| **Setup time** | 5 min (sign up, get API key) | Weeks (integrate components) |
| **Accuracy** | 99.15% (DocVQA) | 80-90% (variable) |
| **Maintenance** | Zero (vendor maintains) | Ongoing (model versions, bugs) |
| **Scaling** | Automatic | Requires infrastructure |
| **Visual grounding** | Built-in | Must implement manually |
| **Cost (high volume)** | ~$0.75 per page | $0.10-0.50 compute per page |
| **Time-to-value** | Days | Months |

**For DAC-UW**: API model is likely **better choice**:
- Regulatory documents must be accurate (99% acceptable)
- Compliance & audit > cost savings
- Faster time-to-market
- No ML infrastructure to maintain

---

## Constraints & Limitations

### What ADE Does Well
- ✅ Text extraction (printed & handwritten)
- ✅ Layout detection & reading order
- ✅ Table structure preservation
- ✅ Form field extraction
- ✅ Visual grounding

### What ADE Doesn't Do
- ❌ Domain-specific reasoning ("is this applicant risky?")
- ❌ Policy enforcement ("applicant must have income > $50K")
- ❌ Image verification (detecting fake documents, tampering)
- ❌ Biometric matching (comparing photo to ID)

**Implication for DAC-UW**: ADE is **information extraction**; you need separate underwriting rules and risk models.

---

## Integration with DAC-UW Architecture

**Where ADE fits**:

```
DAC-UW Four-Layer Architecture
├── Layer 1: Intake (Document Collection)
│   └── ADE parses documents → structured data
├── Layer 2: Brain (Underwriting Logic)
│   └── Use ADE-extracted fields as inputs
├── Layer 3: License (Compliance Check)
│   └── Visual grounding proves audit trail
└── Layer 4: Command Center (Dashboard)
    └── Display extracted fields + source images
```

**Typical workflow**:
1. Applicant uploads documents (identity, medical, financial)
2. ADE API parses them (automated)
3. Extracted fields stored in DB
4. Underwriting rules applied (manual or automated)
5. Visual grounding displayed for review/audit

---

## See Also

- [Lesson 4: Agentic Document Extraction](../topics/lesson-4-agentic-document-extraction.md)
- [Lesson 5: RAG for Document Understanding](../topics/lesson-5-rag-for-document-understanding.md)
- [Lesson 6: Production Deployment on AWS](../topics/lesson-6-production-aws-deployment.md)
- [Visual Grounding](../topics/visual-grounding.md)
