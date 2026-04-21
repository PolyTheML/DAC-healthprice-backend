# Layout Detection

**Type**: Document processing capability  
**Also known as**: Region classification, document structure analysis  
**Created**: 2026-04-10  
**Last updated**: 2026-04-10

## Definition

Layout detection is the process of identifying and classifying distinct regions within a document (text blocks, tables, figures, headers, footers, etc.) and their spatial relationships.

## Purpose

Documents are visual objects with **meaning encoded in structure**:
- A table's gridlines indicate rows/columns
- Text near the top usually is a header
- A figure caption explains the figure
- Footers often contain page numbers or disclaimers

Naive text extraction (OCR) ignores structure. **Layout detection** preserves it.

## Common Region Types

- **Text**: Body text (paragraphs, lists)
- **Table**: Structured data with rows/columns
- **Figure**: Charts, diagrams, images
- **Header/Footer**: Document metadata
- **Margin**: Whitespace, page numbers
- **Logo**: Branding elements

## Methods

### Rule-Based (Legacy)
- Look for gridlines, text alignment, whitespace patterns
- Fast but brittle; fails on unusual layouts

### Deep Learning (Modern)
- Train neural networks on annotated documents
- E.g., LayoutLMv3, DBNet (used in PaddleOCR v3)
- More robust but requires training data

### Vision-Language Models
- Use LLM with vision (Claude, GPT-4V) to reason about layout
- Flexible, handles novel documents
- Slightly slower but very accurate

## Output Format

Typically a bounding box per region:

```json
{
  "regions": [
    {"type": "header", "bbox": [10, 10, 190, 50]},
    {"type": "text", "bbox": [10, 60, 190, 300]},
    {"type": "table", "bbox": [10, 320, 190, 450]},
    {"type": "footer", "bbox": [10, 470, 190, 500]}
  ]
}
```

## Integration with Document Extraction

**Workflow**:
1. **Layout Detection** → Identify regions
2. **Region-Specific Extraction** → Use appropriate tool per region
   - Text regions → OCR or VLM
   - Tables → Table transformer (e.g., LayoutLMv3)
   - Figures → Figure analyzer (VLM + chart reader)
3. **Reassemble** → Reconstructed document with preserved structure

## Relevance to DAC-UW

Insurance documents are rich in structure:
- Identity documents: photo region, text fields, signature areas
- Medical reports: patient info, vital signs table, diagnoses narrative
- Financial statements: income summary tables, asset breakdowns

Accurate layout detection enables accurate field extraction.

## See Also

- [Lesson 3: Layout Detection & Reading Order](../topics/lesson-3-layout-and-reading-order.md)
- [Document Extraction & Medical Parsing](../topics/document-extraction.md)
- [PaddleOCR](./paddleocr.md) — Includes layout detection module
