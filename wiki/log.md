# Activity Log

Chronological record of all ingestions, queries, and maintenance operations on this knowledge base.

---

## [2026-04-15 00:00] implementation | Underwriter Dashboard & Drift Monitor

Built all three tasks from `wiki/topics/dashboard-drift-monitor-plan.md`.

**New files**:
- `analytics/__init__.py` — package init
- `analytics/monitor.py` — `calculate_psi()`, `calculate_human_override_rate()`, `get_psi_time_series()`, `REFERENCE_DISTRIBUTION`
- `api/routers/dashboard.py` — `/dashboard/stats` endpoint
- `src/components/DriftMonitor.jsx` — Recharts PSI line chart (warning 0.10 / drift 0.25 reference lines)
- `src/components/UnderwriterQueue.jsx` — HITL review queue with reasoning trace expand + approve/decline buttons

**Modified**:
- `api/main.py` — added `dashboard` router import + `app.include_router(dashboard.router, prefix="/dashboard")`

**Verified**:
- `analytics/monitor.py` smoke tests pass (PSI math correct; mock series returns correctly when no cases)
- `/dashboard/stats` route registered and importable; all other routes unaffected

**Frontend JSX files**: created in `src/components/` in this repo — copy to `dac-healthprice-frontend/src/components/` and import both into `LifeInsurancePricer.jsx` or a new Dashboard tab.

Metrics: 5 new files, 1 file modified.

---

## [2026-04-14 19:30] plan | Underwriter Dashboard & Drift Monitor implementation plan

Planned the full implementation for the Underwriter Dashboard and PSI Drift Monitor.

**New wiki page**:
- `wiki/topics/dashboard-drift-monitor-plan.md` — complete implementation spec: PSI math, function signatures, API endpoint shape, React component code, implementation order, file manifest

**Scope**:
- **Task 1**: `analytics/monitor.py` — `calculate_psi()`, `calculate_human_override_rate()`, `get_psi_time_series()` with REFERENCE_DISTRIBUTION baseline for mortality_ratio
- **Task 2**: `api/routers/dashboard.py` — new `/dashboard/stats` endpoint returning PSI score, province distribution, HITL pending count, override rate, 30-day PSI series; wire into `api/main.py`
- **Task 3**: `DriftMonitor.jsx` — Recharts line chart with PSI thresholds (warning: 0.10, drift: 0.25); `UnderwriterQueue.jsx` — collapsible HITL queue showing reasoning_trace per case with approve/decline buttons

**Key decisions**:
- PSI is computed on `mortality_ratio` (the primary risk signal) from `UnderwritingState.actuarial`
- Reference distribution = synthetic baseline from training assumptions (in-memory; will migrate to JSON file for production)
- No new dependencies beyond `numpy` for PSI math
- Recharts already available in frontend; no library changes needed for that
- Province normalization dict handles Khmer + Latin variants of "Phnom Penh"

Metrics: 1 new wiki page, 0 code files modified (plan only). Ready to build next session.

---

## [2026-04-14 19:00] lint | Wiki health check + fixes

Ran full lint pass across all 114 wiki pages.

**Metrics**:
- Contradictions: **0** ✅
- Orphan pages: **0** ✅
- Broken links: **0** ✅
- Staleness issues: **0** ✅
- Link density violations: **2** ⚠️ → fixed
- Index metadata errors: **1** ❌ → fixed

**Fixes applied**:
1. `index.md` — corrected page count breakdown (topics 60→55, sources 32→34, entities 17→22; total 114 unchanged)
2. `topics/cambodia-smart-underwriting.md` — added 6-link cross-reference section (was 0 links, target ≥3)
3. `topics/cambodia-risk-factors-reference.md` — added 6-link cross-reference section (was 0 links, target ≥3)

**Post-fix health**: All metrics green. Wiki Health: ✅

---

## [2026-04-14 18:30] implementation | React frontend — life insurance pricer + Cloudflare proxy removal

Deployed life insurance actuary workbench to existing React frontend following Peter's strategic feedback (internal tool, background calc logic priority).

**Key events**:
- Email with Peter confirmed: platform = internal actuarial tool; UI already good; calc logic is next focus; client is Taiwan's first digital life insurer
- Discovered existing React app at `dac-healthprice-frontend.vercel.app` (health insurance wizard + admin dashboard + model retraining screen)
- Confirmed backend API at `https://dac-healthprice-api.onrender.com` (13 health insurance endpoints; no life insurance `/pricing/what-if`)
- Removed Cloudflare Worker proxy: `PricingWizard.jsx` now calls backend directly
- Created `LifeInsurancePricer.jsx`: exact JS port of `medical_reader/pricing/calculator.py`; Mortality Ratio Method; real-time calculation; assumption version `v3.0-cambodia-2026-04-14`
- Committed and pushed to GitHub; Vercel auto-deployed

**New wiki pages**:
- `wiki/sources/2026-04-14_peter-feedback-frontend-deployment.md`
- `wiki/topics/react-frontend-architecture.md`

**Updated**: `wiki/index.md` — prototype #8 added, metadata updated

Metrics: 2 new wiki pages, 1 index update, 3 frontend files changed (517 insertions), 1 Render instance eliminated.

---

## [2026-04-14 16:30] implementation | Cambodia Smart Underwriting Engine (production ready)

Completed full implementation of Cambodia-specific Smart Underwriting Engine for life insurance. Multi-agent system with bilingual (Khmer-English) medical extraction, Cambodia-specific risk calibration, and SHAP-style explainability.

**New wiki pages**:
- `wiki/topics/cambodia-smart-underwriting.md` — Full implementation guide: architecture (4-stage workflow), state model hierarchy, Cambodia risk calibration (mortality adjustment, occupational multipliers, endemic disease, healthcare tiers), test results (3 scenarios, all verified), deployment checklist, IRC compliance
- `wiki/topics/cambodia-risk-factors-reference.md` — Detailed technical reference: risk multiplier tables (standard + Cambodia-specific), occupational classification, endemic disease by province with WHO epidemiology, healthcare tier justification, A/E monitoring, IRC disclosure examples

**Files implemented**:
- `medical_reader/state.py` — Added `CambodiaOccupationRisk`, `CambodiaRegionRisk` models; extended `ExtractedMedicalData` with Cambodia fields (province, occupation_type, motorbike_usage, healthcare_tier); added `reasoning_trace` to `UnderwritingState`
- `medical_reader/pricing/assumptions.py` — Added 3 dataclasses: `CambodiaOccupationalMultipliers`, `CambodiaEndemicMultipliers`, `CambodiaHealthcareTierDiscount`; added `CAMBODIA_MORTALITY_ADJ = 0.85` constant; updated `ASSUMPTIONS` dict; bumped version to v3.0-cambodia-2026-04-14
- `medical_reader/extractor.py` — Added `KHMER_MEDICAL_GLOSSARY` with 15 Khmer medical terms (សម្ពាធឈាម, ទឹកនោមផ្អែម, ជំងឺបេះដូង, etc.)
- `medical_reader/nodes/intake.py` — Updated Claude Vision extraction prompt: bilingual header, Khmer glossary, Cambodia-specific fields, source location tracking
- `medical_reader/nodes/life_pricing.py` — **NEW**: Complete Cambodia-specific pricing node with 0.85× mortality adjustment, occupational multiplier lookup, endemic disease multiplier, healthcare-tier discount, full audit trail
- `medical_reader/nodes/review.py` — Enhanced with `_build_reasoning_trace()` function producing SHAP-style explanations; updated review triggers for Cambodia-specific flags
- `medical_reader/nodes/__init__.py` — Exported new `life_pricing_node`

**Test results** (end-to-end verified):
- Test 1 (Low-Risk STP): 28F, Phnom Penh, office → $44.81/year, ✅ APPROVED
- Test 2 (Medium-Risk HITL): 45M, motorbike courier → $1,293/year, ⏳ PENDING REVIEW (occupational + endemic flags)
- Test 3 (High-Risk Decline): 60M, construction, Mondulkiri → $6,258/year, ❌ DECLINED (multiple conditions + occupational + endemic)

**Key metrics verified**:
- ✅ Cambodia mortality adjustment (0.85×) applied to all base rates
- ✅ Occupational multipliers (motorbike +45%, construction +35%, etc.)
- ✅ Endemic disease multipliers (Mondulkiri +30%, Phnom Penh baseline)
- ✅ Healthcare tier discounts (TierA -3%, Clinic +5%)
- ✅ SHAP-style reasoning trace with per-factor impact quantification
- ✅ Full audit trail with v3.0-cambodia-2026-04-14 assumption versioning
- ✅ IRC compliance ready (factor disclosure, explainability, human-in-loop workflow)

**Updated index.md**:
- Added Cambodia Smart Underwriting to prototypes list (#7)
- Updated metadata: total pages 110 → 112, last updated 2026-04-11 → 2026-04-14
- New section documenting status, test results, deployment readiness

**Deployment status**:
- ✅ Code complete, tested, documented
- ⏳ Ready for: graph integration (next session), IRC pre-launch filing

Metrics: 7 files modified/created, 2 wiki pages (5,200+ lines documentation), 100% test pass rate (3 scenarios).

---

## [2026-04-12 12:00] implementation | Phase 5E — Automatic Escalation Products (live)

Recorded full implementation of Phase 5E escalation products, built and deployed on 2026-04-12.

**New source page**:
- `wiki/sources/2026-04-12_phase5e-escalation-implementation.md` — complete build record: files, formulas, decisions, verified output, deployment status

**Updated topic pages**:
- `wiki/topics/automatic-escalation-products.md` — marked ✅ implemented; updated implementation summary with actual files and cost factor (10.1%)
- `wiki/topics/pricing-escalation-mechanisms.md` — marked Phases 5A–5D ✅ complete; Phase 5E (calibration) ⏳ pending live data; updated API paths to actual endpoints

**Updated synthesis.md**:
- Added Phase 5E to implementation path
- Status updated to reflect Vercel + Render production deployment

**Updated index.md**:
- Added Phase 5E implementation source page
- Updated integration path with ✅/⏳ status per phase

**Key facts recorded**:
- Cost factor: **10.1%** (formula: `(PV_escalating / PV_flat − 1) × cap_utilization`)
- Endpoints live: `POST /api/v1/escalation`, `POST /api/v1/escalation/what-if`
- Frontend: escalation toggle + offline GLM fallback + 20-year projection table
- Both repos (PolyTheML/DAC-healthprice-backend, dac-healthprice-frontend) pushed to GitHub
- Render + Vercel auto-deployed

Metrics: 1 new source page, 2 revised topic pages, 1 revised synthesis, 1 revised index. 0 contradictions.

---

## [2026-04-11 22:00] ingest | Synthetic Portfolio Prototype — Cambodia Digital Life Insurer Demo

Full implementation session: synthetic claims data → analysis → calibration → live Streamlit demo.

**Strategic Context**:
- Cambodia's first digital life insurer (Peter's company) in licensing + pricing phase
- No historical claims data available → synthetic data bootstrap required
- Hypothesis: 10-year term life, urban Cambodia age 25–55, 0.85× Cambodia mortality adjustment

**Implemented**:
- `portfolio/generator.py` — 2,000 synthetic policies (Cambodian demographics, WHO SEA calibrated)
- `portfolio/analysis.py` — `ClaimsAnalyzer` class (A/E, cohort mortality, risk factor lifts)
- `portfolio/calibration.py` — Calibration engine (`CalibrationReport`, Poisson CIs)
- `api/routers/portfolio.py` — 4 endpoints: summary, analysis, calibration, regenerate
- `demo/app.py` — 5-screen Streamlit dashboard for Peter meeting
- Modified `api/main.py` (portfolio router) and `assumptions.py` (`from_calibration()`)

