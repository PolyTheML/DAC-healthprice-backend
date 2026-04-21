# 50 High-Quality Resources for Life Insurance AI in Cambodia

**Source**: Curated reference list for agentic AI system architecture
**Date Ingested**: 2026-04-09
**Category**: Framework & Implementation Guide
**Intended Use**: Foundation for LLM context on niche domain expertise
**Related Topics**: [AI Governance & Regulation](../topics/ai-governance-regulation.md), [Insurance Compliance & Governance](../topics/compliance-governance.md)

---

## Overview

This curated collection of 50 resources is organized into **5 technical sub-modules** aligned with the four-layer thesis architecture (Intake → Brain → License → Command Center). Each module contains tools, frameworks, research papers, and case studies to ground LLM responses in production-grade standards.

---

## Module I: Agent Orchestration & Harnessing (The "Skeleton")

The command center layer—frameworks for building multi-agent systems with state management, persistence, and human-in-the-loop patterns.

### Core Frameworks
1. **LangGraph State Management** — State machine workflow engine for multi-agent coordination
   - Docs: https://langchain-ai.github.io/langgraph/concepts/low_level/
   - Use Case: Managing agent state transitions and memory persistence
   
2. **LangGraph Persistence & Checkpointing** — Durability and recovery patterns
   - Docs: https://langchain-ai.github.io/langgraph/how-tos/persistence/
   - Use Case: Resuming interrupted underwriting workflows
   
3. **Multi-Agent Systems with CrewAI** — Task-driven orchestration framework
   - GitHub: https://github.com/joaomdmoura/crewAI
   - Use Case: Autonomous underwriting teams with specialized agents
   
4. **Agent Protocol (Standardizing Agent Communication)** — Open standard for agent interoperability
   - GitHub: https://github.com/AI-Engineer-Foundation/agent-protocol
   - Use Case: Vendor-agnostic agent architecture

### Safety & Observability
5. **Human-in-the-Loop (HITL) Patterns** — Integration points for human review
   - Docs: https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/
   - Use Case: Escalation workflows, override capabilities, audit trails

6. **Agent Benchmarking (AgentBench)** — Systematic testing for multi-agent systems
   - GitHub: https://github.com/THUDM/AgentBench
   - Use Case: Validating agent reliability before production

7. **Pydantic AI (Strict Type Agent Framework)** — Type-safe agent development
   - GitHub: https://github.com/pydantic/pydantic-ai
   - Use Case: Contract-driven API design for agent interfaces

8. **OpenAI Swarm (Lightweight Multi-Agent Orchestration)** — Simplified agent coordination
   - GitHub: https://github.com/openai/swarm
   - Use Case: Rapid prototyping of multi-agent workflows

### Debugging & Monitoring
9. **LangSmith (Debugging Agent Traces)** — Observability for agentic systems
   - Docs: https://www.langchain.com/langsmith
   - Use Case: Understanding agent decision chains, bottleneck identification

10. **AutoGPT Forge (Template for Agent Harnesses)** — Production-grade agent template
    - GitHub: https://github.com/Significant-Gravitas/AutoGPT/tree/master/forge
    - Use Case: Starting point for building underwriting harness

---

## Module II: Insurance-Specific AI & Actuarial Data (The "Brain")

Risk scoring layer—frameworks for frequency-severity modeling, mortality prediction, and interpretability.

### Actuarial Science & Modeling
11. **CAS (Casualty Actuarial Society) - Machine Learning Working Group** — Industry standards
    - Docs: https://www.casact.org/professional-education/research/machine-learning-working-group
    - Use Case: Best practices in actuarial machine learning

12. **Actuarial Data Science (Python for Actuaries)** — Practical implementation guide
    - GitHub: https://github.com/actuarial-data-science/ads-tutorial
    - Use Case: Python libraries and workflows for actuarial modeling

13. **Life Insurance Mortality Modeling in R/Python** — Domain-specific model templates
    - GitHub: https://github.com/actuarial-data-science/LLM-Mortality-Model
    - Use Case: Building mortality curves for Cambodian population data

14. **Frequency-Severity Modeling Guide** — GLM implementation for insurance claims
    - Docs: https://scikit-learn.org/stable/auto_examples/linear_model/plot_tweedie_regression_insurance_claims.html
    - Use Case: Pricing models for life insurance products

### Interpretability & Governance
15. **Interpretability for Insurance (SHAP/LIME)** — Explainability for model decisions
    - GitHub: https://github.com/slundberg/shap
    - Use Case: Explaining underwriting decisions to regulators and customers

### Industry Research
16. **Swiss Re: Life & Health AI Transformation** — Enterprise implementation insights
    - Docs: https://www.swissre.com/institute/research/topics-and-risk-dialogues/digital-business-model-and-cyber-risk/ai-in-insurance.html

17. **Munich Re: Automated Underwriting for Life** — Large-scale automation case study
    - Docs: https://www.munichre.com/en/solutions/life-and-health-solutions/automated-underwriting.html

