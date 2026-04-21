# Swiss Re: Generative AI for Underwriting Assistants

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Underwriting Automation Framework](../sources/2026-04-10_underwriting-automation-framework.md)

---

## Overview

**Company**: Swiss Re (reinsurance + insurance major)  
**Program**: Generative AI underwriting assistant  
**Use Case**: Assist underwriters with document analysis + decision support  
**Result**: **50% reduction in manual workload**

---

## Implementation Details

### AI Assistant Role

```
Underwriter gets new submission
    ↓
AI Assistant (GenAI):
  1. Summarize application (key facts + risk profile)
  2. Identify missing information ("No recent medical exam; recommend")
  3. Suggest comparable cases ("Similar to case XYZ-001; rated +25%")
  4. Flag regulatory concerns ("High coverage; may trigger antitrust review")
  5. Recommend decision ("Approve substandard with +30% rating")
    ↓
Underwriter reviews AI recommendation + makes final decision
    ↓
Policy issued or escalated
```

### AI Augmentation
- AI doesn't make decisions
- AI provides decision support (summary + recommendation)
- Underwriter retains full control

### Workload Reduction
- **Manual analysis**: 45 min per case (read documents, extract info, research)
- **AI-assisted analysis**: 15 min per case (review AI summary + recommendation)
- **50% reduction** in manual workload

---

## Technology Stack

- **LLM**: Claude or GPT-4 (document understanding + recommendation generation)
- **Prompt Engineering**: Swiss Re-specific domain prompts
- **Integration**: API to existing underwriting system
- **Guardrails**: Constitutional AI to prevent hallucination

---

## Key Success Factors

### 1. AI as Copilot, Not Decision-Maker
- AI provides recommendations, underwriter decides
- Reduces bias (AI suggests, human approves)
- Easier regulatory acceptance (human remains accountable)

### 2. Explainable Recommendations
- AI shows reasoning: "Recommend substandard because [age + hypertension + high coverage]"
- Underwriter can agree/disagree with reasoning
- Feedback improves future recommendations

### 3. Domain-Specific Prompting
- General LLM insufficient
- Swiss Re-specific prompts (underwriting rules, rating factors, regulatory requirements)
- Continuously refined based on underwriter feedback

### 4. Human-AI Collaboration
- Underwriter can override AI (high confidence)
- AI learns from overrides (feedback retrains prompts/models)
- Iterative improvement cycle

---

## Business Impact

### Operational Metrics
- **Manual workload**: 45 min → 15 min per case (66% reduction)
- **Underwriter productivity**: 50% increase in cases reviewed
- **Underwriter satisfaction**: High (less drudgery, more decision-making)

### Financial Metrics
- **Cost per decision**: Reduced ~$100 (AI processing cost negligible)
- **Volume handling**: 50% more business with same team
- **Revenue**: Increased capacity → increased premium volume

---

## Lessons for DAC Integration

1. **Copilot Model Wins Over Automation**
   - AI + Human better than AI alone (for complex domains)
   - Reduces regulatory concerns
   - Higher underwriter adoption
   - DAC lesson: Design AI as assistant, not replacement

2. **Domain Expertise in Prompts**
   - GenAI needs domain-specific prompting
   - Simple prompts = poor results
   - Swiss Re invested in prompt engineering (hidden infrastructure)
   - DAC lesson: Budget for prompt engineering (Phase 2)

3. **Feedback Loop Critical**
   - Underwriter overrides AI → feedback improves AI
   - Track override rate (>20% = AI not trusted; <5% = AI over-trusted)
   - DAC lesson: Build feedback mechanism from day 1

---

## Risks Encountered

| Risk | Swiss Re's Mitigation |
|------|----------------------|
| AI hallucination (invents facts) | Always cite sources; underwriter verifies before acting |
| AI bias (systematic over/under-rates) | Monitor override patterns; feedback retrains prompts |
| Regulatory audit of AI-assisted decisions | Full audit trail; underwriter decision logged (not just AI recommendation) |

---

## Related Case Studies

- [AXA RAG + Agentic AI](./axa-rag-agentic-ai.md) (agentic approach)
- [Aviva Medical Underwriting](./aviva-medical-underwriting.md) (summarization focus)

---

## Related Topics

- [Tech Stack](../topics/underwriting-tech-stack.md) (LLM architecture)
- [DAC Integration](../topics/dac-underwriting-integration.md)