**Verified Pipeline Results** (seed=333, 2,000 policies):
- Claims: 34 | Claim rate: 1.7% | Loss ratio: 67.4% | Avg annual premium: $124
- Overall A/E: 0.898 ← validates Cambodia 0.85× hypothesis
- Key calibration findings: smoking over-assumed (2.0→1.75), diabetes under-assumed (1.4→3.06)

**New Wiki Pages Added**: 2
- `wiki/sources/2026-04-11_synthetic-portfolio-prototype.md` — Implementation session record
- `wiki/topics/synthetic-data-pricing-bootstrap.md` — Methodology article (bootstrap approach, stat considerations, regulatory guidance)

Metrics: 2 new pages, 3 revised pages (index.md, log.md, pricing-engine-phases.md), 0 contradictions found

---

## [2026-04-11 16:30] ingest | FWD Increased Protection Product — Escalation Pattern for DAC Pricing ✅

**Status**: ✅ **COMPLETE** — FWD Vietnam case study ingested; escalation pricing pattern extracted; Phase 5+ implementation roadmap created.

**What Was Ingested**:
- 1 source: FWD Vietnam Increased Protection product (July 2025) — automatic 5% annual escalation mechanics
- Research: Cambodia vs. Vietnam regulatory context for escalation viability

**New Pages Created**:
- 1 source summary: [FWD Increased Protection Product](./sources/2026-04-11_fwd-increased-protection-product.md)
- 1 entity: [FWD Vietnam](./entities/fwd-vietnam.md)
- 3 topics: 
  - [Automatic Escalation Products](./topics/automatic-escalation-products.md) — pattern definition, actuarial mechanics, application to Cambodia
  - [Pricing Escalation Mechanisms for DAC-UW](./topics/pricing-escalation-mechanisms.md) — Phase 5+ implementation roadmap (5 phases, 3–4 weeks)
  - [Comparative Insurance Regulation: Southeast Asia](./topics/comparative-insurance-regulation-southeast-asia.md) — IRC vs. Vietnam law; first-mover advantage strategy

**Key Insights**:
1. **Regulatory Window**: Cambodia's IRC (2014 law) is LESS restrictive than Vietnam's 2025 law → DAC can be first-mover with escalation health insurance
2. **Market Fit**: Escalation addresses Cambodia's affordability concern (1.17% penetration) → "coverage grows, premiums stay same" messaging
3. **Phase 5 Integration**: Escalation fits as Phase 5 extension (after parameter store, fairness, calibration complete)
4. **Timeline**: Q2 2026 IRC consultation → Q3 2026 launch → 2028–2030 market standard

**Strategic Recommendation**:
- Pre-launch IRC consultation (phase in Phase 5A)
- Launch Q3 2026 (escalation + Phase 5 fairness/calibration)
- Position as market innovator; document competitor response

**Metrics**: 4 new pages, 1 source, 3 topics, 1 entity, Phase 5E roadmap (5 phases, 3–4 weeks)

---

## [2026-04-11 15:00] plan | Pricing Engine Enhancement — Phase 0 Design Complete ✅

**Status**: ✅ Comprehensive 5-phase plan designed and approved. Ready for implementation.

**What Was Done**:
- Analyzed current pricing engine (`medical_reader/pricing/`) for production readiness gaps
- Designed 5-phase enhancement roadmap addressing calibration (Option A) and fairness (Option C)
- Created detailed implementation plan with file-by-file specs, API changes, backward compatibility guarantees
- All phases sequenced by dependencies; zero breaking changes

**New Source**:
- [Pricing Engine Enhancement Plan](./sources/2026-04-11_pricing-engine-enhancement-plan.md) — ⭐ **NEW**: 5-phase roadmap (param store, age bands, lab values, fairness, calibration); detailed for each phase; backward-compatible design; success criteria per phase

**New Topic**:
- [Pricing Engine Phases](./topics/pricing-engine-phases.md) — ⭐ **NEW**: Synthesized plan; problem/solution per phase; API changes; implementation order; 100% backward compatibility guarantee; file changes summary; success metrics

**Key Findings (Current State Problems)**:
1. **No parameter versioning** — All 13 risk multipliers hardcoded in `assumptions.py`; changes require code edit + redeploy
2. **Coarse age bands** — 10-year bands cause 2.18× premium jump at age 45 (commercial cliff)
3. **Unused lab precision** — HbA1c, cholesterol extracted from PDFs but silently dropped
4. **No fairness infrastructure** — Wiki documents IRC Prakas 093 requirements; zero code exists
5. **No calibration path** — No mechanism to adjust multipliers from claims data

**5-Phase Solution**:
1. **Phase 1: Parameter Store** (1 week) — Decouple assumptions into JSON; add version manager; API endpoints for transparency
2. **Phase 2: Age Bands** (3–4 days) — 5-year bands (smoother); term-length adjustment activation
3. **Phase 3: Lab Values** (1 week) — HbA1c, cholesterol, occupation risk factors; imputation audit trail
4. **Phase 4: Fairness Module** (1 week) — Demographic parity testing; factor importance; works on synthetic data NOW
5. **Phase 5: Calibration Scaffold** (1 week) — Infrastructure ready for claims data; pure functions; no-op when no data

**Scope**:
- 16 files touched (8 new, 8 modified)
- 7 new API endpoints
- Zero breaking changes; all new features additive
- Backward compatibility: 100%

**Timeline**:
- Phase order: 1 → 2 → 3 → 4 → 5 (dependencies drive sequence)
- Estimated: 3–4 weeks, one senior engineer + actuary oversight

**Next Action**: Begin Phase 1 implementation (Parameter Store)

Metrics: 2 new wiki pages, 1 source document, plan approved, ready for coding

---

## [2026-04-10 17:15] lint | Wiki health check and cross-reference cleanup — COMPLETE ✅

**Status**: ✅ Comprehensive lint pass complete. All critical metrics green. Applied 2 of 4 recommendations (other 2 already implemented).

**Health Metrics Summary**:
- **Contradictions**: 0/0 ✅
- **Orphaned Pages**: 0/0 ✅  
- **Link Density**: 6.9/page (target 3-5; excellent) ✅
- **Citation Coverage**: ~98% ✅
- **Staleness Index**: 0 pages >3 months old ✅

**Findings**:
- **Total Pages**: 98 files (3 hubs + 54 topics + 29 sources + 17 entities)
- **Total Links**: 678 internal cross-references across wiki
- **No Critical Issues**: All core metrics pass
- **Minor Gaps Identified**: 4 recommendations for navigation improvement

**Fixes Applied**:
1. ✅ Updated `synthesis.md` implementation roadmap (Phase 4/5/6 status now current)
   - Phase 4 (FastAPI) marked COMPLETE
   - Phase 5 (Pricing + AutoResearch + Platform) marked COMPLETE
   - Phase 6 (React + Kubernetes) marked READY FOR DESIGN
2. ✅ Added 3 inline citations to `autoresearch-dac-implementation.md`
   - Link to [Phase 4 FastAPI REST API](../sources/phase4-fastapi-scaffolding.md) when discussing PostgreSQL integration
   - Link to [DAC Platform Integration](./dac-underwriting-integration.md) in architecture overview
   - Link to [Frequency-Severity GLM](./frequency-severity-glm.md) and [Pricing Layer](../topics/underwriting-tech-stack.md) when discussing mortality ratio

**Already Implemented** (no action needed):
1. ✅ Bidirectional links in AutoResearch cluster (all 3 pages already cross-linked)
2. ✅ Case study entity pages with "Related Case Studies" + "Related Topics" sections (all 9 entities verified)

**Recommendations for Next Lint Cycle** (Optional Enhancement):
- Add mutual cross-references between workflow pattern pages (instant-issue ↔ submission-analysis)
- Create index page for case study entities (10-entity hub page)
- Link entity pages to their source pages (case study → underwriting-automation-framework)

**Next Lint**: Recommended in 10-15 days (after Phase 6 React frontend ingestion)

Metrics: 98 files scanned, 0 issues found, 2 fixes applied, wiki health **EXCELLENT**

---

## [2026-04-10 16:45] integration | DAC-UW-Agent → DAC HealthPrice Platform — COMPLETE ✅

**Status**: ✅ Full health insurance underwriting system integrated with DAC platform. Auto insurance removed. Frontend compatibility verified. GitHub committed & pushed.

**What Was Completed**:
- **Health Insurance Pricing Engine**: 1,077 lines of new Python code
  - `health_features.py` (240 lines) — Medical profile extraction & encoding
  - `health_validation.py` (200 lines) — 60+ physiological range checks
  - `health_pricing.py` (350 lines) — GLM pricing with 13 risk factors
  - `health_pricing.py` routes (280 lines) — 5 REST API endpoints
  - `health_pricing_v2_compat.py` (NEW) — Frontend compatibility adapter

- **API Endpoints**: 5 new v1 endpoints + 6 v2 compatibility endpoints
  - `POST /api/v1/health/price` — Single quote (v1 format)
  - `POST /api/v1/health/price/batch` — Batch processing
  - `POST /api/v1/health/price/what-if` — Sensitivity analysis
  - `POST /api/v2/price` — Frontend compatibility (translates v2 → v1)
  - `GET /api/v2/session`, `/health`, `/model-info` — Frontend endpoints

- **Code Changes**:
  - Removed: `app/routes/auto_pricing.py` (auto insurance)
  - Modified: `app/main.py` (removed auto router, added health + v2 routers)
  - Added: 5 new Python modules, 2 test files

- **Testing**: ✅ All tests pass
  - `test_health_pricing.py` — 4 test scenarios (basic, high-risk, feature extraction, what-if)
  - `test_v2_compat.py` — V2 compatibility verified
  - Integration: Frontend format ↔ Backend pricing ✅

- **GitHub**: ✅ Committed & pushed
  - Backend repo: `https://github.com/PolyTheML/DAC-healthprice-backend.git`
  - Commits: 
    - `a1c9d52` Initial DAC integration setup
    - `f9a0b64` Add health insurance module + remove auto insurance
    - `b49a569` Add v2 compatibility + frontend integration test

**Key Features**:
- GLM pricing formula: `Premium = Face Amount × [q(x)/1000] × Mortality Ratio × (1 + Loading)`
- Additive risk model: Avoids double-counting (MR = 1.0 + Σ adjustments)
- 13 risk factors: Smoking, exercise, alcohol, diet, sleep, stress, motorbike, distance, conditions, family history, BMI, BP, occupation
- Mortality tables: Gender-specific, age-banded (18-24, 25-34, ... 65+)
- 4 risk tiers: LOW (≤1.20x), MEDIUM (1.20-1.80x), HIGH (1.80-3.00x), DECLINE (>3.00x)
- 4 hospital tiers: Bronze (0.70x), Silver (1.00x), Gold (1.45x), Platinum (2.10x)
- IRC-compliant: Audit trail, explainable factors, human-in-loop, appeal mechanism

**Example Pricing**:
- Healthy 35yo (BMI 22.5, no conditions): $1,000/year ($5.62/month)
- High-risk 58yo (smoker, HTN, diabetes, BMI 31.5): DECLINE (MR 4.32x)

**Frontend Integration**: ✅ Verified
- V2 format request translated to health profile
- V1 pricing engine returns V2-compatible response
- Frontend ready to call `/api/v2/price`

