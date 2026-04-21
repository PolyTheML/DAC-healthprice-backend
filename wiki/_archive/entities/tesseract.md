# Tesseract OCR

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Type**: Open-source OCR engine (traditional rule-based approach)

## Overview

Tesseract is a classic optical character recognition (OCR) engine representing the **1980s-2000s paradigm** of hand-engineered computer vision.

**Current version**: 5.x (2025), maintained by Google  
**License**: Open source (Apache 2.0)  
**Language support**: 100+ languages

## History

- **1980s-1990s**: Proprietary (Hewlett Packard)
- **2005**: Released open source
- **Today**: Maintained by Google; widely used in legacy systems

Per [Lesson 2](../topics/lesson-2-ocr-evolution.md), Tesseract represents the first era of OCR: hand-engineered features and procedural pipelines.

## Architecture

**Pipeline**:
1. **Line finding**: Detect horizontal text lines
2. **Word segmentation**: Split lines into words
3. **Character classification**: Identify individual characters
4. **Post-processing**: Dictionary lookup, heuristics

**Approach**: Every step is explicitly coded and tuned. No machine learning for core recognition (though recent versions add some deep learning).

## Strengths

- ✅ **Clean printed documents**: Excels on books, newspapers, scanned text
- ✅ **Resource-efficient**: CPU-only; no GPU needed
- ✅ **Lightweight**: Single binary; minimal dependencies
- ✅ **Mature**: Stable, well-tested, widely adopted
- ✅ **Open source**: No licensing costs

## Limitations

- ❌ **Text-in-the-wild**: Fails on rotated, curved, low-contrast text
- ❌ **Real documents**: Poor on receipts, forms, signs, handwriting
- ❌ **No semantic understanding**: Just pattern-matches character shapes
- ❌ **Layout awareness**: Treats document as sequence of lines, not structure
- ❌ **Brittle on noise**: OCR errors cascade (one wrong character breaks regex downstream)

## Use Cases

**Good for**:
- Digitizing scanned books (black text on white)
- Historical documents (with clean quality)
- Document archive projects
- When accuracy on clean text > handling real-world variability

**Avoid for**:
- Mobile photos, screenshots
- Receipts, invoices, forms
- Mixed text/images
- Handwriting
- Multilingual documents with scripts

## Comparison to Modern Systems

| Aspect | Tesseract | PaddleOCR | ADE |
|--------|-----------|-----------|-----|
| **Paradigm** | Hand-engineered rules | Deep learning (CNN) | Vision-first agentic |
| **Accuracy (clean text)** | ~98% | ~95% | ~99% |
| **Accuracy (real docs)** | ~60% | ~85% | ~99% |
| **Layout awareness** | No | Partial | Full |
| **Table handling** | Poor | Fair | Excellent |
| **Speed** | Fast (CPU) | Medium (GPU) | Slower (API) |
| **Deployment** | Local binary | Local/Docker | Cloud API |

Per [Lesson 2](../topics/lesson-2-ocr-evolution.md), Tesseract represents an **evolutionary dead-end** for modern document AI. Deep learning didn't build on Tesseract; it replaced it with fundamentally different architecture.

## Relevance to DAC-UW

For insurance documents, Tesseract alone would be **insufficient**:
- Identity docs (worn, watermarked) → too noisy
- Medical records (mixed printed/handwritten) → fails on handwriting
- Financial statements (complex tables) → poor layout handling

**Could use for**: Basic document pre-processing (text detection) as input to better system, but better to skip directly to [PaddleOCR](./paddleocr.md) or [ADE](./agentic-document-extraction.md).

## Related

- [OCR Evolution](../topics/lesson-2-ocr-evolution.md)
- [PaddleOCR](./paddleocr.md) — Next evolution
- [Agentic Document Extraction](./agentic-document-extraction.md) — Modern approach
