# Lesson 4: Agentic Document Extraction (ADE) — Single API for Document Understanding

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Document AI Course](../sources/2026-04-10_document-ai-course.md)

## The Problem ADE Solves

Previous lessons showed the progression:
1. OCR extracts text (brittle, noisy)
2. Layout detection identifies regions (helps, but incomplete)
3. Reading order fixes sequencing (necessary but still not enough)
4. VLMs provide reasoning (powerful, but hallucinate on complex docs)

**Result**: Complex multi-stage pipelines that are:
- Hard to maintain (each component needs tuning)
- Brittle across edge cases (one stage's failure cascades)
- Difficult to scale (manual orchestration of 5+ models)

**ADE's answer**: **One unified API** that handles all steps end-to-end with quality guarantees.

---

## The Three Pillars of ADE

### 1. Vision-First

**Core insight**: Documents are *visual objects*, not just text.

**What this means**:
- Meaning is encoded in **layout** (where things are), **structure** (how they relate), **spatial relationships** (alignment, grouping)
- A table isn't "text with commas"; it's pixels arranged in rows and columns
- A form isn't "labels next to values"; it's visual alignment of elements

**Implication**: The foundation must be **document-native vision models**, trained specifically to *see documents the way humans do*.

### 2. Data-Centric

**Philosophy**: Model architecture matters, but **data quality is paramount**.

**What ADE does**:
- Trained on curated, high-quality annotated document datasets
- Not just any labeled data; documents representative of real-world complexity
- Continuous data collection and refinement (like Karpathy's autoresearch approach)

**Why it matters**: A perfectly designed architecture trained on garbage data produces garbage. Good architecture + good data = reliable system.

### 3. Agentic

**Agentic means**: The system plans, acts, observes, and iteratively refines until quality threshold is met.

**How ADE uses this**:
- **Plan**: "What type of document is this? What regions does it have?"
- **Act**: Route each region to appropriate handler (table-reader, chart analyzer, text extractor)
- **Observe**: "Do my answers make sense together? Are there inconsistencies?"
- **Refine**: Re-run uncertain extractions, cross-check values, verify consistency

**Unlike pipelines**: Agentic systems can handle novelty. If a document layout is unusual, the agent can reason about it instead of failing.

---

## The DPT Foundation

**DPT = Document Pretrained Transformer**

LandingAI released a family of vision models specifically trained on documents:
- **DPT-1** (earlier): Good for general-purpose documents
- **DPT-2** (current, 2025): State-of-the-art; handles complex layouts
- **DPT-2-mini** (lightweight): Fast, lower compute

**What DPT does**:
- Text detection (finds text regions)
- Text recognition (reads text in regions)
- Layout detection (labels regions as table, figure, text, etc.)
- Reading order detection (sequences regions correctly)
- Figure captioning (understands what's in images)
- All in a single model, trained together

**Key advantage**: Unlike PaddleOCR (which has separate det/rec models), DPT is end-to-end. Better coordination = fewer errors.

---

## The Output: Grounded, Structured Data

ADE's output is not just text; it's **richly structured**:

```json
{
  "chunks": [
    {
      "chunk_id": "abc123",
      "chunk_type": "table",
      "text": "[markdown table]",
      "bbox": [x1, y1, x2, y2],
      "page": 0,
      "confidence": 0.98
    },
    ...
  ],
  "markdown": "[complete document as markdown]",
  "splits": [...]  // per-page if requested
}
```

**Each chunk includes**:
- **text**: Clean markdown
- **chunk_id**: Unique identifier for visual grounding
- **chunk_type**: Semantic label (text, table, figure, attestation, etc.)
- **bbox**: Bounding box for cropping original image
- **page**: Which page this chunk came from
- **confidence**: Model's confidence in this extraction

### Why This Matters

Unlike traditional OCR (which just outputs text), ADE enables:
1. **Visual grounding** (link answer back to pixels)
2. **Type-aware downstream processing** (route tables to CSV export, figures to VLM)
3. **Confidence filtering** (only trust high-confidence extractions)
4. **Audit trails** (prove where information came from)

---

## Performance: 99.15% on DocVQA

ADE achieves **99.15% accuracy** on the DocVQA benchmark (question-answering on real scanned documents), exceeding all published models and human performance.

**DocVQA**: Benchmark with 500K+ real scanned documents from archives, with varied layouts, quality, languages.

**Why this matters**: Not a curated test set; real-world documents with occlusion, handwriting, low quality.

---

## Use Cases for ADE

### 1. Field Extraction (Key-Value Pairs)

**Problem**: Documents arrive with variable formats; need to extract specific fields.

**Example** (from Lesson 4 lab):
- Input: Utility bill (PDF)
- Schema: `{ account_number, current_charges, due_date, usage_chart_peak_month }`
- Output: Structured JSON with visual grounding for each field

**Why ADE wins**:
- No hand-coded parsing logic
- One API call; handles variable layouts
- Can extract from tables, charts, handwritten fields

### 2. RAG for Knowledge Assistants (Lesson 5)

**Problem**: Need to answer questions about multi-document datasets (financial filings, medical records, research papers).

**Example**: "What was Apple's net sales in 2023?" on a 74-page 10-K filing.

**Why naive RAG fails**:
- Pure text embedding loses layout context
- LLM can hallucinate when given noisy OCR
- No proof of where answer came from

**Why ADE + RAG works**:
- Clean text + bounding boxes → better embeddings
- Chunks are semantically coherent (table = one chunk, not scattered rows)
- Visual grounding proves answer (show the user the exact table)

---

## Relevance to DAC-UW

For insurance underwriting, ADE is a **game-changer**:

### Current State
- Manual document review (slow, error-prone)
- Rule-based extraction (breaks on new document types)
- No audit trail for extracted values

### With ADE

**Identity document processing**:
- Extract name, DOB, issue date from ID (despite watermarks, wear)
- Auto-detect document type (passport vs. driver license vs. national ID)
- Visual grounding for compliance ("here's where we got the birthdate")

**Medical history extraction**:
- Extract vital signs from tables (blood pressure, weight, etc.)
- Extract diagnoses from narrative text
- Identify risk factors mentioned in doctors' notes
- Link each extracted value to original pixels (audit trail)

**Financial verification**:
- Extract income from pay stubs (variable layouts across employers)
- Extract asset values from bank statements (handling multi-page, account transfers)
- Verify consistency across documents ("claimed income matches tax forms")

**Claims processing**:
- Auto-categorize claim documents (accident report vs. medical report vs. repair estimate)
- Extract key fields (date of incident, claimant name, damage amount)
- Handle handwritten notes and annotations
- Provide visual evidence for claim decisions

**Compliance & Audit**:
- Every extracted fact is grounded in pixels
- Trace back: "Decision made based on page 2, table 3, row 5"
- Regulatory proof: Can show auditors exactly where information came from

---

## The Trade-off: API-Based vs. Self-Hosted

**ADE is an API service** (cloud-based), unlike open-source tools (PaddleOCR):

| Aspect | ADE (API) | PaddleOCR (Open) |
|--------|-----------|-----------------|
| **Accuracy** | 99.15% (DocVQA) | ~85-90% (variable) |
| **Complexity** | Single API call | Multi-stage pipeline |
| **Cost** | Per-page API fee | Free (compute cost) |
| **Privacy** | Data sent to LandingAI | On-premises |
| **Latency** | Network latency | Instant (local) |
| **Maintenance** | None (vendor maintains) | You maintain model versions |

**For DAC-UW**: API model likely better because:
- Regulatory documents must be accurate (99% acceptable)
- Compliance > cost (audit trails, data governance)
- Scaling: Handle 1000s of documents monthly without maintaining ML infrastructure

---

## See Also

- [Agentic Reasoning](./agentic-reasoning.md)
- [Visual Grounding](./visual-grounding.md)
- [Lesson 5: RAG for Regulated Industries](./lesson-5-rag-for-document-understanding.md)
- [Entity: ADE (Agentic Document Extraction)](../entities/agentic-document-extraction.md)