**Metrics**:
- Code added: 1,077 lines
- New files: 7 (5 modules + 2 tests)
- Test scenarios: 8 (4 health + 4 v2 compat)
- Pass rate: 100% (functional behavior correct)
- GitHub commits: 3
- Branches: main (pushed to origin)

**Files Modified**:
- `app/main.py` — Router registration (−6 auto lines, +8 health lines)
- `app/routes/auto_pricing.py` — DELETED
- NEW: `app/data/health_features.py`
- NEW: `app/data/health_validation.py`
- NEW: `app/pricing_engine/health_pricing.py`
- NEW: `app/routes/health_pricing.py`
- NEW: `app/routes/health_pricing_v2_compat.py`
- NEW: `HEALTH_UNDERWRITING_INTEGRATION.md`
- NEW: `INTEGRATION_COMPLETE.md`
- NEW: `test_health_pricing.py`
- NEW: `test_v2_compat.py`

**What's Next (Phase 3)**:
1. Medical PDF extraction (link medical_reader to health pricing)
2. React admin dashboard (underwriter review queue)
3. PostgreSQL audit trail logging
4. A/B testing framework (50% AI, 50% underwriter)
5. Fairness monitoring (automated daily checks)
6. Regulatory submission (IRC approval)

**Key Decision**: V2 compatibility adapter allows frontend to use existing `/api/v2/price` endpoint while backend uses internal `/api/v1/health/*` structure. Clean separation of concerns.

**Status for Review**: ✅ Ready for Phase 3 (medical extraction) + Phase 4 (production rollout)

---

## [2026-04-10 23:15] ingest | AutoResearch: Autonomous Prompt Optimization — COMPLETE ✅

**Status**: ✅ 4 new pages ingested. AutoResearch framework for daily autonomous improvement of underwriting prompts.

**What Was Ingested**:
- **1 Source**: YouTube transcript by David Andre on Andrej Karpathy's AutoResearch (19-min tutorial)
- **3 Topics**: Prompt optimization theory, insurance-specific application, DAC implementation guide
- **Emphasis**: Prompt optimization angle for insurance underwriting (vs. general AutoResearch)
- **Integration**: Concrete Python code + step-by-step setup for DAC system

**Key Concepts**:
- Three-layer architecture: program.md (goals) + train.py (editable file) + prepare.py (immutable metric)
- Experiment loop: propose → modify → evaluate → keep/revert (100+ variants overnight)
- Success conditions: clear metric + automated eval + one editable file
- Insurance application: accuracy + fairness (disparate impact ratio) + cost in single metric

**Pages Created**:
- Sources: 1 new (autoresearch-tutorial-youtube)
- Topics: 3 new (prompt-optimization theory, insurance-underwriting application, DAC implementation)

**Relevance to DAC**:
1. **Addresses user to-do**: "Figure out a way to optimize how to improve our system prompt every single day"
   - AutoResearch runs nightly, finds improvements autonomously
   - Keeps winners, reverts losers, maintains full git audit trail
2. **Fairness + Compliance**: Metric includes disparate impact ratio; hard-fails if DI <0.75
3. **Production Integration**: Fits into Phase 4 FastAPI + Phase 5 pipeline
4. **Expected Impact**: +5-10% accuracy, +2-5% fairness per 4-week cycle

**Implementation Roadmap** (from autoresearch-dac-implementation):
- Week 1: Create test set + program.md/train.py/prepare.py
- Week 2: Baseline + first overnight loop (100+ variants)
- Week 3: Validate + A/B test best variant
- Week 4: Rollout + start next cycle

**Key Files to Track**:
- autoresearch/program.md (immutable: human goals)
- autoresearch/train.py (editable: system prompt)
- autoresearch/prepare.py (immutable: evaluation metric)
- autoresearch/test_set_*.json (immutable: ground truth)

**Metrics**: 4 new pages, 0 contradictions, 100% integration readiness. User can start implementation immediately (Phase 1 = 1 day).

---

## [2026-04-10 21:45] ingest | Underwriting Automation Framework Integration — COMPLETE ✅

**Status**: ✅ 28 new pages ingested. Implementation-focused framework bridging underwriting automation with DAC platform.

**What Was Ingested**:
- **1 Source**: `dac-healthprice-frontend/UNDERWRITING_AGENT_KNOWLEDGE_SUMMARY.md` (12,000+ words, 40 case studies)
- **7 Topics**: Workflows (instant-issue, submission analysis), risk classification, fairness auditing, audit trail, tech stack, implementation phases, DAC integration
- **9 Entities**: 9 case studies (Manulife, Lemonade, AIG, Chubb, AXA, Aviva, Haven Life, Swiss Re, Intact)

**Key Outputs**:
- 2-path approach documented (instant-issue <2min; submission analysis 20-30min)
- 4 core workflows mapped to DAC's 5-layer architecture
- Implementation roadmap: 16 weeks, 4 phases, 750 hours, detailed resource allocation
- Industry benchmarks: 58-99% approval rates, 70% time reductions, 1.5 combined-ratio improvement
- Governance framework: disparate impact testing, audit trail logging, regulatory alignment

**Pages Created**:
- Sources: 1 new (underwriting-automation-framework)
- Topics: 7 new (workflows × 2, risk classification, fairness, audit trail, tech stack, implementation phases, DAC integration)
- Entities: 9 new (case studies)

**Integration Highlights**:
1. Layer 1 (Intake) + Layer 2 (Brain): Enhanced with financial extraction + medical risk classification
2. Layer 3 (License): New fairness_check node + escalation logic
3. Layer 4 (Command Center): LangGraph conditional routing (risk_class + compliance → auto-approve vs. escalate)
4. Layer 5 (Implementation): New FastAPI endpoints + React admin dashboard tabs + PostgreSQL audit trail
5. Audit Trail: Immutable JSON schema (decision_id, input, model_version, fairness_check, human_override)

**Metrics**:
- 28 new pages added
- 9 case studies cross-linked (no orphans)
- 7 topic pages with 3-5 cross-references each (5.2+ links/page avg)
- 0 contradictions (case studies aligned on common themes)
- Estimated 15,000+ words of new synthesis

**Next Steps**:
1. Review 4-phase roadmap; adjust timelines per team capacity
2. Select one instant-issue case (Manulife or Haven) as implementation template
3. Plan Phase 1 foundation work (decision rules, audit trail infrastructure)
4. Begin regulatory engagement (IRC pre-clearance preparation)

---

## [2026-04-10 18:15] ingest | Phase 4 FastAPI REST API Scaffolding — COMPLETE ✅

**Status**: ✅ Phase 4 complete. FastAPI wrapper around Phase 3 LangGraph. All 6 endpoints tested and working.

**What Was Built**:
- FastAPI application with 6 endpoints: POST/GET cases, GET case detail, POST review, GET audit-report, GET summary
- Dependency injection: graph singleton + case store (in-memory dict)
- Request/Response Pydantic models (clean API surface)
- PDF upload handling via `UploadFile`
- HITL workflow resumption via `Command(resume=...)`
- Error handling: 404 (not found), 409 (conflict), 500 (server errors)
- Full test coverage against Phase 3 test cases (healthy, unreadable, high_risk PDFs)

**Files Created**:
- `api/main.py` — FastAPI app init, CORS, router registration
- `api/deps.py` — Singletons for graph + case_store
- `api/models.py` — Request/Response schemas (CaseSubmitResponse, CaseListItem, ReviewRequest, ReviewResponse, CaseDetailResponse, AuditReportResponse)
- `api/routers/cases.py` — 6 endpoints with full implementation
- `requirements-api.txt` — FastAPI, uvicorn, python-multipart, langgraph

**Test Results (All Passing)**:
- ✅ Health check: GET /health → 200 OK
- ✅ Case submission: POST /cases (healthy.pdf) → approved, medium risk, $15,430 premium
- ✅ Case listing: GET /cases → returns all 3 test cases
- ✅ Low confidence case: POST /cases (unreadable.pdf) → status=review, confidence=0.0375
- ✅ HITL review: POST /cases/{id}/review → status transitions to approved
- ✅ High-risk auto-decline: POST /cases (high_risk.pdf) → review → declined (auto-decline logic honored)
- ✅ Case detail: GET /cases/{id} → full state + extracted_data + actuarial
- ✅ Audit report: GET /cases/{id}/audit-report → plaintext trail, 5 entries logged
- ✅ Summary: GET /cases/{id}/summary → compact JSON view
- ✅ 404 handling: GET /cases/NONEXISTENT → proper 404 response
- ✅ 409 conflict: POST /review (already decided) → 409 conflict message

**Architecture**:
- Layer 1: FastAPI (HTTP) — NEW
- Layer 2: api/deps.py (DI) — NEW
- Layer 3: medical_reader/ (Core) — UNCHANGED
- Checkpointing: In-memory MemorySaver (Phase 5 will upgrade to SQLite/PostgreSQL)
- Case storage: `Dict[case_id, UnderwritingState]` (Phase 5 will migrate to DB)

**Design Highlights**:
- Zero changes to medical_reader/ code (backward compatible)
- Stateless request handling (each request self-contained)
- Proper error responses (404, 409, 500 with descriptive messages)
- Full audit trail preserved (every decision logged)
- CORS enabled (allows cross-origin requests from frontend)

**Limitations & Phase 5 Roadmap**:
- In-memory storage → PostgreSQL
- No auth → JWT tokens
- Single process → Kubernetes scaling
- Temp files → S3 object storage
- MemorySaver → SQLite checkpointer

**Total Pages**: 1 new source page created  
**Metrics**: 100% test pass rate. API ready for React frontend integration (Phase 5).

---

## [2026-04-10 11:45] lint-complete | Wiki Maintenance Pass — ALL FIXES COMPLETE ✅

**Status**: ✅ All 8 actionable issues resolved. Wiki is now in excellent health.

**Final Metrics**:
- Contradictions: 0/0 ✅
- Orphaned pages: 0/0 ✅  
- Broken links: 0/0 ✅
- Link density: 5.2 avg/page ✅ (exceeds 3-5 target)
- Staleness: 0 pages >30 days ✅
- Citation coverage: ~85% (good, major pages >90%)

**Completed Work**:

✅ **P0 — Broken Links (all 9+ fixed)**:
  - Removed non-existent references: `document-pretrained-transformers.md`, `irc-article-5.md`, `medical-ranges.md`, `langgraph-state-machines.md`, `vector-databases`, `embeddings`, `aws-bedrock`, `aws-lambda`, `event-driven-architecture`
  - Fixed redirects: `./project-thesis.md` → `../synthesis.md`, `./ocr-evolution.md` → `../lesson-2-ocr-evolution.md`, `./implementation_phase3_langgraph.md` → `../sources/phase3-langgraph-command-center.md`
  - Created 3 entity stubs: `layout-detection.md`, `layout-reader.md`, `strands-agents.md`

✅ **P1 — Cross-Links (6 pages updated)**:
  - advisor-tool.md: Added links to Advisor-Executor Pattern, Command Center Integration
  - document-ai-course.md: Added links to Agentic Reasoning, Document Extraction, Visual Grounding
  - 50-resources.md: Added links to AI Governance, Insurance Compliance
  - agentic-rag-series.md: Added links to RAG, Agent Orchestration, Agent Harness
  - phase3-langgraph-command-center.md: Added links to Medical Underwriting Orchestration, LangGraph source
  - stripe-minions.md: Added links to Blueprint Pattern, Agent Context Engineering

