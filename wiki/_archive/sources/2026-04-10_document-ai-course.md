# Document AI Course: From OCR to Agentic Document Extraction

**Source**: Lesson videos + labs from LandingAI/AWS collaborative course  
**Ingested**: 2026-04-10  
**Course Length**: 6 lessons + hands-on labs  
**Key Provider**: LandingAI (agentic document extraction) + AWS (production deployment)  
**Related Topics**: [Agentic Reasoning](../topics/agentic-reasoning.md), [Document Extraction & Medical Parsing](../topics/document-extraction.md), [Visual Grounding](../topics/visual-grounding.md)

## Overview

A comprehensive course on modern document intelligence, spanning the evolution from traditional OCR to vision-first agentic systems. Emphasis on why each architectural phase emerged and the conceptual reasoning behind agentic approaches.

**Core argument**: Document understanding is fundamentally a *vision* + *reasoning* problem, not just text extraction. Agentic systems solve this by combining visual grounding with iterative refinement.

## Lessons Covered

1. **Lesson 1: Agentic Document Processing Basics** — Why OCR+regex fails; how to layer reasoning on top
2. **Lesson 2: Four Decades of OCR Evolution** — From hand-engineered features (Tesseract) to deep learning (PaddleOCR)
3. **Lesson 3: Layout Detection & Reading Order** — Why structure matters; vision-language models vs. pure OCR
4. **Lesson 4: Agentic Document Extraction (ADE)** — Single unified API replacing multi-stage pipelines
5. **Lesson 5: RAG for Document Understanding** — Embedding, vector search, and grounding for regulated industries
6. **Lesson 6: Production Deployment on AWS** — Event-driven serverless architecture with Bedrock

## Key Themes

- **Evolution**: Rule-based → Statistical → Deep learning → Agentic (vision-first)
- **Vision-First Paradigm**: Documents are visual objects; meaning is encoded in layout, not just text
- **Grounding**: Every extracted fact must link back to original pixels (audit trail, trust, compliance)
- **Agentic Reasoning**: Plan-act-observe loops replace rigid pipelines; system can handle novel layouts

## Relevance to DAC-UW

**Potential applications**:
- Identity document parsing (passports, driver licenses, national IDs) with tamper detection
- Medical report extraction (structured/unstructured health histories)
- Financial statement analysis (income verification, asset statements)
- Claims document processing (variable layouts, handwriting, mixed media)
- Compliance & audit trails (grounded visual evidence for underwriting decisions)

---

## Document Metadata

- **Total Content**: ~50K tokens across video transcripts
- **Practical Labs**: 4 (Lesson 1, 2, 3, 4) + production lab (Lesson 6)
- **Code Examples**: Python (LangChain, PaddleOCR, OpenAI, AWS SDK)
- **Frameworks**: LangChain, Strands Agents, Bedrock, ChromaDB
- **Models**: GPT-4o-mini, Text-Embedding-3-Small, Claude (Bedrock), DPT-2 (LandingAI)
