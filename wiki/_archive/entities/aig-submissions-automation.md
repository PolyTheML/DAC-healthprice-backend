# AIG: Submission Analysis Automation Case Study

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Underwriting Automation Framework](../sources/2026-04-10_underwriting-automation-framework.md)

---

## Overview

**Company**: AIG (American International Group)  
**Program**: Agentic AI for Commercial Submissions  
**Use Case**: Processing complex commercial insurance applications  
**Result**: **370,000 submissions processed 5× faster (20-30 min vs. 2-4 hours)**

---

## Implementation Details

### Workflow Automation

```
Commercial submission (complex)
    ↓
AI agents:
  1. Document extraction (medical records, financials, policies)
  2. Risk classification (business risk analysis)
  3. Pricing recommendation (GLM + adjustments)
  4. Underwriter summary (1-page brief)
    ↓
Underwriter reviews + finalizes
    ↓
Quote generated + sent to broker
```

### Speed Improvement
- **Manual**: 2-4 hours (underwriter reads all documents, extracts key data, computes pricing)
- **AI-assisted**: 20-30 minutes (AI extracts + summarizes, underwriter focuses on judgment calls)

### Volume Impact
- **370,000 submissions** annually processed via AI (vs. impossible with manual process)
- **5× speedup** enables handling more business without hiring more underwriters

---

## Technology Stack

- **Document Processing**: LLM-based extraction (GPT-4 / Claude)
- **Risk Classification**: XGBoost model (trained on historical underwriting decisions)
- **Pricing Engine**: GLM (generalized linear model) + rider pricing
- **Agentic Coordination**: LangChain or similar orchestration framework
- **Storage**: Enterprise document management system

---

## Key Success Factors

### 1. Multi-Agent Orchestration
- Agent 1: Document processor (extract key fields from PDFs, contracts, emails)
- Agent 2: Risk classifier (assess business risk + loss history)
- Agent 3: Pricing engine (compute base premium + adjustments)
- Agent 4: Summary generator (write 1-page brief for underwriter)
- Orchestrator: Coordinate agents, manage state, escalate edge cases

### 2. Underwriter Trust
- AI summary gives underwriter everything needed (no re-reading documents)
- SHAP explainability: Show which factors drove risk classification
- Underwriter can override any decision (AI is advisory)

### 3. Scale
- 370K submissions annually = massive operational burden manually
- AI handles routine cases; underwriter focuses on judgment + exceptions
- Cost per submission: Reduced 60-70%

### 4. Regulatory Acceptance
- Agentic AI (transparent workflow) preferred over black-box ML
- Clear audit trail: Each agent's output logged
- Explainability at each step (document extraction → risk classification → pricing)

---

## Business Impact

### Financial Metrics
- **Time per submission**: 20-30 min (vs. 2-4 hours manual) = 4-8× speedup
- **Cost per submission**: Reduced $200 → $50 (75% savings on labor)
- **Volume increase**: 5× more submissions handled with same team
- **Revenue**: Additional $50M+ annual premiums from increased capacity

### Quality Metrics
- **Accuracy**: AI extract matches underwriter 92%+ of time
- **Consistency**: Pricing factors applied uniformly (less underwriter subjectivity)
- **Compliance**: 100% audit trail (vs. paper-based historical process)

---

## Lessons for DAC Integration

1. **Agentic AI Wins Over Point Solutions**
   - Single "extraction tool" insufficient; need orchestrated workflow
   - Multi-agent approach (intake → risk → price → summary) more powerful
   - DAC lesson: Build Command Center (Layer 4) to orchestrate sub-agents

2. **Underwriter Judgment Still Critical**
   - AI handles routine data gathering + analysis
   - Underwriter makes final judgment (coverage decision, exceptions)
   - DAC lesson: Human-in-the-loop essential; don't aim for 100% automation

3. **Explainability Drives Adoption**
   - Underwriters trust SHAP explainability ("Why this risk class?")
   - Clear summaries (AI does the reading; underwriter does the thinking)
   - DAC lesson: Invest heavily in explainability layer (Phase 2)

4. **Scale Benefits Compound**
   - 5× speedup at scale = massive cost savings + revenue growth
   - Worth investing in infrastructure + model quality
   - DAC lesson: Build for scale from day 1 (Kubernetes, async processing)

---

## Risks Encountered

| Risk | AIG's Mitigation |
|------|------------------|
| AI misses important risk factors in documents | Fallback to human review; feedback retrains extraction model |
| Underwriter doesn't trust AI risk class | Explainability dashboard; SHAP values prove fair reasoning |
| Regulatory audit of AI decisions | Complete audit trail; every decision step logged + traceable |
| Model drift (new submission types unseen in training) | Continuous monitoring; monthly retraining on latest submissions |

---

## Related Case Studies

- [Manulife MAUDE](./manulife-maude.md) (instant-issue, simpler)
- [Chubb AI Transformation](./chubb-ai-transformation.md) (end-to-end AI transformation)
- [Swiss Re Generative AI](./swiss-re-generative-ai.md) (GenAI for underwriting)

---

## Related Topics

- [Submission Analysis Workflow](../topics/underwriting-submission-analysis-workflow.md)
- [Tech Stack](../topics/underwriting-tech-stack.md)
- [DAC Integration](../topics/dac-underwriting-integration.md)