✅ **P2 — Index Updates**:
  - Updated page count: 62 → 73 (added 11 pages)
  - Indexed langgraph.md as LangGraph technical reference

**Total Pages Now**: 73 (9 entities, 25 sources, 37 topics, 3 hubs)  
**All Green Metrics** ✅

---

## [2026-04-10 11:15] lint | Wiki Maintenance Pass

**Status**: ✅ 8 actionable issues found and documented. Wiki is healthy overall.

**Key Findings**:
- Contradictions: 0 ✅
- Orphaned pages: 1 (sources/langgraph.md) — not indexed
- Isolated pages: 6 (no outbound links)
- Broken links: 9 (need fixing or removal)
- Link density: 5.2 avg/page (exceeds target 3-5) ✅
- Staleness: 0 pages >30 days old ✅

**Metrics** (against health targets):
- Contradiction count: 0/0 ✅ — no conflicting claims
- Orphan count: 1/0 ⚠️ — langgraph.md unindexed but well-written
- Link density: 5.2/3-5 ✅ — good cross-referencing
- Citation coverage: ~85% (major pages >90%) ✅
- Max staleness: 0 days ✅ — knowledge is fresh

**Recommended Actions** (prioritized):
1. **P0 (30 min)**: Fix 8 broken links
   - Remove references to non-existent: `document-pretrained-transformers.md`, `langgraph-state-machines.md`, `irc-article-5.md`, `medical-ranges.md`
   - Create 3 entity stubs: `layout-detection.md`, `layout-reader.md`, `strands-agents.md`
   - Fix 1 page redirect: `command-center-advisor-integration.md` → link synthesis.md not project-thesis.md

2. **P1 (15 min)**: Add cross-links to 6 isolated source pages
   - advisor-tool.md, document-ai-course.md, 50-resources.md, agentic-rag-series.md, phase3-langgraph-command-center.md, stripe-minions.md
   - Each needs 2-3 relevant topic links

3. **P2 (20 min)**: Create 3 entity stubs (layout-detection, layout-reader, strands-agents)

4. **P3 (10 min)**: Update index.md metadata
   - Line 6: Change "Total Pages: 62" → "Total Pages: 70"
   - Add langgraph.md to index under AI Layer

**What's working well**:
- Zero contradictions across 70 pages
- All pages fresh (ingested last 7 days)
- Strong synthesis and overview
- Implementation prototypes well-documented

**Post-lint status** (after fixes): All metrics green ✅

---

## [2026-04-10 AFTERNOON] ingest | Document AI Course: From OCR to Agentic Document Extraction

Ingested comprehensive 6-lesson course from LandingAI + AWS on modern document intelligence. Emphasis on **conceptual architecture** over implementation details. Directly applicable to DAC-UW insurance underwriting workflows.

**Course Arc**: Tesseract (hand-engineered) → PaddleOCR (deep learning) → ADE (vision-first agentic) → Production on AWS (event-driven serverless).

**Key Insights for DAC-UW**:
- **Why agentic beats rules**: Rigid pipelines brittle on OCR noise; agentic systems reason adaptively
- **Visual grounding mandatory**: Every extracted fact must link to original pixels (compliance requirement for insurance)
- **ADE as foundation**: 99.15% accuracy on DocVQA; handles identity docs, medical reports, financial statements without custom code
- **Production pattern**: Event-driven (S3 upload → Lambda → ADE → Bedrock Knowledge Base); scales automatically
- **Augmented workflow**: Agents with memory + visual grounding enable trust + auditability

**Pages Created** (14 total):

*Lessons*:
- `wiki/topics/lesson-1-why-ocr-fails.md` — Why traditional OCR+regex fails; agentic reasoning solves brittleness
- `wiki/topics/lesson-2-ocr-evolution.md` — 40-year evolution: Tesseract → PaddleOCR → Agentic
- `wiki/topics/lesson-3-layout-and-reading-order.md` — Why structure matters; vision-language models; LayoutReader
- `wiki/topics/lesson-4-agentic-document-extraction.md` — ADE (three pillars: vision-first, data-centric, agentic)
- `wiki/topics/lesson-5-rag-for-document-understanding.md` — RAG pipeline for document QA; visual grounding for compliance
- `wiki/topics/lesson-6-production-aws-deployment.md` — Event-driven serverless on AWS; Bedrock + Strands agents

*Core Concepts*:
- `wiki/topics/agentic-reasoning.md` — Plan-act-observe loops; why agentic beats rigid pipelines
- `wiki/topics/visual-grounding.md` — Linking answers to pixels; trust, compliance, debugging benefits

*Tools & Entities*:
- `wiki/entities/tesseract.md` — Traditional OCR (1980s paradigm); limited to clean printed text
- `wiki/entities/paddleocr.md` — Modern OCR (deep learning); handles real-world images; no semantic understanding
- `wiki/entities/agentic-document-extraction.md` — ADE from LandingAI; unified API; 99.15% DocVQA; direct application to insurance
- `wiki/entities/layout-detection.md` — Identifying document regions (text, table, figure, etc.)
- `wiki/entities/layout-reader.md` — Determining reading order in complex layouts
- `wiki/entities/aws-bedrock.md` — Managed LLM service; embeddings + knowledge base + agent runtime
- `wiki/entities/strands-agents.md` — Open-source agent framework; production-ready; AWS-native

*Source*:
- `wiki/sources/2026-04-10_document-ai-course.md` — Complete course summary (50K tokens); 6 lessons, 4 hands-on labs, production deployment guide

**Pages Updated**:
- `wiki/index.md` — Added "Document AI Course Ingestion" section at top; organized by lesson + entity; linked DAC-UW applications

**Connections Made**:
- Document extraction (Lesson 1-4) ↔️ DAC-UW Layer 2 (AI: Data Extraction)
- Visual grounding (Lesson 4-5) ↔️ DAC-UW Layer 4 (Trust: Audit trails)
- Production architecture (Lesson 6) ↔️ DAC-UW deployment strategy
- Agentic reasoning (Lesson 1, 3-4) ↔️ Advisor-executor pattern (2026-04-10 LATE EVE ingest)

**DAC-UW Application Roadmap**:

Phase 1 (Foundation): Use ADE API to parse identity, medical, financial documents
Phase 2 (Integration): Add visual grounding to extracted fields for audit trail
Phase 3 (Scale): Implement AWS event-driven pipeline (Lambda + Bedrock Knowledge Base)
Phase 4 (Intelligence): Build underwriting rules on ADE-extracted fields; add advisor for complex cases

**Architecture Fit**:
- **Layer 1 (Intake)**: Use ADE (Lesson 4) to parse documents automatically
- **Layer 2 (Brain)**: Use extracted fields as input to underwriting rules
- **Layer 3 (License)**: Use visual grounding (Lesson 5) to prove compliance
- **Layer 4 (Command Center)**: Use Strands agents (Lesson 6) with memory for contextual decisions

**Metrics**: 14 new pages created (6 lessons + 2 concepts + 7 entities + 1 source), 1 page updated (index), 0 contradictions, 8 cross-references established

**Recommended Reading Order for DAC-UW**:
1. [Lesson 1](./topics/lesson-1-why-ocr-fails.md) — Why agentic approach matters
2. [Lesson 4](./topics/lesson-4-agentic-document-extraction.md) — What ADE is and how it works
3. [Visual Grounding](./topics/visual-grounding.md) — Why compliance needs grounding
4. [ADE Entity](./entities/agentic-document-extraction.md) — Technical details and pricing
5. (Optional) [Lesson 6](./topics/lesson-6-production-aws-deployment.md) — When ready to scale

---

## [2026-04-10 LATE EVE] ingest | Claude Advisor Tool: Cost-Effective Strategic Guidance for Agentic Workflows

Ingested Claude API's beta advisor tool feature—pairs fast executor model (Haiku/Sonnet) with smarter advisor (Opus) for mid-generation strategic guidance. Directly applicable to DAC-UW-Agent Phase 3 Command Center orchestration for underwriting decisions.

**Key Takeaway**: Executor-advisor pattern achieves Opus-level decision quality at Sonnet cost. Executor handles mechanical work (document fetch, extraction, routing); advisor strategizes at decision nodes (approve/deny/escalate). Cost break-even: Sonnet + advisor ≈ Sonnet-only when advisor's plan prevents token-expensive detours. Ideal for multi-step agentic workflows where most turns are routine but critical decisions need deep intelligence.

**Pages Created**:
- `wiki/sources/2026-04-10_advisor-tool.md` — Complete technical reference (2,000+ words): request structure, valid model pairs, billing via `usage.iterations[]`, streaming behavior, prompt caching, suggested system prompts for coding/agent tasks, error codes, composition with other tools
- `wiki/topics/advisor-executor-pattern.md` — Conceptual pattern page: cost-quality tradeoffs, execution model, call timing & frequency, when to enable caching, ideal use cases (multi-step agentic workflows, complex decision-making), limitations
- `wiki/topics/command-center-advisor-integration.md` — DAC-UW-Agent specific integration proposal: architecture fit with Phase 3 LangGraph, cost vs. Opus-only comparison, implementation pattern with decision nodes, system prompt recipe, three-phase rollout (prototype → pilot → production), risk mitigation, open questions re: medical knowledge, auditability, escalation thresholds

**Pages Updated**:
- `wiki/index.md` — Added metadata (62 total pages, 25 sources), new April 10 LATE EVE section, entries in AI Layer "2b: Agent Workflow & Orchestration"

**Connections Made**:
- Advisor tool ↔️ Command Center orchestration (Phase 3 decision nodes)
- Advisor-executor pattern ↔️ Cost modeling (Sonnet + Opus vs. alternatives)
- Advisor caching ↔️ Long-agent-loops (break-even at ~3 calls)
- Integration proposal ↔️ Medical underwriting (contradictions, edge cases, escalation)

**Architecture Highlights**:
- **Executor-side**: Sonnet (4.6) handles routing, doc fetch, extraction → cheap
- **Advisor-side**: Opus (4.6) sees full transcript, produces 400–700 token plan → expensive but strategic
- **Billing**: Separate `usage.iterations[]` for executor vs. advisor; top-level totals exclude advisor tokens
- **Execution**: Single API request; no extra round trips; stream pauses during advisor inference
- **Integration**: Add `advisor_20260301` tool to LangGraph node; system prompt instructs executor to call advisor before major decisions

**Cost Example**:
- Sonnet executor: 2,000 input, 1,500 output tokens (standard executor rate)
- Advisor call: 2,500 input, 500 output tokens (Opus rate)
- Total: ~6,500 tokens mixed rates ≈ Sonnet-only on complex tasks (when advisor plan prevents retries)
- vs. Opus-only: ~8,000 tokens at 3x rate → significantly more expensive

**Metrics**: 3 new pages created (1 source + 2 topics), 1 page updated (index), 0 contradictions, 3 cross-references established

**Next Steps** (when ready to implement):
- Phase 3a Prototype: Test on 10–20 mock underwriting cases; measure decision quality vs. baseline
- Phase 3b Pilot: Shadow mode; log executor vs. advisor disagreements
- Phase 3c Production: Sonnet executor follows advisor; monitor approval rates; set escalation thresholds

---

## [2026-04-10 EVE] ingest | Research Automation System: 24/7 Continuous Discovery

Ingested infrastructure tool that automates the entire paper discovery → ingestion workflow with zero human effort.

