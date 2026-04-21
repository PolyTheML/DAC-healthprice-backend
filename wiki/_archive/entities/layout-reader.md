# Layout Reader (Reading Order Detection)

**Type**: Document processing capability  
**Also known as**: Reading order detection, document structure understanding  
**Related to**: [Layout Detection](./layout-detection.md)  
**Created**: 2026-04-10  
**Last updated**: 2026-04-10

## Definition

**Reading order detection** determines the correct sequence in which a human should read document regions to understand content.

**Problem it solves**: OCR returns regions in visual order (top-to-bottom, left-to-right), but documents often have complex layouts where visual order ≠ logical order.

## Example: Multi-Column Layout

Visual layout:
```
┌──────────────────────────────────────┐
│ Title                                 │
├─────────────┬──────────────────────┤
│ Column 1    │ Column 2             │
│ Para 1      │ Para 2               │
│             │ Para 3               │
│ Figure A    │                      │
└─────────────┴──────────────────────┘
```

**Visual order** (top-to-bottom, left-to-right):
1. Title
2. Column 1 Para 1
3. Column 2 Para 2
4. Column 1 Figure A
5. Column 2 Para 3

**Logical order** (what humans read):
1. Title
2. Column 1: Para 1 → Figure A
3. Column 2: Para 2 → Para 3

Reading order detection outputs: [Title, Col1-Para1, Col1-FigureA, Col2-Para2, Col2-Para3]

## How It Works

### Deep Learning Approach
- Train on documents with annotated reading order
- Model learns patterns: "Text in left column comes before right column"
- Outputs sequence of region IDs

### Vision-Language Model Approach
- Show LLM the layout (bounding boxes + region types)
- Ask: "In what order should I read these regions?"
- LLM reasons: "Column 1 top, then Column 2, then footnotes"

## Output Format

Ordered list of region indices:

```json
{
  "reading_order": [0, 1, 3, 2, 4],
  "regions": [
    {"id": 0, "type": "header", "text": "Title"},
    {"id": 1, "type": "text", "text": "Column 1 Para 1"},
    {"id": 2, "type": "text", "text": "Column 2 Para 2"},
    {"id": 3, "type": "figure", "text": "Figure A"},
    {"id": 4, "type": "text", "text": "Column 2 Para 3"}
  ]
}
```

## Integration with Document Processing

**Workflow**:
1. [Layout Detection](./layout-detection.md) → Identify regions + bounding boxes
2. **Reading Order Detection** → Determine sequence
3. Region-specific extraction (text, table, figure per region)
4. **Reconstruction** → Reassemble in logical order

Result: Clean markdown or JSON that preserves document structure.

## Challenges

- **Nested layouts**: Headers, footnotes, sidebars within columns
- **Non-linear reading**: Some documents intentionally jump around (e.g., scientific papers: intro → figures → results)
- **Forms**: Field order may not match visual order
- **Rotated/scanned**: May need to handle 90°/180° rotations

## Relevance to DAC-UW

Medical documents often have complex layouts:
- **Forms**: Fields in visual order ≠ extraction order (patient info, vital signs, diagnoses, signature)
- **Reports**: Narrative + embedded tables + lab results (all mixed)
- **Multi-page**: Information scattered across pages

Accurate reading order ensures extracted data appears in logical sequence, reducing post-processing.

## See Also

- [Lesson 3: Layout Detection & Reading Order](../topics/lesson-3-layout-and-reading-order.md)
- [Layout Detection](./layout-detection.md)
- [Document Extraction & Medical Parsing](../topics/document-extraction.md)
- [PaddleOCR](./paddleocr.md) — Includes reading order detection