18. **RGA (Reinsurance Group of America) Insights** — Industry data and benchmarking
    - Docs: https://www.rgare.com/knowledge-center/insights

19. **Casualty Actuarial Society - Python for GLMs** — Mathematical foundations
    - Docs: https://www.casact.org/sites/default/files/2021-03/Python_for_GLM.pdf

20. **AI Governance in Insurance (Singapore Model)** — Regulatory framework reference
    - Docs: https://www.mas.gov.sg/news/media-releases/2023/mas-announces-the-release-of-white-papers-on-the-feat-principles
    - Use Case: FEAT principles (Fairness, Ethics, Accountability, Transparency) for Cambodia adaptation

---

## Module III: Intelligent Document Processing - IDP (The "Intake")

Data extraction layer—OCR, layout understanding, and medical document parsing for Cambodian hospital PDFs.

### High-Performance PDF Processing
21. **Marker (High-Speed PDF to Markdown)** — Fast, layout-preserving conversion
    - GitHub: https://github.com/VikParuchuri/marker
    - Use Case: Batch processing of hospital discharge summaries

22. **Docling (IBM's Document Conversion for LLMs)** — Semantic document understanding
    - GitHub: https://github.com/DS4SD/docling
    - Use Case: Extracting structured data from semi-structured medical documents

23. **Nougat (Meta's Neural Optical Understanding)** — High-quality document understanding
    - GitHub: https://github.com/facebookresearch/nougat
    - Use Case: Handling handwritten or low-quality Cambodian medical records

24. **Surya (Accurate Line-Level OCR)** — Robust OCR for multiple languages
    - GitHub: https://github.com/VikParuchuri/surya
    - Use Case: Extracting text from Khmer and mixed-script medical documents

### Structured Data Extraction
25. **LlamaIndex - Recursive Data Extraction** — Hierarchical document parsing
    - Docs: https://docs.llamaindex.ai/en/stable/examples/low_level/recursive_retriever/
    - Use Case: Breaking down complex medical narratives into structured claims

26. **Microsoft LayoutLM (V3) for Document Understanding** — Layout-aware models
    - GitHub: https://github.com/microsoft/unilm/tree/master/layoutlmv3
    - Use Case: Extracting data from tables and structured medical forms

27. **Amazon Textract - Medical Specific Extraction** — Cloud-based document AI
    - Docs: https://aws.amazon.com/textract/features/medical/
    - Use Case: Compliance-grade extraction with audit trails

28. **Google Document AI - Life Insurance Vertical** — Pre-trained models for insurance
    - Docs: https://cloud.google.com/solutions/document-ai-insurance
    - Use Case: Leveraging Google's domain-specific document understanding

29. **Unstructured.io (Partitioning PDFs for LLMs)** — Preparing documents for LLM ingestion
    - GitHub: https://github.com/Unstructured-IO/unstructured
    - Use Case: Chunking and formatting medical data for LLM context windows

30. **Reducto (High-Fidelity Layout Extraction)** — Enterprise document processing
    - Docs: https://reducto.ai/
    - Use Case: Preserving layout accuracy for complex medical forms

---

## Module IV: Cambodian & Regional Compliance (The "License")

Regulatory and governance layer—frameworks aligned with Cambodian insurance laws and ASEAN standards.

### Regulatory & Legal Framework
31. **Insurance Regulator of Cambodia (IRC) Regulations** — Primary regulatory body
    - Docs: https://irc.gov.kh/en/regulations
    - **Critical for Project**: Official requirements for AI-assisted underwriting

32. **ASEAN Digital Masterplan 2025/2026** — Regional digital economy governance
    - Docs: https://asean.org/book/asean-digital-masterplan-2025/
    - Use Case: Understanding ASEAN-wide digital standards and interoperability

33. **DFDL Cambodia Fintech Legal Update** — Recent fintech and insurance regulations
    - Docs: https://www.dfdl.com/insights/legal-and-tax-updates/cambodia-prakas-on-the-licensing-of-fintech/
    - Use Case: Understanding regulatory approach to financial technology innovation

34. **Tilleke & Gibbins - Insurance Laws Cambodia** — Legal counsel insights
    - Docs: https://www.tilleke.com/practice_area/insurance-cambodia/
    - Use Case: Recent case law and regulatory interpretations

### Market Research & Strategy
35. **The World Bank: Cambodia's Digital Economy Report** — Economic context
    - Docs: https://www.worldbank.org/en/country/cambodia/publication/cambodia-digital-economy-report

36. **PwC: Digital Insurance Trends in SE Asia** — Regional industry trends
    - Docs: https://www.pwc.com/gx/en/industries/financial-services/insurance/trends-2026.html

37. **KPMG: Future of Insurance in ASEAN** — Strategic planning guide
    - Docs: https://kpmg.com/xx/en/home/insights/2026/01/future-of-insurance.html

### Regional Regulatory Models
38. **FSC Taiwan - Digital Insurer Guidelines** — Reference model for digital regulation
    - Docs: https://www.fsc.gov.tw/en/home.jsp?id=54
    - Use Case: Governance approach that Cambodia may adopt (mentioned by Chris)

39. **Vietnam Actuarial Conference Highlights** — Regional actuarial practices
    - Docs: https://actuaries.asn.au/microsites/v-act/
    - Use Case: Understanding regional actuarial standards (mentioned by Peter)

### Industry Standards
40. **Open Insurance (OPIN) Standards** — API standardization for insurers
    - Docs: https://openinsurance.io/
    - Use Case: Interoperability framework for underwriting APIs

---

## Module V: Architecture & Operational Patterns (The "Implementation")

Deployment layer—containerization, scaling, observability, and operational excellence patterns.

### API & Service Architecture
41. **Event-Driven Architecture for Insurance (EDA)** — Asynchronous processing patterns
    - Docs: https://solace.com/industries/insurance/
    - Use Case: Real-time underwriting decision publishing and audit trails

42. **Microservices for Life Insurers (Case Study)** — Enterprise architecture patterns
    - Docs: https://www.thoughtworks.com/en-sg/clients/insurance-modernization
    - Use Case: Modular underwriting service design

43. **Twelve-Factor App Methodology for Fintech** — Operational best practices
    - Docs: https://12factor.net/
    - Use Case: Designing scalable, maintainable Python services

44. **Observability with OpenTelemetry (For Agent Audit Trails)** — Comprehensive logging and tracing
    - Docs: https://opentelemetry.io/
    - Use Case: Full audit trail for underwriting decisions and agent actions

### Frontend & Data Visualization
45. **Streamlit UI Patterns for Data Science** — Rapid dashboard development
    - Docs: https://streamlit.io/gallery
    - Use Case: Underwriter dashboard for case review and override

### High-Performance Backend
46. **FastAPI for High-Performance Actuarial APIs** — Modern Python web framework
    - Docs: https://fastapi.tiangolo.com/
    - Use Case: REST API layer for underwriting engine with automatic OpenAPI docs

47. **Celery (Task Queues for Heavy Medical Processing)** — Async task execution
    - Docs: https://docs.celeryq.dev/en/stable/
    - Use Case: Offloading document parsing and medical data extraction

### Distributed Systems
48. **Dapr (Distributed Application Runtime for Agents)** — Service mesh for distributed agents
    - Docs: https://dapr.io/
    - Use Case: Managing state and messaging across multiple agent instances

### Containerization & Orchestration
49. **Dockerizing Python AI Applications** — Container best practices
    - Docs: https://docs.docker.com/language/python/
    - Use Case: Packaging underwriting service for cloud deployment

50. **Kubernetes for Scalable Underwriting Clusters** — Orchestration for production scale
    - Docs: https://kubernetes.io/docs/concepts/overview/
    - Use Case: Auto-scaling underwriting agents based on case volume

---

## How to Use This Reference

### For Thesis Development
- **Friday Meeting with Chris & Peter**: Pick 3 specific resources from Module IV (IRC regulations, Swiss Re AI paper, AWS reference implementation) to demonstrate grounded expertise
- **Internal RAG System**: Copy these links into your Obsidian Master Index under `_Context` folder organized by module
- **LLM Prompt Engineering**: When requesting system design help, reference specific tools: "Using LangGraph for state management and FastAPI for the underwriting API, design..."

### For Implementation
- **Phase 1 (Intake)**: Start with Module III + relevant sources (Marker, Surya for Khmer support)
- **Phase 2 (Brain)**: Implement Module II concepts (GLM pricing, SHAP interpretability)
- **Phase 3 (License)**: Build Module IV compliance framework + Module I HITL patterns
- **Phase 4 (Command Center)**: Deploy Module V architecture (FastAPI, Kubernetes)

### For Regulatory Discussion
- **IRC Compliance**: Reference #31 (IRC Regulations)
- **Regional Context**: Reference #35 (World Bank Cambodia report), #36-37 (PwC/KPMG SE Asia trends)
- **AI Governance Model**: Reference #20 (Singapore FEAT principles), #38 (Taiwan FSC guidelines)

---

## Key Integration Points

| Module | Thesis Layer | Primary Topics | Key Resources |
|--------|-------------|-----------------|---|
| I | Command Center | Agent Orchestration, Safety | #1-10 (LangGraph, AgentOps, LangSmith) |
| II | Brain | Risk Scoring, GLM, Interpretability | #11-20 (CAS, SHAP, Swiss Re/Munich Re cases) |
| III | Intake | Document Extraction, Medical Parsing | #21-30 (Marker, Docling, Nougat, Textract) |
| IV | License | Regulatory, Compliance, Governance | #31-40 (IRC, DFDL, KPMG, ASEAN standards) |
| V | Implementation | Architecture, Deployment, Operations | #41-50 (FastAPI, Kubernetes, Celery, Dapr) |

---

## Last Updated
2026-04-09 (ingestion date)