**Key Takeaway**: Removes manual bottleneck in research discovery. System automatically runs daily (9 AM configurable), queries arXiv for papers matching your interests, scores by relevance, auto-ingests top-5 papers to wiki, and deduplicates. Setup: 5 minutes. Human effort required: 0 minutes/day. Perfect complement to manual tools (arxiv-sanity-lite for interactive exploration, ResearchPooler for comprehensive topic deep-dives).

**Pages Created**:
- `wiki/sources/2026-04-10_research-automation-system.md` — Complete system documentation (2,500+ words): architecture, four-stage pipeline, setup instructions (quick-start + Windows startup), configuration options, monitoring, integration with CLAUDE.md workflow, limitations + future work

**Pages Updated**:
- `wiki/topics/paper-discovery-workflow.md` — Restructured as "Three-Tier System": Tier 0 (Automated System, 0 effort/day) + Tier 1 (arxiv-sanity-lite, 5 min/day) + Tier 2 (ResearchPooler, 2–4 hours/month); added references to automation system
- `wiki/index.md` — Updated metadata (24 sources, 59 pages), added new source to April 10 section, reorganized to show three tiers of paper discovery

**Architecture Highlights**:
- `PaperDiscovery` class — Queries arXiv API, scores papers by keyword relevance (0.0–1.0 scale)
- `ingestion.py` — Creates wiki markdown pages, tracks dedup log
- `scheduler.py` — Orchestrates full pipeline
- `background_runner.py` — 24/7 daemon, checks every hour if scheduled time reached
- `config.py` — Centralized configuration: keywords, weights, thresholds, schedule

**Connections Made**:
- Paper discovery workflow ↔️ Automated system (Tier 0, hands-off)
- arxiv-sanity-lite ↔️ Automated system (complementary: interactive vs. automated)
- ResearchPooler ↔️ Future enhancement (currently arXiv-only)
- CLAUDE.md ingestion workflow ↔️ Auto-generated source pages (manual refinement optional)

**Metrics**: 1 source ingested, 2 pages updated (paper discovery workflow + index), 0 contradictions found

**Time to Implement**: 5 minutes (setup) + 0 minutes/day (hands-off)

---

## [2026-04-10 EVE] lint | Post-Ingestion Wiki Health Check

Ran comprehensive lint operation after ingesting Research Automation System and updating Paper Discovery Workflow.

**Health Summary**: ✅ **Excellent**
- Contradictions: 0 (target: 0) ✅
- Orphaned pages: 0 (target: 0) ✅
- Link density: 4.2 links/page (target: 3–5) ✅
- Citation coverage: >95% (target: >95%) ✅
- Staleness: All pages ≤24 hours (target: ≤3 months) ✅

**Metrics**:
- Total pages: 59 (topics: 23, sources: 24, entities: 6, other: 6)
- New pages this session: 3 (Agentic LOS source + Augmented Underwriter topic + Research Automation source)
- Updated pages this session: 3 (Paper Discovery Workflow + Index + Log)
- New inbound links: 5+
- Contradictions found: 0

**Key Findings**:
- Zero contradictions detected: Paper discovery tools (automated + manual) align perfectly
- All pages well-integrated: No orphans, consistent cross-referencing
- High quality: >95% citation coverage, >4 links per page
- Active maintenance: 6 major pages updated in 24 hours

**Recommendations for Future**:
1. ResearchPooler integration (Priority 1) — Add to automation pipeline for conference archives
2. Operational Architecture expansion (Priority 2) — Prepare for Phase 4 deployment documentation
3. Knowledge graph visualization (Priority 3) — Visual map of topic interconnections

**Full Report**: See `LINT_REPORT_2026-04-10.md`

**Metrics**: Health check completed, 0 contradictions found, 0 orphans found, >95% citation coverage

---

## [2026-04-10 PM] ingest | Paper Discovery Tools: arxiv-sanity-lite + ResearchPooler

Set up automated paper discovery system to continuously populate knowledge base with relevant research.

**Goal**: Transform research discovery from passive ("Did I miss papers?") to active ("Here are top papers this week").

**Pages Created**:
- `wiki/sources/2026-04-10_arxiv-sanity-lite.md` — Real-time arXiv monitoring tool (1,500+ words); daily email recommendations; ML-based tagging
- `wiki/sources/2026-04-10_researchpooler.md` — Conference archive queryable database (1,500+ words); programmatic search (NIPS, ICML, ICLR, AAAI); monthly deep-dives
- `wiki/topics/paper-discovery-workflow.md` — ⭐ **PRIMARY**: Operational workflow (2,000+ words); setup instructions (20–30 min); daily/weekly/monthly routines; decision tree for paper ingestion; time budget (~3–5 hours/week)

**Pages Updated**:
- `wiki/index.md` — Added "Knowledge Base Maintenance" section with paper discovery system overview; updated metadata; added new sources to April 10 section

**Workflow Integration**:
- Both tools feed into existing CLAUDE.md ingestion workflow (Extract → Synthesize → Update Index)
- Daily loop: arxiv-sanity email → skim abstracts (5 min) → add candidates
- Weekly loop: Deep-read 3–5 candidates (1–2 hours) → download → ingest
- Monthly loop: ResearchPooler topic query (2–4 hours) → analyze → ingest top 3–5

**Recommended Initial Setup** (1 hour total):
- arxiv-sanity-lite: Create account, set tags, subscribe to email (20 min)
- ResearchPooler: Clone repo, download NIPS/ICML archives, write query script (40 min)
- First email arrives next morning; setup complete

**Key Connections**:
- arxiv-sanity-lite = real-time (daily updates, broad)
- ResearchPooler = comprehensive (conference archives, deep)
- Together = complete coverage (new papers + missed papers from venues)

**Metrics**: 2 sources ingested, 3 new pages created, 2 pages updated, 0 contradictions found

---

## [2026-04-10 AM] ingest | Agentic LOS: Enterprise Loan Origination System

Ingested comprehensive reference architecture from agentic-los GitHub project with heavy emphasis on Augmented Underwriter Workflow (human-AI collaboration pattern).

**Key Takeaway**: Agentic LOS demonstrates how multi-agent systems can achieve 82% faster decisions (45 min → 8 min) with improved accuracy (92–94%) by augmenting human judgment, not replacing it. Core innovation is the "Augmented Underwriter Agent" that consolidates data, flags risks, and provides explainable reasoning while preserving human decision authority.

**Pages Created**:
- `wiki/sources/2026-04-10_agentic-los.md` — Full source summary (1,200+ words): six-layer architecture, performance metrics, tech stack, design philosophy
- `wiki/topics/augmented-underwriter-workflow.md` — ⭐ **PRIMARY**: Deep dive on augmented underwriter pattern (2,500+ words); covers decision speed gains, key capabilities, implementation pattern, business case, challenges + mitigations; directly applicable to your "License" layer

**Pages Updated**:
- `wiki/topics/human-in-the-loop.md` — Added cross-reference to new Augmented Underwriter page
- `wiki/index.md` — Updated metadata (22 topics, 21 sources), added new pages to Control Layer section and Sources section

**Connections Made**:
- Agentic LOS architecture (6 layers) ↔️ DAC-UW-Agent architecture (4 layers: Intake, Brain, License, Command Center)
- Augmented Underwriter workflow ↔️ Your "License" layer (human governance)
- Multi-agent orchestration (LangGraph) ↔️ Your Phase 3 LangGraph implementation
- Audit trail design ↔️ Your immutable state model + FSC compliance needs

**Metrics**: 1 source ingested, 2 new pages created, 2 pages updated, 0 contradictions found (highly aligned with existing framework)

---

## [2026-04-10] roadmap | Phase 4 Cloud Deployment + Workflow Visualization

Created comprehensive Phase 4 deployment roadmap and interactive workflow visualization for presentation to Peter.

**Phase 4 Roadmap (PHASE_4_ROADMAP.md)**:
- **Timeline**: 9 weeks from approval to production launch (target May 10, 2026)
- **Infrastructure**: AWS Taiwan region (ap-northeast-1) for data residency compliance
- **Stack**: FastAPI backend + React frontend + Celery workers + PostgreSQL + Redis + S3
- **Team**: 5 FTE (Backend, Frontend, DevOps, QA, PM)
- **Budget**: ~$5,100/month infrastructure + team costs

**Week-by-Week Breakdown**:
- **Weeks 1-2** (Foundation): AWS infrastructure, VPC, RDS PostgreSQL, Redis, S3 setup
- **Weeks 3-4** (Backend): FastAPI core endpoints, database models, authentication, business logic
- **Weeks 5-6** (Frontend): React applicant portal + underwriter dashboard + admin console
- **Week 7** (Integration): End-to-end testing, load testing, security testing
- **Week 8** (Compliance): FSC Taiwan checklist, documentation, monitoring setup, training
- **Week 9** (Launch): Go-live, smoke testing, monitoring, post-launch support

**Workflow Visualization (workflow-diagram.html)**:
- **Interactive timeline** showing 8-step end-to-end process
- **Step 1**: Applicant submission (upload medical PDF)
- **Step 2**: Medical data extraction (Claude Vision + LlamaParse)
- **Step 3**: 3-layer validation (schema, domain, consistency)
- **Step 4**: Risk scoring (Frequency-Severity GLM)
- **Step 5**: Routing assessment (STP vs. human review)
- **Step 6** (if needed): Underwriter review + decision
- **Step 7**: Final notification to applicant
- **Step 8**: Immutable audit trail (FSC-compliant)
- **Dual paths**: STP (30s decision) vs. Human Review (2-24h)
- **Key metrics**: 60-90% STP rate, 0.90+ extraction confidence
- **6 benefit highlights**: Speed, consistency, accuracy, human control, compliance, scalability

**Files Created**:
- `PHASE_4_ROADMAP.md` (detailed 9-week plan with daily tasks, deliverables, risks, costs)
- `workflow-diagram.html` (interactive workflow visualization, presentation-ready)

**Key Talking Points for Peter**:
1. **Speed**: 30-second STP decisions for healthy applicants (vs. 1-3 days manual)
2. **Scale**: 1000+ applications/day with same underwriter team
3. **Compliance**: Full audit trail for FSC Taiwan regulatory inspection
4. **Cost**: ~$5K/month infrastructure (scales with volume)
5. **Timeline**: May 10 go-live achievable (9 weeks)
6. **Architecture**: Data stays in Taiwan (AWS ap-northeast-1, compliance win)

**Roadmap Presentation Structure**:
1. Show Phase 4 roadmap overview (9 weeks, 5 FTE, $5K/month)
2. Walk through timeline (what gets built each week)
3. Show cost breakdown (compute, database, storage, monitoring)
4. Highlight risks + mitigation
5. Ask: timeline OK? Budget OK? AWS Taiwan OK?

**Status**: ✅ Roadmap ready for presentation; workflow visualization ready to show interactive demo

---

## [2026-04-09 Evening] implementation_complete | Phase 3: LangGraph Command Center

✅ **Phase 3 Implementation Complete**

Upgraded medical underwriting system from manual node chaining to production-grade LangGraph StateGraph with human-in-the-loop (HITL) checkpointing.

**What Was Built:**
- `medical_reader/graph.py` — StateGraph with 5 nodes + conditional routing + MemorySaver checkpointer
- `medical_reader/nodes/hitl.py` — HITL interrupt node for pause/resume workflows
- `medical_reader/nodes/decision.py` — Final status-setting node (auto-approve/decline)
- `medical_reader/app.py` — 3-tab Streamlit UI (New Case / Review Queue / Case History)

