# PaddleOCR

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Type**: Deep learning OCR engine; open-source  
**Developed by**: Baidu

## Overview

PaddleOCR is a modern OCR system using **deep learning end-to-end** (text detection + recognition).

**Current version**: 3.0 (2025)  
**License**: Apache 2.0 (open source)  
**Language support**: 80+ languages  
**Repository**: [github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)

Represents the **2015+ deep learning paradigm** per [Lesson 2](../topics/lesson-2-ocr-evolution.md).

## Architecture (v3)

**Two-stage pipeline** (decoupled, independently optimizable):

1. **Text Detection** (DBNet: Differential Binarization Network)
   - Input: Image
   - Output: Bounding boxes around text regions
   - Learns to locate all text in image

2. **Text Recognition** (SVTR: Short Vision Transformer Recognizer)
   - Input: Cropped text region
   - Output: Recognized text string
   - Learns to read text in each region

**Additional modules**:
- **Layout Detection**: Classifies regions (text, table, figure, logo, margin, etc.)
- **Line Orientation Detection**: Auto-corrects rotated text
- **Preprocessing**: Auto-straightens documents

## Strengths

- ✅ **Real-world robustness**: Handles rotated, curved, low-quality text
- ✅ **Multi-language**: Supports 80+ languages automatically
- ✅ **GPU accelerated**: Fast with GPU; reasonable on CPU
- ✅ **Open source**: Free, modifiable, deployable on-premises
- ✅ **Layout detection**: Can classify region types
- ✅ **Lightweight variants**: PaddleOCR-lite for mobile/edge

## Limitations

- ❌ **Tables**: Struggles with dense tables (merged cells, no gridlines)
- ❌ **Reading order**: Multi-column docs still cause issues (doesn't understand document structure)
- ❌ **Handwriting**: Cursive, varied styles fail
- ❌ **Semantic understanding**: Recognizes text, but doesn't understand meaning
- ❌ **No visual grounding**: Doesn't link extracted text back to original context
- ❌ **Complex layouts**: Floating figures, sidebars, nested structures problematic

**Key insight from [Lesson 3](../topics/lesson-3-layout-and-reading-order.md)**: PaddleOCR solved OCR; it didn't solve **document understanding**.

## Accuracy

Per [Lesson 2](../topics/lesson-2-ocr-evolution.md) lab results:

**Clean documents**: ~95-98%  
**Real documents** (receipts, forms, photos): ~80-90%  
**Complex documents** (tables, multi-column): ~60-75%

Significantly better than Tesseract on real-world images, but still falls short for complex document understanding.

## Use Cases

**Good for**:
- Receipts and invoices (single-region, variable layouts)
- Signage and wayfinding
- Screenshots and UI text
- Scanned documents with noise/rotation
- Mobile photos
- Single-language focused pipelines

**Avoid for** (or handle separately):
- Dense financial tables → use layout detection + specialized table reader
- Handwritten forms → use Intelligent Character Recognition (ICR)
- Complex multi-column layouts → use agentic approach with [Visual Grounding](../topics/visual-grounding.md)
- Multi-column documents → use [LayoutReader](./layout-reader.md) for reading order
- Complex spatial reasoning → use vision-language models or [ADE](./agentic-document-extraction.md)

## Comparison to Alternatives

| System | Text Detection | Text Recognition | Layout Aware | Semantic | Best For |
|--------|----------------|------------------|--------------|----------|----------|
| **Tesseract** | Rule-based line finding | Hand-engineered classifier | No | No | Clean printed docs |
| **PaddleOCR** | DBNet (neural) | SVTR (neural) | Partial | No | Real-world OCR |
| **ADE** | DPT (vision-first) | DPT (vision-first) | Full | Yes | Document understanding |
| **EasyOCR** | CRAFT (neural) | CRNN (neural) | No | No | Quick prototyping |

## Deployment Options

1. **Local (on-premises)**:
   ```python
   from paddleocr import PaddleOCR
   ocr = PaddleOCR(use_angle_cls=True, lang='en')
   result = ocr.ocr('image.jpg')
   ```
   - Pros: No API costs, full privacy, instant
   - Cons: GPU/CPU needed, you maintain it

2. **Docker**:
   - Containerize PaddleOCR; deploy on K8s for scaling

3. **Cloud endpoint**:
   - Host on AWS/GCP/Azure; expose via API

## Relevant to DAC-UW

**Current role** (if adopted):
- First-pass text extraction for medical reports, financial statements
- Better than Tesseract for worn/scanned identity documents
- Can handle variable layouts (different insurers' forms)

**Limitations for insurance**:
- Still can't reliably extract structured data from complex forms
- No semantic understanding ("this field is risk-critical")
- Would need post-processing (regex, rules) to extract specific fields
- No visual grounding (can't prove where data came from)

**Better alternatives for DAC-UW**:
- Use PaddleOCR as building block within [ADE](./agentic-document-extraction.md)
- Or use ADE directly (handles everything end-to-end)

---

## See Also

- [OCR Evolution](../topics/lesson-2-ocr-evolution.md) — Historical context
- [Tesseract](./tesseract.md) — Previous generation
- [Agentic Document Extraction](./agentic-document-extraction.md) — Next generation
- [Layout Detection](./layout-detection.md) — Complements PaddleOCR
- [LayoutReader](./layout-reader.md) — Solves reading order problem
