# Lesson 1: Why OCR Fails & Why Agentic Reasoning Fixes It

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Document AI Course](../sources/2026-04-10_document-ai-course.md)

## The Core Problem: OCR ≠ Understanding

OCR (optical character recognition) extracts raw text from images. But extracting text is **not** the same as understanding meaning.

### Why Traditional OCR Pipelines Break

**Pipeline**: Image → OCR → Regex/Rules → Extraction

**Example failure** (from Lesson 1 invoice):
- OCR output: `tax at $125.50` (with "@" instead of space, due to noise)
- Regex looking for `tax $[0-9.]+` → **fails silently**
- Same document: subtotal appears first, total appears later
- Naive regex matches subtotal first → **wrong answer**

**Root cause**: Regex has no semantic understanding. It only pattern-matches strings. If OCR output changes even slightly (noise, layout shift, font), rules break.

### Why Regex Can't Handle Real Documents

1. **Semantic blindness**: Regex doesn't know "tax" refers to a tax line; it just sees letters
2. **Brittle on noise**: OCR errors (apostrophes instead of exponents, missing lines) cascade
3. **No context**: Can't distinguish "subtotal" from "total" without understanding document semantics
4. **No layout awareness**: Doesn't know if a number belongs to a table, margin, or footer

## The Agentic Solution

Instead of pre-written rules, **give the system reasoning capability**:

1. **Vision** (OCR): Extract raw text and bounding boxes
2. **Reasoning** (LLM): "What does this document mean? What is the question?"
3. **Tools** (Agent): Call OCR, parse markup, verify consistency, iteratively refine
4. **Observation**: Is the answer correct? Do I have enough context?

### Why This Works

- LLMs understand **semantics** ("revenue" and "net sales" mean the same thing)
- LLMs understand **context** (even noisy OCR text, LLM tries to infer intent)
- LLMs can **reason** across multiple pieces of information (sum tables, compare year-over-year)
- Agents can **self-correct** (if one approach fails, try another tool)

### Key Insight

> **Agentic document processing is "plan-act-observe-refine" in a loop, not a rigid pipeline.**

The agent sees the OCR output, reasons about what it likely means, calls specialized tools (tables, charts, text), and iteratively builds confidence in its answer until it meets a quality threshold.

---

## Conceptual Architecture

```
Raw Image
    ↓
[Vision] OCR + Layout Detection
    ↓
Structured Data (text + bounding boxes)
    ↓
[Reasoning] LLM Agent
    ├─ Interprets meaning
    ├─ Calls tools as needed
    ├─ Cross-checks answer
    └─ Reports confidence
    ↓
Grounded Answer
(with visual proof: "page 3, table 5, row 2")
```

---

## Relevance to DAC-UW

**Insurance underwriting documents** are perfect use cases:
- Identity docs (passports, driver licenses) → highly structured, but with noise, watermarks, wear
- Medical reports → mixed text/tables/handwriting; key fields buried in dense text
- Financial statements → tables with merged cells, footnotes, complex layouts
- Claims forms → variable layouts, handwritten annotations

An agentic approach would:
1. **Extract** identity features (name, DOB, issue date) despite occlusion/wear
2. **Reason** about medical findings ("hypertension" = high risk)
3. **Cross-check** financial data across multiple documents
4. **Flag** inconsistencies for human review

**vs. Rule-based approach**: Would require separate regex for every document type, break on layout changes, miss context.

---

## See Also

- [Lesson 2: OCR Evolution](./lesson-2-ocr-evolution.md) — How OCR got better over 40 years
- [Visual Grounding](./visual-grounding.md) — Why showing original pixels matters
- [Agentic Reasoning](./agentic-reasoning.md) — How agents plan-act-observe
