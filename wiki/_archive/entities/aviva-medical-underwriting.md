# Aviva: Medical Underwriting Summarization

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Underwriting Automation Framework](../sources/2026-04-10_underwriting-automation-framework.md)

---

## Overview

**Company**: Aviva (major UK life insurer)  
**Program**: AI-powered medical record summarization  
**Use Case**: Complex medical record review (life + critical illness insurance)  
**Result**: **50% reduction in underwriter review time; £100M claims savings**

---

## Implementation Details

### Workflow

```
Medical records received (5-20 pages)
    ↓
AI system:
  1. Extract key medical facts (diagnoses, treatments, outcomes)
  2. Identify risk factors (comorbidities, medication adherence)
  3. Generate 1-page summary (key facts + risk implications)
    ↓
Underwriter reviews 1-page summary (vs. full 20-page file)
    ↓
Decision: Approve/Substandard/Decline
```

### Time Savings
- **Manual**: 30-45 min per file (read full medical record, extract key info)
- **AI-assisted**: 10-15 min per file (read 1-page summary, same decision quality)
- **Scale**: 1000+ cases annually → 20,000+ hours saved

---

## Technology Stack

- **Document Processing**: LLM-based extraction (Claude/GPT-4)
- **Medical Knowledge**: Medical terminology NLP (MeSH, ICD-10)
- **Risk Scoring**: Domain-specific ML model (trained on Aviva medical decisions)
- **Summarization**: Template-based synthesis (key facts + risk implications)

---

## Key Success Factors

### 1. Medical Domain Expertise
- Summaries written in medical/underwriting language (not plain English)
- Key facts highlighted (e.g., "HbA1c = 8.2%, indicating suboptimal diabetes control")
- Risk implications explicit (e.g., "Diabetes increases mortality 3-5×; likely substandard")

### 2. Template-Based Summarization
- Not free-form text; structured format
- Section 1: Diagnosis & treatment history
- Section 2: Current status (medications, recent exams)
- Section 3: Risk assessment (underwriter can quickly decide)

### 3. Confidence Scoring
- AI flags cases with low extraction confidence
- Underwriter should double-check if confidence <85%
- Builds trust (system doesn't over-promise)

### 4. Feedback Loop
- Underwriter reviews summary + compares to original file
- Provides feedback if summary missed important fact
- Feedback retrains model (continuous improvement)

---

## Business Impact

### Operational Metrics
- **Review time per case**: 45 min → 15 min (66% reduction)
- **Cases processed daily**: 10 → 30 per underwriter (3× increase)
- **Underwriter satisfaction**: High (less tedious work, more decision-making)

### Financial Metrics
- **Claims savings**: £100M annually
  - Better risk assessment → fewer adverse claims
  - Faster processing → earlier claim detection
- **Underwriter productivity**: Worth £2-3M annually in reduced labor

---

## Lessons for DAC Integration

1. **Domain Expertise in Prompts**
   - Aviva's summaries are medical + underwriting language
   - Not generic summaries; specialized for decision-making
   - DAC lesson: Fine-tune prompts for Cambodian health context (local disease prevalence, treatment standards)

2. **Structured Output Format**
   - Not free-form text; fixed sections
   - Easier to extract key facts from structured format
   - DAC lesson: Define underwriter summary template (Phase 1)

3. **Confidence Scoring Essential**
   - AI should say "I'm 92% confident" not just provide summary
   - Low confidence → underwriter double-checks
   - DAC lesson: Build confidence scoring into extraction layer (Layer 1)

---

## Risks Encountered

| Risk | Aviva's Mitigation |
|------|-------------------|
| AI misses critical medical fact | Confidence scoring; underwriter spot-checks summaries |
| Medical terminology misunderstood | Medical NLP fine-tuning; domain expert review |
| Regulatory audit of AI decisions | Full audit trail; AI summary + original file both stored |

---

## Related Case Studies

- [AXA RAG + Agentic AI](./axa-rag-agentic-ai.md) (knowledge synthesis at scale)
- [Swiss Re Generative AI](./swiss-re-generative-ai.md) (GenAI for underwriting)

---

## Related Topics

- [Submission Analysis Workflow](../topics/underwriting-submission-analysis-workflow.md)
- [Tech Stack](../topics/underwriting-tech-stack.md)
- [DAC Integration](../topics/dac-underwriting-integration.md)
