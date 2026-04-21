# Knowledge Base Index

**Created**: 2026-04-09 | **Last Updated**: 2026-04-21 (wiki cleanup — archived 67 off-topic pages; 51 active)

> **Thesis pages** moved to `C:\DAC-UW-Thesis\wiki\`  
> **General AI research** archived to `wiki/_archive/`

---

## Implementation Plans

All project plans: [`wiki/plans/`](./plans/index.md) — Phase 0 (Pricing), Phase 3 (LangGraph), Phase 4 (FastAPI), Phase 5 (React)

---

## DAC Platform Status

| Deployment | URL | Status |
|-----------|-----|--------|
| Frontend | https://dac-healthprice-frontend.vercel.app | ✅ Live |
| Backend | https://dac-healthprice-api.onrender.com | ✅ Live |

**Phase 4 Week 8 (NEXT)**: Email/SMS notifications + portal.dactuaries.com

### Phase 4 Build History

| What | Source | Status |
|------|--------|--------|
| Full underwriting platform (Weeks 1–7) | [phase4-weeks2-7](./sources/2026-04-17_phase4-weeks2-7.md) | ✅ Done |
| ETL + Recalibration Engine | [etl-pipeline-recalibration](./sources/2026-04-16_etl-pipeline-recalibration.md) | ✅ Built |
| Dashboard + PSI Drift Monitor | [dashboard-drift-monitor](./sources/2026-04-15_dashboard-drift-monitor-deployment.md) | ✅ Live |
| Phase 5E Escalation | [phase5e-escalation](./sources/2026-04-12_phase5e-escalation-implementation.md) | ✅ Live |
| Peter Feedback + Frontend Deploy | [peter-feedback](./sources/2026-04-14_peter-feedback-frontend-deployment.md) | ✅ Done |
| FastAPI REST Scaffolding | [phase4-fastapi](./sources/phase4-fastapi-scaffolding.md) | ✅ Done |
| LangGraph Command Center | [phase3-langgraph](./sources/phase3-langgraph-command-center.md) | ✅ Done |
| Synthetic Portfolio Prototype | [synthetic-portfolio](./sources/2026-04-11_synthetic-portfolio-prototype.md) | ✅ Done |

---

## Vietnam Case Study (May 1 Demo)

**Goal**: Health + Life ML pricing (XGBoost + GLM), SHAP, retraining pipeline  
**Audience**: Chris & Peter → Vietnamese insurer client

| What | File | Status |
|------|------|--------|
| FWD Vietnam entity | [fwd-vietnam](./entities/fwd-vietnam.md) | ✅ |
| FWD product research | [fwd-increased-protection](./sources/2026-04-11_fwd-increased-protection-product.md) | ✅ |
| GLM pricing reference | [frequency-severity-glm-tutorial](./sources/frequency-severity-glm-tutorial.md) | ✅ |
| Regulatory comparison (Vietnam/Cambodia) | [comparative-insurance-regulation-southeast-asia](./topics/comparative-insurance-regulation-southeast-asia.md) | ✅ |
| Escalation products pattern | [automatic-escalation-products](./topics/automatic-escalation-products.md) | ✅ |

---

## Core Topics (Active)

### Pricing & Actuarial
- [Frequency-Severity GLM Models](./topics/frequency-severity-glm.md)
- [Risk Scoring & Pricing](./topics/risk-scoring.md)
- [Pricing Engine Phases](./topics/pricing-engine-phases.md)
- [Pricing Escalation Mechanisms](./topics/pricing-escalation-mechanisms.md)
- [Automatic Escalation Products](./topics/automatic-escalation-products.md)
- [Synthetic Data Pricing Bootstrap](./topics/synthetic-data-pricing-bootstrap.md)

### Cambodia / DAC Platform
- [Cambodia Smart Underwriting Engine](./topics/cambodia-smart-underwriting.md)
- [Cambodia Risk Factors Reference](./topics/cambodia-risk-factors-reference.md)
- [DAC Underwriting Integration](./topics/dac-underwriting-integration.md)
- [ETL Pipeline + Recalibration](./topics/etl-pipeline-recalibration.md)
- [Dashboard & Drift Monitor Plan](./topics/dashboard-drift-monitor-plan.md)
- [React Frontend Architecture](./topics/react-frontend-architecture.md)
- [Operational Architecture](./topics/operational-architecture.md)

### Underwriting Workflow
- [Instant-Issue Workflow](./topics/underwriting-instant-issue-workflow.md)
- [Submission Analysis Workflow](./topics/underwriting-submission-analysis-workflow.md)
- [Medical Underwriting Orchestration](./topics/medical-underwriting-orchestration.md)
- [Augmented Underwriter Workflow](./topics/augmented-underwriter-workflow.md)
- [Human-in-the-Loop](./topics/human-in-the-loop.md)
- [Actuarial Scenario Agent](./topics/actuarial-scenario-agent.md)
- [Medical Doc → Health Pricing Bridge](./topics/medical-doc-health-pricing-bridge.md)

### Compliance & Safety
- [Underwriting Fairness Audit](./topics/underwriting-fairness-audit.md)
- [Underwriting Audit Trail](./topics/underwriting-audit-trail.md)
- [AI Governance & Regulation](./topics/ai-governance-regulation.md)
- [Compliance & Governance](./topics/compliance-governance.md)
- [Guardrails & Safety](./topics/guardrails-safety.md)
- [XAI & Explainability](./topics/xai-explainability-auditability.md)

### Tech & ML
- [Underwriting Tech Stack](./topics/underwriting-tech-stack.md)
- [Underwriting Risk Classification](./topics/underwriting-risk-classification.md)
- [Document Extraction](./topics/document-extraction.md)
- [Intelligent Document Processing](./topics/intelligent-document-processing.md)
- [Medical Data Validation](./topics/medical-data-validation.md)
- [Underwriting Implementation Phases](./topics/underwriting-implementation-phases.md)
- [Agentic AI STP](./topics/agentic-ai-stp.md)
- [Advisor-Executor Pattern](./topics/advisor-executor-pattern.md)
- [Command Center + Advisor Integration](./topics/command-center-advisor-integration.md)

---

## Entities (Active)

- [Claude](./entities/claude.md) — AI advisor powering the platform
- [FastAPI](./entities/fastapi.md) — REST API framework
- [LangGraph](./entities/langgraph.md) — Multi-agent orchestration
- [FWD Vietnam](./entities/fwd-vietnam.md) — Vietnam case study reference

---

## Archive

- **General AI research** (harness design, document AI course, agentic patterns, company case studies): `wiki/_archive/`
- **Thesis pages** (auto insurance telematics, templates, experiment results): `C:\DAC-UW-Thesis\wiki\`