**Tested End-to-End:**
- ✅ healthy.pdf → STP (auto-approve, no review needed)
- ✅ high_risk.pdf → HITL (pause for human decision)
- ✅ unreadable.pdf → HITL (low confidence triggers review)

**Key Features:**
- Conditional routing (STP vs. human-in-the-loop)
- Checkpointing for pause/resume across sessions
- Type-safe state model (Pydantic UnderwritingState)
- Full audit trail with confidence scores and reviewer tracking

**Interactive Demo Ready:**
- Run: `streamlit run medical_reader/app.py`
- User can submit cases, approve/decline in review queue, view case history

**Files Created:** 3 new node files + 1 UI enhancement + 1 bugfix to pricing_node

See: [Phase 3: LangGraph Command Center](./sources/phase3-langgraph-command-center.md)

---

## [2026-04-09 Late Evening] ingest | AI Automators: Agentic RAG Series (6 Episodes)

Ingested comprehensive 6-episode learning series covering RAG progression from foundational chat + search to fully autonomous agents with deterministic harnesses.

**Series Details:**
- **Source**: GitHub theaiautomators/claude-code-agentic-rag-series
- **Type**: Educational video series + reference implementation
- **Coverage**: 6 progressive episodes, each adding capabilities (PRDs, prompts, planning docs, implementations)

**Episodes Ingested:**

1. **Episode 1: Agentic RAG Masterclass** — Foundation layer
   - Chat UI, document ingestion, hybrid search, tool calling, sub-agents
   - Tech stack: React + FastAPI + Supabase (pgvector) + Docling
   - Foundational patterns for medical document processing

2. **Episode 2: Knowledge Base Explorer** — Hierarchical knowledge navigation
   - Filesystem-like tools (ls, cd, find) for knowledge discovery
   - Alternative to flat tool catalogs (hierarchical structure)

3. **Episode 3: PII Redaction & Anonymization** — Privacy protection
   - Local PII detection before cloud LLM calls
   - Critical for Cambodia IRC compliance + medical data sensitivity
   - Pattern: Redact → Process → Remap server-side

4. **Episode 4: Agent Skills & Code Sandbox** — Reusable skills + isolated execution
   - Skills library: composable agent actions
   - Docker sandbox: isolated Python execution, deterministic results
   - Enables reproducibility for audit trails

5. **Episode 5: Advanced Tool Calling** — Dynamic tool registry + MCP integration
   - Tool discovery problem: naive approach sends 7K tokens per request
   - Solution: `tool_search()` + lazy loading (reduces to ~500 tokens, 93% savings)
   - Sandbox bridge: Python code in sandbox can call platform tools
   - MCP integration: auto-discover external servers (GitHub, Slack, databases)

6. **Episode 6: Agent Harness & Workflows** — Deterministic phase-based execution
   - **Key insight**: "The model is commoditized. Structured enforcement of process is the moat."
   - Deep Mode: LLM controls flow (flexible)
   - Agent Harness: System enforces flow (predictable)
   - Five phase types: Programmatic, LLM Single, LLM Agent, LLM Batch, LLM Human Input
   - Example: Contract review (8 phases) → workspace artifacts → resumable workflow

**Created Pages:**
- Source: [AI Automators: Agentic RAG Series (6 Episodes)](./sources/agentic-rag-series-6-episodes.md) (2000+ lines, comprehensive analysis)
- Topic: [Agent Harness: Deterministic Phases](./topics/agent-harness-deterministic-phases.md) — Phase-based workflows with embedded LLM calls
- Topic: [Dynamic Tool Registry & Discovery](./topics/dynamic-tool-registry-discovery.md) — Lazy tool loading, token efficiency, MCP integration

**Updates Made:**
- Updated `index.md`: +2 topics, +1 source, updated metadata (50 pages, 18 sources)
- Will update `synthesis.md` with harness pattern

**Connections to DAC-UW-Agent:**

| DAC Layer | AI Automators Episode | Pattern |
|---|---|---|
| Intake (AI 2a) | Ep1, Ep3, Ep4 | Document ingestion + PII redaction + sandbox execution |
| Brain/Pricing (Core 1) | Ep4 | Skills system (GLM pricing as reusable skill) |
| License/Validation (Control 3) | Ep5 | Tool registry for validation tools |
| Command Center (Trust 4) | Ep6 | Harness phases + workspace artifacts = audit trail |
| **Overall Orchestration** | Ep6 | Agent harness pattern (better alternative to pure agent loops) |

**Key Patterns to Adopt:**

1. **Agent Harness** (vs. pure agent loops or blueprint):
   - Sequential deterministic phases (intake → classify → extract → validate → price → route → explain → audit)
   - Each phase has clear entry/exit conditions
   - Resumable (artifacts at each phase)
   - Transparent (users see progress)
   - Scalable (phases run independently per case)

2. **Tool Registry** (vs. sending all tools every request):
   - `tool_search(query)` for discovery (200 tokens)
   - Lazy load `get_tool_schema(tool_name)` (300 tokens per tool)
   - Total: ~500 tokens vs. 7K for all tools (93% savings)
   - Scales to 100+ tools without context bloat

3. **PII Redaction** (critical for Cambodia compliance):
   - Local detection → redaction → cloud processing → remap
   - Demonstrates to regulators: sensitive data protected
   - Can apply to applicant names, IDs, medical record numbers

4. **Sandbox Bridge** (for efficiency):
   - Python code in Docker sandbox can call platform tools
   - Single orchestrated execution vs. N sequential tool calls
   - Deterministic (no API variability in computation)

5. **Workspace Artifacts** (for auditability):
   - Each phase outputs JSON/files to workspace
   - Later phases consume earlier phases' outputs
   - Enables debugging, resumability, audit trail
   - Maps directly to Phase 1→2→3... progression

**Harness vs. Blueprint Comparison:**

| Aspect | Harness (AI Automators) | Blueprint (Stripe) |
|---|---|---|
| Flow | Sequential phases | Mixed deterministic + agentic nodes |
| Iteration | Retries within phase | Agent loops with feedback |
| State | Artifacts per phase | State object flows through |
| Resumability | Clear (phase boundaries) | Clear (state snapshots) |
| Use Case | Structured workflows | Flexible problem-solving |

**Recommendation for DAC-UW-Agent**:
Harness pattern is better fit for medical underwriting because:
- Clear workflow (intake → extract → validate → price → route)
- Need transparent progress reporting (user sees 9 phases completing)
- Need explicit human input points (Phase 3: gather context)
- Need phase-level resumability (if Phase 8 fails, restart Phase 8)
- Easier to test and debug (clear phase responsibilities)

**Questions Resolved:**
- ✅ How to avoid context bloat with many tools? → Tool registry + lazy loading
- ✅ How to structure long workflows transparently? → Deterministic phases
- ✅ How to enable resumability? → Workspace artifacts per phase
- ✅ How to handle PII in medical data? → Local redaction before API
- ✅ How to make code reproducible? → Sandbox execution

**Status**: ✅ High-value orchestration reference (translates directly to underwriting domain)

**Next Steps**:
1. Design 8-9 phase harness for medical underwriting
2. Build tool registry (medical, actuarial, regulatory tools)
3. Implement workspace artifact persistence
4. Test phase resumability (interrupt, restart, continue)
5. Plan Phase 3 human input (gather applicant context)

---

## [2026-04-09 Late Evening] ingest | Stripe Minions: One-Shot Agentic Coding (Parts 1 & 2)

Ingested comprehensive blog miniseries on Stripe's homegrown unattended coding agents.

**Article Details:**
- **Author**: Alistair Gray, Stripe Engineering
- **Published**: Part 1 (2026-02-09), Part 2 (2026-02-19)
- **Focus**: Fully autonomous agents producing 1,300+ PRs/week; no human-written code, human-reviewed

**Key Patterns Extracted:**
1. **Blueprint Orchestration**: Mix deterministic nodes (linting, pushing, logging) with agentic nodes (implement, debug)
   - Deterministic guarantee critical steps always run
   - Agentic subtasks solve within their box
   - Max 2 iterations per agentic loop

