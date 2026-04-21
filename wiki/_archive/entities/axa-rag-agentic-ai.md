# AXA: RAG + Agentic AI for Underwriting & Claims

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Underwriting Automation Framework](../sources/2026-04-10_underwriting-automation-framework.md)

---

## Overview

**Company**: AXA (multinational insurance)  
**Program**: RAG + Agentic AI (Retrieval-Augmented Generation + LLM agents)  
**Use Case**: Underwriting + Claims research + Document analysis  
**Result**: **70% reduction in manual research time**

---

## Implementation Details

### RAG Architecture

```
Underwriter question: "Is cardiac surgery covered under this policy?"
    ↓
RAG System:
  1. Retrieve: Search policy documents + regulatory guidelines
  2. Augment: Gather context (similar cases, prior decisions)
  3. Generate: LLM synthesizes answer with citations
    ↓
Underwriter gets: "Yes, covered under section 3.2. Similar case: XYZ-001 (approved)."
```

### Time Savings
- **Manual research**: 30-45 min per question (reading policies + case files)
- **RAG-assisted**: 2-3 min per question (instant synthesis)
- **Scale**: 100+ research questions daily → 70% time savings

---

## Technology Stack

- **LLM**: Claude or GPT-4 (document understanding)
- **RAG Engine**: LangChain + Vector embeddings (Pinecone/Weaviate)
- **Document Store**: Enterprise document management (SAP/SharePoint)
- **Knowledge Base**: Policy documents + prior decisions + regulatory guidance

---

## Key Success Factors

### 1. Policy Document Indexing
- All policies + amendments indexed as embeddings
- Semantic search (find relevant policies by meaning, not keyword)
- Version control (can query "What was covered in v2.1?" for legacy cases)

### 2. Agentic Workflow
- Agent 1: Retrieval agent (fetch relevant policy sections)
- Agent 2: Analysis agent (interpret policy language)
- Agent 3: Comparison agent (find similar historical cases)
- Orchestrator: Coordinate agents, synthesize final answer

### 3. Citation Accuracy
- LLM provides citations (e.g., "Section 3.2, page 5, Policy v2.3")
- Underwriter can verify by clicking link to source document
- Builds trust (citations = transparency)

### 4. Continuous Learning
- Every research question + answer logged
- Periodically retrain embeddings (policy language evolves)
- Agents learn from feedback (underwriter corrections)

---

## Business Impact

### Time Savings
- **Manual research time**: -70% (30 min → 5 min per question)
- **Underwriter productivity**: 50% increase in cases reviewed per day
- **Team scaling**: Handle 50% more business without hiring

### Quality Metrics
- **Citation accuracy**: 95%+ (RAG citations are correct)
- **Answer relevance**: 90%+ (LLM answers directly address question)
- **Missed cases**: <5% (RAG occasionally fails to retrieve relevant policy)

---

## Lessons for DAC Integration

1. **RAG Unlocks Regulatory Knowledge**
   - Cambodia insurance regulations (Prakas 093) can be indexed + queried
   - Underwriter: "Is diabetes automatically declined?" → RAG finds relevant guidelines
   - DAC lesson: Build RAG on Prakas 093 + IRC guidance early

2. **Agentic Coordination > Single LLM Call**
   - Multiple agents (retrieve → analyze → compare) better than one LLM
   - Each agent specializes; easier to debug + improve
   - DAC lesson: Design multi-agent system (per [DAC Integration](../topics/dac-underwriting-integration.md))

3. **Citations Drive Adoption**
   - Underwriters trust AI when they can verify sources
   - Regulatory acceptance: Decisions are traceable
   - DAC lesson: Always cite sources (audit trail requirement)

---

## Risks Encountered

| Risk | AXA's Mitigation |
|------|------------------|
| Hallucination (LLM invents policy language) | Always cite sources; underwriter verifies before acting |
| Stale embeddings (policy language changes) | Re-index monthly; version control for policies |
| Missed relevant documents (RAG retrieval gap) | Fallback to keyword search; feedback retrains retriever |

---

## Related Case Studies

- [Swiss Re Generative AI](./swiss-re-generative-ai.md) (GenAI for underwriting synthesis)
- [Aviva Medical Underwriting](./aviva-medical-underwriting.md) (medical knowledge synthesis)

---

## Related Topics

- [Tech Stack](../topics/underwriting-tech-stack.md) (LLM + RAG architecture)
- [DAC Integration](../topics/dac-underwriting-integration.md)
