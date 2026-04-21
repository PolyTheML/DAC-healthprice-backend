# Lesson 3: Layout Detection & Reading Order — Why Structure Matters

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Document AI Course](../sources/2026-04-10_document-ai-course.md)

## The Core Problem: Text Extraction Is Destructive

**The naive pipeline** (from Lesson 1-2):
1. Extract all text from document
2. Flatten into a single sequence
3. Pass to LLM to answer questions

**What gets lost**:
- Column alignment (multi-column docs read across instead of down)
- Table structure (rows/columns become a jumbled text blob)
- Captions & figures (relationship between image and text severed)
- Reading order (which text should be read first?)
- Spatial context (is a number in a table, margin, or footnote?)

**Example** (from Lesson 3): Academic paper with 2-column layout
- OCR reads left column, then right column, but **continues across** (left-top → right-top → left-next → right-next)
- Result: "in most of the westernized countries that system based on some of the interview" (nonsense)
- **Should be**: All of left column, then all of right column

---

## The Vision-Language Model Insight

**Why pure text extraction fails on complex documents:**

Traditional LLMs see only text tokens. They're **blind to visual structure**.

```
Visual Document          →  Text Extraction      →  LLM (blind)
[Multi-column layout]      [flattened sequence]     "Just words;
[with table]               [jumbled reading]        can't see layout"
[with caption]             [no structure]
```

**Vision-Language Models (VLMs)** add a vision encoder:

```
Visual Document          →  Vision Encoder       →  LLM (sees meaning)
[pixels + structure]        [embeddings]            "Understands that this
[layout info]               [layout understood]     text is in a table,
[spatial cues]              [spatial awareness]     this is a caption"
```

**What changed**: VLMs can *see* the document as a human does.

---

## The Reading Order Problem

Documents don't always follow top-to-bottom, left-to-right order. Examples:
- **Multi-column** (read left column top-to-bottom, then right column)
- **Tables** (rows and columns form a matrix, not a sequence)
- **Captions** (figure on top, caption on bottom)
- **Sidebars** (asides that interrupt main text)

### Why Heuristics Fail

Old approach: Sort text regions by (x, y) coordinates using heuristics (e.g., "top-to-bottom, left-to-right").

**Problem**: Heuristics break on non-standard layouts. No rule works for all cases.

### The Learned Solution: LayoutReader

**LayoutReader** (Microsoft LayoutLMv3 + ReadingBank dataset):
- Trained on **500,000 annotated documents** with correct reading sequences
- Input: OCR bounding boxes + layout features
- Output: Predicted reading order for each text region
- Handles: Multi-column, tables, mixed layouts, floating elements

**Key insight**: Reading order is **learnable from data**, not hand-coded.

---

## Why Layout Detection Matters

Beyond reading order, documents have **region types**:
- Text blocks
- Tables
- Figures
- Charts
- Captions
- Headers/footers
- Logos
- Attestations (stamps, signatures)

**Why**: Downstream processing differs by type.

**Example**:
- Chart → send to VLM for trend analysis
- Table → send to specialized table-reader
- Text → can use OCR alone
- Figure → needs figure captioning

**Old pipeline**: One-size-fits-all (just extract text)  
**New pipeline**: Route regions to appropriate tools

---

## The Hybrid Architecture

Lesson 3 introduces a **hybrid** approach:

1. **Layout Detection** (PaddleOCR LayoutDetect): Identify region types & boundaries
2. **Reading Order** (LayoutReader): Order regions correctly
3. **Type-Specific Tools**:
   - Charts → VLM (Claude/GPT) for interpretation
   - Tables → Table Transformer for structure
   - Text → OCR
   - Figures → Caption generator
4. **Agentic Orchestration** (LangChain): Decide which tool to use for which region

**Visual metaphor**: Like a human analyst scanning a complex report:
1. First scan the structure ("there's a chart here, table there")
2. Decide reading order ("start with title, then executive summary")
3. Dive deep ("zoom in on the chart, extract precise numbers")

---

## Limitations & Next Steps

Even with layout detection + reading order, **challenges remain**:

1. **Dense tables** (merged cells, no gridlines) → VLMs still hallucinate
2. **Nested structures** (table inside figure, caption with variables)
3. **Multi-page documents** → need page-aware reasoning
4. **Domain-specific semantics** → "this risk metric matters for underwriting"

**Solution**: [Lesson 4](./lesson-4-agentic-document-extraction.md) — **Agentic Document Extraction (ADE)**
- Unifies all the above steps (layout, reading order, table extraction, etc.)
- Adds **iterative refinement** (agent verifies its own answers)
- Grounded outputs (every fact links to original pixels)

---

## Relevance to DAC-UW

Insurance documents are **layout-heavy**:

**ID documents** (passport, driver license):
- Multi-region: photo, text fields, machine-readable zone
- Reading order: Should extract name/DOB from readable text, not from barcode

**Medical reports**:
- Mixed tables (vital signs) and narrative (diagnosis)
- Figures (X-rays, lab results as images)
- Captions linking figures to findings

**Financial statements**:
- Dense tables with merged headers
- Year-over-year columns
- Footnotes with critical caveats

**Current challenge**: Rule-based extraction assumes fixed layouts  
**Why it breaks**: Each insurance product, each country's documents have different layouts  
**Agentic solution**: Learns layout understanding; adapts to new formats

---

## See Also

- [Layout Detection](../entities/layout-detection.md)
- [LayoutReader](../entities/layout-reader.md)
- [Visual Grounding](./visual-grounding.md)
- [Lesson 4: Agentic Document Extraction](./lesson-4-agentic-document-extraction.md)