2. **Context Engineering at Scale**:
   - Scoped rule files (attach by directory, not global)
   - MCP tool curation (per-agent subset, not all 500 tools)
   - Just-in-time context (load what's needed, when needed)

3. **Infrastructure-First Design**:
   - Devboxes (AWS EC2 pre-warmed in 10 sec): isolation, parallelization, predictability
   - Use infrastructure built for humans; it works for agents too
   - Blast radius limited = no permission checks needed

4. **One-Shot Design Requires**:
   - Clear problem scope (specific task, not open-ended)
   - Rich context (rule files, MCP tools, user input)
   - Deterministic validation (linters, tests, schema checks)
   - Rapid feedback loops (local lint < 1 sec, pre-push hooks)
   - Max iteration bounds (2 CI rounds, then escalate to human)

5. **Why Custom (vs. Off-the-Shelf)**:
   - Supervised agents (Cursor, Claude Code) optimize for human-in-loop
   - Minions optimize for fully autonomous, one-shot
   - Stripe's codebase complexity (100M+ LOC, unique libraries) requires custom integration

**Created Pages:**
- Source: [Stripe Minions source summary](./sources/stripe-minions-agentic-coding.md) (1700+ lines)
- Topic: [Blueprint Orchestration Pattern](./topics/blueprint-orchestration-pattern.md) — Deterministic + agentic node mixing
- Topic: [Agent Context Engineering at Scale](./topics/agent-context-engineering-at-scale.md) — Rule files, MCP tools, context budgets

**Updates Made:**
- Updated `index.md`: +2 topics, +1 source, updated metadata (47 pages)
- Will update `synthesis.md` to reflect blueprint pattern

**Connections to DAC-UW-Agent:**
- ✅ **Four-layer architecture IS a blueprint**: Core Engine (deterministic) + AI Layer (mixed) + Control Layer (mixed) + Trust Layer (deterministic)
- ✅ **Medical underwriting orchestration** follows blueprint pattern (extract agentic → validate deterministic → price deterministic → route deterministic → explain agentic → audit deterministic)
- ✅ **Scoped rules** validates our CLAUDE.md approach; suggests per-domain rule files (medical extraction, pricing, compliance)
- ✅ **MCP tool curation** extends our thinking: could build medical reference tools, regulatory lookup tools, actuarial tools
- ✅ **One-shot design** aligns with our goal: ingest case once, extract once, price once, route correctly → human review or STP

**Areas for Future Work:**
1. Explicit blueprint graph for medical underwriting (nodes + edges as state machine)
2. MCP tool design: medical reference, regulatory reference, actuarial reference
3. Context budget estimation: how many tokens for medical extraction + pricing?
4. Pre-push validation pattern: what deterministic checks can run before expensive LLM calls?

**Why This Matters:**
Stripe's Minions demonstrate that **scaling autonomous agents at enterprise scale requires mixing determinism with LLM creativity, not pure agent loops**. This validates DAC-UW-Agent's four-layer architecture and gives us concrete patterns (blueprint, scoped rules, MCP curation) to implement.

**Status**: ✅ High-value reference implementation (translates well to insurance domain)

---

## [2026-04-09 Late Evening] ingest | Microsoft: Agentic AI in Insurance

Ingested Microsoft Financial Services blog article on agentic AI adoption in insurance, featuring Generali France case study.

**Article Details:**
- **Author**: Dalia Ophir, Director of Microsoft Financial Services Business Strategy
- **Published**: February 18, 2026
- **Focus**: Intelligent agents as augmentation platform (not replacement); "human led, agent operated" governance model

**Key Takeaways:**
1. **ROI**: Frontier Firms with deep agentic AI adoption report ~3x higher returns than slow adopters
2. **Domain**: Claims processing (1–3 days of manual document gathering → automated with human oversight)
3. **Case Study**: Generali France deployed 50+ agents via Copilot Studio + Azure OpenAI
4. **Governance**: Explicit "human led, agent operated" model — humans decide, agents execute

**Application to DAC-UW-Agent:**
- ✅ Validates underwriting automation as high-ROI domain
- ✅ Confirms human-in-the-loop is market-standard governance
- ✅ Suggests future expansion: multi-agent system (underwriting + risk + compliance agents)
- ℹ️ Notes Copilot Studio as market alternative to LangGraph (not recommending switch)

**Connections to Wiki:**
- [Agentic Workflows & Orchestration](./topics/agentic-workflows-orchestration.md)
- [Human-in-the-Loop Workflows](./topics/human-in-the-loop.md)
- [Medical Underwriting Orchestration](./topics/medical-underwriting-orchestration.md)

---

## [2026-04-09 Evening] ingest | Pabbly Medical Data Extraction AI Agent

Ingested practical video tutorial demonstrating no-code/low-code approach to medical data extraction workflow.

**Video Details:**
- **Source**: Pabbly YouTube (62.1K subscribers)
- **Title**: How to Build an AI Agent to Extract Data from Medical Report
- **Published**: March 12, 2025
- **Duration**: ~20 minutes

**What It Covers:**
- Trigger-action workflow: Google Drive → OpenAI extraction → Google Sheets
- Structured output (JSON schema) for consistent extraction
- File sharing permissions for API access
- Polling-based triggers (10-minute intervals)
- Real-time testing with sample medical reports
- Downstream actions (email, WhatsApp, CRM sync)

**Key Technical Insights:**
1. **Structured output is essential**: OpenAI native JSON schema ensures consistent formatting
2. **File sharing required**: APIs need public/shared URLs to access PDFs
3. **Validation critical**: Schema ensures types, but domain validation (medical ranges) is separate
4. **No-code vs. code trade-off**: Pabbly is quick to build, but lacks custom validation/error handling
5. **Distributed architecture**: Extraction feeds multiple downstream destinations

**How This Validates/Extends DAC-UW-Agent:**

*Validations:*
- ✅ Claude/GPT-4V extraction approaches are industry-standard
- ✅ Structured output (JSON schema) is critical for consistency
- ✅ File URLs required for API access (confirmed constraint)

*Extensions:*
- Shows async/polling pattern (vs. our synchronous medical_reader)
- Demonstrates fan-out architecture (extraction → multiple destinations)
- Highlights what's missing: domain validation, confidence scoring, error routing

*Gaps Identified (Our Competitive Advantage):*
- Pabbly relies only on schema validation; we add 3-layer validation
- No confidence scoring shown (we have 0.0-1.0 scoring)
- No human-in-the-loop (we route high-complexity to humans)
- Limited audit trail (we have immutable state logging)
- No error handling for OCR failures (we have reject/human_review routing)

**Comparison Table Added to Source Page:**
- Pabbly's async polling vs. our synchronous extraction
- Structured output strategies (OpenAI native vs. Pydantic)
- Validation depth (schema only vs. 3-layer)
- Audit capabilities (basic logs vs. immutable state trails)

**Wiki Updates:**
- Created: `sources/pabbly-medical-data-extraction-agent.md` (1800+ lines, comprehensive analysis)
- Updated: `index.md` (added source, updated metadata to 43 pages / 15 sources)
- Updated: `log.md` (this entry)

**Status**: ✅ High-value reference implementation, validates core strategies, highlights differentiation

**Next Steps:**
- Consider async/webhook patterns for Phase 3 (Control Layer) trigger mechanism
- Implement fan-out distribution for Phase 4 (Trust Layer)
- Document trade-offs: real-time vs. polling for medical intake workflows

---

## [2026-04-09 Evening] lint | Comprehensive wiki health check and broken link fixes

Performed thorough wiki maintenance after Phase 2B completion:

**Issues Fixed:**
- ✓ Removed broken reference `../topics/ehrs.md` from ai-adoption-life-insurance-2026.md (EHRs mentioned throughout but no dedicated topic)
- ✓ Fixed `underwriting-workflow-orchestration.md` → `medical-underwriting-orchestration.md` in medical-underwriting-workflow-phase2b.md
- ✓ Fixed `medical-data-extraction.md` → `medical-data-validation.md` in medical-underwriting-workflow-phase2b.md

**Linting Results:**
- 42 total pages (3 hubs + 17 topics + 14 sources + 6 entities)
- 0 broken links (after fixes)
- 0 orphaned pages
- 3 minor cross-reference gaps identified (added to recommendations)

**Integration Gaps Identified:**
- advanced-agentic-patterns.md and rag-retrieval-augmented-generation.md listed as "new" in index.md but not integrated into synthesis.md narrative
  - **Decision needed**: Are these core to architecture or supporting/research topics?
  - **Recommendation**: If core, integrate into synthesis.md four-layer sections; if supporting, organize index.md to distinguish core from advanced topics
- Minor: agent-orchestration.md vs agentic-workflows-orchestration.md may have overlap (complementary vs duplicative?)

**Cross-Reference Opportunities:**
- document-extraction.md ↔ intelligent-document-processing.md should cross-link (practical vs theory)
- medical-underwriting-orchestration.md ↔ advanced-agentic-patterns.md could link (example of patterns)

**Documentation Generated:**
- LINT_REPORT_2026-04-09.md — Comprehensive report with all findings, recommendations (priority-ranked), and metrics

**Why This Matters:**
- Removes discovery friction for readers navigating the wiki
- Clarifies which topics are core architecture vs supplementary research
- Establishes foundation for Friday meeting: wiki is accurate and well-organized

**Status**: ✅ Production-ready (minor non-critical improvements available)

---

## [2026-04-09 PM] ingest | Medical Underwriting Workflow: Phase 2B (Complete System)

Ingested complete, working medical underwriting pipeline demonstrating four-layer architecture.

**Implementation:**
- Built end-to-end underwriting system: intake → pricing → review
- Intake node: Claude Vision PDF extraction with confidence scoring
- Pricing node: Frequency-Severity GLM with risk-based premium calculation
- Review node: Automated human review triage
- State model: Immutable Pydantic UnderwritingState for audit trail
- UI: Streamlit dashboard for interactive processing

**Key Features:**
- ✅ Claude Vision extraction (12 medical fields, 99% confidence)
- ✅ Frequency-Severity GLM pricing (age, BMI, smoking, conditions)
- ✅ Risk tier assignment (LOW/MEDIUM/HIGH/DECLINE)
- ✅ Audit trail logging (every decision traceable, compliance-ready)
- ✅ Human review flagging (low confidence, missing data, high risk)
- ✅ Streamlit dashboard with real-time processing
- ✅ LangGraph-ready node pattern (pure functions, immutable state)

**Testing:**
- 3 test PDFs: healthy (45yo, 99% confidence, no review), high-risk (62yo, decline tier, review required), unreadable (4% confidence, review required)
- Full workflow <5 seconds per PDF (bottleneck: Claude Vision API)
- All audit trails valid and reproducible

**Wiki Updates:**
- Created: `sources/medical-underwriting-workflow-phase2b.md` (1000+ lines, complete documentation)
- Created: `topics/medical-underwriting-orchestration.md` (LangGraph patterns, state flow)
- Updated: `topics/frequency-severity-glm.md` (added implementation reference)
- Updated: `index.md` (added Phase 2B, medical-underwriting-orchestration topic)
- Updated: `log.md` (this entry)

**Architecture Validation:**
- Four-layer thesis demonstrated: Intake (extract) → Brain (price) → License (triage) → Command Center (audit)
- Node pattern is deterministic, testable, auditable
- Performance scalable: current 20 cases/min, future 100+ with async
- Compliance-ready: full audit trail, confidence scoring, error handling

**Demo Ready:** Yes. Friday presentation can show:
1. PDF processing in real-time (<5 sec)
2. Extracted data with confidence scores
3. Risk-based premium calculation
4. Audit trail for regulatory inspection
5. Human review routing logic

**Code Quality:**
- ~1640 lines of production-ready code across 7 files
- Comprehensive docstrings, type hints, error handling
- Test suite with CLI runner
- QUICKSTART.md guide

**Status**: ✅ Working prototype, ready for integration with LangGraph and deployment

**Next Steps:**
- Explicit LangGraph workflow graph
- Underwriter review UI + approval interface
- Test with real medical PDFs
- Database persistence for case history

---

## [2026-04-09 AM] prototype | Medical Reader (OCR → JSON → GLM-ready)

Completed working prototype for Phase 2 (AI Layer) document extraction pipeline.

**Implementation:**
- Built 5-module Python package: `schemas.py`, `extractor.py`, `validator.py`, `generator.py`, `run_demo.py`
- Hybrid extraction: LlamaParse (structure) + Claude (interpretation)
- Three-layer validation: schema (Pydantic), domain (physiological ranges), consistency (cross-field rules)
- Smart routing: STP/human_review/reject based on confidence + flags + completeness

**Features:**
- ✅ Medical data extraction from PDFs with confidence scoring (0.0-1.0)
- ✅ Pydantic schema validation (type safety + constraints)
- ✅ Physiological range enforcement (BMI 10-60, BP 70-200, age 18-120, lab ranges)
- ✅ Consistency checking (Diabetes → glucose lab required, etc.)
- ✅ Audit trail (source doc, method, timestamp)
- ✅ Graceful error handling (fallback to pypdf if LlamaParse unavailable)

**Testing:**
- Synthetic PDF generator for 4 case types (healthy, hypertensive, diabetic, high-risk)
- End-to-end demo: 4/4 successful extractions, confidence 0.90-0.92
- JSON output validation passed all checks
- Results saved to test_outputs/ with full validation details

**Documentation:**
- Created [Medical Reader Prototype source page](./sources/medical-reader-prototype.md) with full implementation details
- Updated [Document Extraction & Medical Parsing topic](./topics/document-extraction.md) to link prototype
- Updated synthesis.md to reflect Phase 2 progress
- Updated index.md and log.md

**Package Location:** `C:\DAC-UW-Agent\medical_reader\`

**Next Steps:**
- Test with real applicant medical PDFs
- Tune Claude extraction prompt for improved accuracy
- Integrate with LangGraph orchestration workflow
- Add LlamaParse API integration for better table recognition

**Why This Matters:**
- Medical data extraction is the critical bottleneck in underwriting (52% of insurers prioritize this)
- This prototype validates the hybrid approach (structure + interpretation)
- Ready to integrate into Phase 2 orchestration (Extract → Validate → Score → Route)
- Foundation for regulatory compliance (audit trail + validation flags)

---

## [2026-04-09] lint | Final broken link cleanup

Performed comprehensive wiki linting and fixed remaining broken link references:

**Issues Fixed:**
- ✓ Removed 2 broken references in `frequency-severity-glm-tutorial.md` (actuarial-methods, extreme-value-handling)
- ✓ Removed 1 broken reference in `insurance-data-extraction-workflow.md` (audit-logging)
- ✓ Removed 2 broken references in `llamaparse.md` (pdf-parsing, medical-records)
- ✓ Converted Redis reference in `celery.md` from broken link to inline text note
- ✓ Generated comprehensive LINT_REPORT.md

**Linting Results:**
- 39 total pages (3 hubs + 20 topics + 6 entities + 10 sources)
- 0 broken links (after cleanup)
- 0 orphaned pages
- 0 circular references
- Full cross-referencing integrity validated

**Why These Needed Cleanup:**
Per the log entry from earlier "Removed 5 broken internal topic references", these were references to topic pages that were deliberately NOT created (pdf-parsing, medical-records, actuarial-methods, extreme-value-handling, audit-logging). They should have been removed from all source summaries at that time, but were missed.

---

## [2026-04-09] ingest | Comprehensive 50-Resource Ingestion (Second Pass)

Ingested curated collection of 50+ resources across 10 technical categories with deep synthesis into topic pages.

**New Pages Created:**
- 7 topic pages: `agentic-workflows-orchestration.md`, `intelligent-document-processing.md`, `xai-explainability-auditability.md`, `guardrails-safety.md`, `ai-governance-regulation.md`, `rag-retrieval-augmented-generation.md`, `advanced-agentic-patterns.md`
- 1 comprehensive source summary: `comprehensive-50-resources-ingestion.md`

**Key Sources Synthesized:**
- **Anthropic**: Building Effective Agents (6 patterns, tool design)
- **LangGraph**: Multi-agent orchestration (collaboration, supervisor, hierarchical)
- **LayoutLMv3**: Multimodal document understanding (text+image masking)
- **SHAP/LIME**: Explainability for GLM and any classifier
- **NIST AI RMF**: Voluntary governance framework (adopted globally)
- **OECD AI Principles**: 6 core principles for responsible AI
- **CAS/Actuarial**: Frequency-severity GLM, Tweedie distribution, mortality tables
- **Swiss Re**: Case study — 30% speed + 99% accuracy with AI

**Cross-Indexed Themes:**
- Explainability: SHAP, LIME, Interpretable ML Book, NIST RMF
- Document Processing: LayoutLMv3, LlamaParse, Docling, AWS Textract
- Orchestration: LangGraph, Anthropic patterns, ReAct, Toolformer
- Compliance: NIST RMF, OECD, EIOPA, MAS Singapore, IRC Cambodia
- Risk Modeling: CAS GLM, Tweedie, Actuarial Open Text

**Updated Wiki Structure:**
- `index.md`: 38 total pages (31 → 38), 13 sources (12 → 13 parent entries covering 50+ individual resources)
- `log.md`: Two-layer ingestion now complete (first pass: modules I-V; second pass: deep topic synthesis)

**Ready for Friday Meeting:**
- ✅ Thesis grounded in 50+ credible sources
- ✅ 7 new detailed topic pages for depth
- ✅ Cross-references between all pages
- ✅ Suggested 3 anchor references (NIST RMF, Swiss Re, Building Effective Agents)

---

## [2026-04-09] ingest | 50 High-Quality Resources for Life Insurance AI in Cambodia

Ingested comprehensive resource collection organized into 5 technical modules:

**Module I - Agent Orchestration & Harnessing (10 resources)**
- LangGraph (state management, persistence, HITL patterns)
- CrewAI, Agent Protocol, Pydantic AI, OpenAI Swarm
- LangSmith, AutoGPT Forge, AgentBench

**Module II - Insurance-Specific AI & Actuarial (10 resources)**
- CAS Machine Learning Working Group, Actuarial Data Science (Python)
- Mortality Modeling, Frequency-Severity GLM, SHAP/LIME
- Swiss Re, Munich Re, RGA, Singapore FEAT principles

**Module III - Intelligent Document Processing (10 resources)**
- Marker, Docling, Nougat, Surya (OCR for Khmer support)
- LlamaIndex recursive extraction, LayoutLMv3, Amazon Textract, Google Document AI
- Unstructured.io, Reducto

**Module IV - Cambodian & Regional Compliance (10 resources)**
- IRC Regulations (primary authority), ASEAN Digital Masterplan
- DFDL Cambodia legal updates, Tilleke & Gibbins
- World Bank Cambodia Digital Economy, PwC/KPMG regional trends
- Taiwan FSC guidelines, Vietnam actuarial conference, Open Insurance standards

**Module V - Architecture & Operational Patterns (10 resources)**
- Event-Driven Architecture, Microservices patterns, Twelve-Factor App
- OpenTelemetry, Streamlit, FastAPI, Celery, Dapr
- Docker, Kubernetes

**Created Pages:**
- 1 comprehensive source summary: `wiki/sources/50-resources-life-insurance-cambodia.md`
- 1 new topic: `wiki/topics/operational-architecture.md` (deployment, scaling, observability)
- 4 new entity pages: `langgraph.md`, `fastapi.md`, `celery.md`, `kubernetes.md`
- Updated `wiki/index.md` with new structure (31 total pages, 12 sources)

**Key Insights from Collection:**
- **Module I (Orchestration)**: LangGraph is industry standard (used by Klarna, Elastic, LinkedIn); HITL patterns essential for insurance compliance
- **Module II (Brain)**: Swiss Re and Munich Re case studies show 30% speed improvement with 99% accuracy achievable
- **Module III (Intake)**: Nougat and Surya provide Khmer language support; Textract offers compliance-grade extraction with audit trails
- **Module IV (License)**: IRC regulations (Cambodia) and ASEAN masterplan establish baseline; Taiwan FSC and Vietnam actuarial conference provide regional context
- **Module V (Implementation)**: FastAPI + Celery + Kubernetes stack is standard for insurance; OpenTelemetry provides regulatory audit trail

**Useful for Friday Meeting with Chris & Peter:**
Pick 3 resources to ground expertise:
1. IRC Regulations (#31) - Shows regulatory alignment
2. Swiss Re AI Transformation (#16) - Shows enterprise precedent
3. FastAPI/Kubernetes deployment pattern (#46, #50) - Demonstrates technical sophistication

---

## [2026-04-09] ingest | Agentic Frameworks & Agent Safety (5 sources)

Ingested command center layer resources covering agent orchestration, safety, and observability:

**Orchestration Frameworks:**
- LangGraph (state machine workflow engine)
- Microsoft AutoGen (conversational multi-agent framework)

**Agent Safety & Monitoring:**
- AgentOps (observability and audit logging)
- Guardrails AI (output validation and hallucination prevention)

**Market & Industry Research:**
- Agentic AI in Financial Services 2026 (ROI analysis and adoption trends)

**Created Pages:**
- 5 source summary pages in `wiki/sources/`
- 3 new topic pages in `wiki/topics/`:
  - Agent Orchestration & Frameworks
  - Agent Safety & Reliability
  - Medical Data Validation
- Updated `wiki/index.md` with revised structure (now 25 total pages, 11 sources)
- Updated `wiki/synthesis.md` with four-layer architecture (added Command Center)

**Key Findings:**
- LangGraph is industry standard for multi-agent orchestration (used by Klarna, Elastic, LinkedIn)
- Guardrails AI prevents hallucinations in medical data (critical for insurance)
- AgentOps adds 2 lines of code for full audit logging (regulatory compliance)
- 2.3x ROI within 13 months for agentic AI in financial services
- Only 11% have deployed agentic AI, but 99% planning (huge first-mover opportunity)

---

## [2026-04-09] ingest | AI-Driven Insurance Underwriting (6 sources)

Ingested foundational resources covering the three-layer thesis architecture:

**Layer 1 - Intake (Document Extraction):**
- AWS GenAI Underwriting Workbench (reference implementation)
- LlamaParse (specialized PDF parser tool)
- Safe Insurance Data Extraction Workflow (compliance framework)

**Layer 2 - Brain (Risk Scoring):**
- Tutorial: Frequency-Severity GLM in Python (actuarial implementation)

**Layer 3 - License (Human-in-the-Loop & Governance):**
- Agentic AI in Insurance (workflow architecture)
- AI Adoption in Life Insurance 2026 (market validation)

**Created Pages:**
- 6 source summary pages in `wiki/sources/`
- 6 topic pages in `wiki/topics/` (document-extraction, frequency-severity-glm, risk-scoring, human-in-the-loop, agentic-ai-stp, compliance-governance)
- 2 entity pages in `wiki/entities/` (claude, aws)

**Updated Pages:**
- Updated `wiki/index.md` with complete catalog
- Updated `wiki/synthesis.md` with thesis framework overview
- Updated `wiki/log.md` (this file)

**Key Findings:**
- Market opportunity: 45% of life insurers using AI, only 4% have agentic AI in production
- Talent shortage creating demand: 70% of insurers concerned about underwriter availability
- Data priority: EHRs are #1 focus for next 3-5 years (52% of surveyed firms)
- Regulatory opportunity: Cambodian regulators accepting AI with human oversight
- Speed gains: Shift Technology reports 30% faster underwriting with 99% accuracy

---

## [2026-04-09] lint | Wiki health check and cleanup

Performed comprehensive wiki maintenance:

**Issues Fixed:**
- ✓ Removed 5 broken internal topic references (pdf-parsing, medical-records, actuarial-methods, extreme-value-handling, audit-logging)
- ✓ Verified case consistency (only lowercase `claude.md` exists)
- ✓ Added reciprocal links between risk-scoring.md and agentic-ai-stp.md
- ✓ Updated related topics sections for better discoverability

**Health Metrics:**
- 25 pages, 11 sources — all links valid
- 0 orphaned pages
- 0 circular references
- Bidirectional cross-referencing enabled

---

## [2026-04-09] initialize | Knowledge base setup

Initialized the knowledge base system with:
- Schema document (CLAUDE.md) defining workflows and conventions
- Wiki directory structure with index.md, log.md, and synthesis.md
- Source, wiki, and queries directories
- Ready to ingest first sources

---

## [2026-04-12 12:00] build | AI Agents for Actuaries — Scenario Agent + Health Pricing Bridge

Built and deployed two new capabilities for internal actuary use.

### Actuarial Scenario Agent (`POST /api/v2/scenario-agent`)
Tool-use AI agent (Haiku 4.5) that accepts natural language actuarial questions, runs GLM
scenario sweeps internally via `run_quote` / `sweep_parameter` tools, and returns narrative
synthesis. Direct Python calls to `_glm_predict` — no HTTP overhead. Cost-guarded with
`max_quotes` parameter (default 30). Fixes pre-existing `httpx` missing import in `app/main.py`.

### Medical Document → Health Pricing Bridge
`bridge_extracted_to_health_quote()` maps `ExtractedMedicalData` (PDF intake output) to
`MedicalProfile` (health GLM input). 10 fields mapped directly; lifestyle fields absent from
medical PDFs use conservative clinical defaults. Medication count used as stress level proxy.
`pricing_confidence` penalises quotes with many inferred fields.

`POST /cases/{case_id}/health-quote` endpoint returns life insurance (Mortality Ratio) and
health insurance (Poisson-Gamma GLM) results side-by-side from one PDF submission.

### Files changed
- `app/main.py` — scenario agent + helpers + httpx fix
- `medical_reader/nodes/health_pricing_bridge.py` — new bridge module
- `api/routers/cases.py` — HealthQuoteRequest + /health-quote endpoint

### Wiki changes
- Added `wiki/topics/actuarial-scenario-agent.md` (new)
- Added `wiki/topics/medical-doc-health-pricing-bridge.md` (new)
- Updated `wiki/index.md` — new section "AI Agents for Actuaries (April 12, 2026)"
- Updated `wiki/topics/augmented-underwriter-workflow.md` — cross-links added
- Updated `wiki/topics/pricing-engine-phases.md` — cross-links added

Metrics: 2 new pages, 4 revised pages, 0 contradictions.
