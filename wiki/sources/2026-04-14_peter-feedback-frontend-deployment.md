# Peter Feedback & Frontend Deployment — April 14, 2026

**Created**: 2026-04-14  
**Last updated**: 2026-04-14  
**Type**: Session implementation notes  
**Source**: Internal email exchange (Chanpoly → Peter) + development session

---

## Summary

Email exchange with Peter (actuarial executive) clarified product positioning, followed by a development session that deployed the life insurance pricer and simplified the frontend infrastructure.

---

## Peter's Strategic Guidance

### 1. Platform Orientation

Peter confirmed the platform should be positioned as an **internal tool for insurance companies** to conduct pricing and maintain claims data — not a customer-facing quote engine. His exact words:

> *"The background calculation logic should be the next major focus. The current user interface is well designed for the purpose of demonstration/sample."*

This resolves the question raised in the email: **do not pivot to customer-facing**. The actuarial workbench framing is correct.

### 2. Input Variables

- Variables already in demo are appropriate
- Future additions depend on what claims fields the client has
- Free to propose additional variables that are actuarially beneficial

### 3. Taiwan Digital Insurance Context

Peter clarified the strategic context:
- Taiwan's FSC has opened applications for digital life insurance licenses
- DAC is helping **Taiwan's first digital life insurer** establish its license and price initial products
- This insurer wants AI-powered quoting, underwriting, and customer service to run lean
- Digital products in the region are currently simple (same offline product adjusted for online expenses/commissions)
- FWD Vietnam uses AI for agent product recommendations based on customer attributes (referenced from Vietnamese Actuarial Conference)

**Implication**: The platform is being built for a real client in licensing phase. Scope decisions should favour regulatory compliance and actuarial transparency over UX polish.

---

## Frontend Discovery

The existing React frontend at `https://dac-healthprice-frontend.vercel.app` was found to contain:

| Component | Purpose |
|-----------|---------|
| `LoginPage` | Hard-coded staff credentials (3 users) |
| `InsuranceDashboard.jsx` | Quick Quote + Claims upload + GLM calibration — internal admin |
| `PricingWizard.jsx` | 6-step health insurance quote wizard with local GLM fallback |
| `ModelRetrainingDashboard.jsx` | Model improvement visualisation (mock data) |

**Infrastructure before this session:**
- Frontend: Vercel (free tier) ✅
- Backend: `https://dac-healthprice-api.onrender.com` (Render free tier) ✅
- Proxy: Cloudflare Worker (`snowy-haze-f313...workers.dev`) → `backend-5frr.onrender.com` ⚠️ removed

---

## Changes Made This Session

### 1. Cloudflare Proxy Removed

`PricingWizard.jsx` previously routed all API calls through a Cloudflare Worker, which itself proxied to a separate Render instance (`backend-5frr.onrender.com`). Both `API` and `CHAT_BACKEND` constants now point directly to the confirmed backend:

```
Before: snowy-haze-f313.poungrotha01555.workers.dev → backend-5frr.onrender.com
After:  dac-healthprice-api.onrender.com (direct)
```

Removes an unnecessary hop, eliminates a second Render instance, and simplifies debugging.

### 2. Life Insurance Pricer Added (`LifeInsurancePricer.jsx`)

New internal actuary workbench tab added to the React app. Implements the full **Mortality Ratio Method** in JavaScript — an exact port of `medical_reader/pricing/calculator.py` and `medical_reader/pricing/assumptions.py`.

**Calculation chain:**
1. Look up `q(x)` from WHO SEA mortality table by age band and gender
2. Apply Cambodia 0.85× adjustment (calibrated from portfolio A/E analysis)
3. Apply additive risk factor adjustments to build Mortality Ratio
4. Classify risk tier (LOW / MEDIUM / HIGH / DECLINE)
5. Compute pure premium: `Face × (q/1,000) × MR`
6. Apply four loading components (expense 12%, commission 10%, profit 5%, contingency 5%)
7. Return gross annual and monthly premiums

**UI features:**
- Real-time calculation — updates as inputs change, no submit button
- Policy parameters: face amount ($10K–$200K), term (5–30 years)
- Applicant profile: age, gender, BMI, alcohol use
- Health flags: smoker, diabetes, hypertension, hyperlipidemia, family CHD history
- Blood pressure: JNC-8 classification shown live (normal/elevated/stage 1/stage 2/crisis)
- Mortality basis card: raw WHO SEA rate, Cambodia-adjusted rate, age band
- Premium build-up bars: pure → expense → commission → profit → contingency → gross
- Active risk factors table: factor name, multiplier, marginal annual cost
- IRC audit footer: assumption version, sources, loading breakdown

**Assumption version**: `v3.0-cambodia-2026-04-14` (matches backend)

### 3. Deployment

Committed and pushed to `PolyTheML/dac-healthprice-frontend`. Vercel auto-deployed.

---

## Backend API Inventory

`https://dac-healthprice-api.onrender.com` exposes (confirmed from `/openapi.json`):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/health/price` | POST | Health insurance GLM pricing |
| `/api/v1/health/price/batch` | POST | Batch quote |
| `/api/v1/health/price/what-if` | POST | Health sensitivity analysis |
| `/api/v1/health/risk-classification` | GET | Risk tier lookup |
| `/api/v1/escalation` | POST | Escalation product pricing |
| `/api/v1/escalation/what-if` | POST | Escalation sensitivity |
| `/api/v2/price` | POST | v2 pricing (GLM) |
| `/api/v2/session` | GET/POST | Session management |
| `/api/v2/chat` | POST | Chat interface |
| `/api/v2/model-info` | GET | Model metadata |
| `/health` | GET | Health check |

**Note**: The life insurance `/pricing/what-if` endpoint (from `api/main.py`) is **not** on this backend — that app is not deployed. The React pricer uses local JS calculation instead.

---

## Cross-references

- [Cambodia Smart Underwriting Engine](../topics/cambodia-smart-underwriting.md) — the backend that produces these premiums
- [Cambodia Risk Factors Reference](../topics/cambodia-risk-factors-reference.md) — assumption tables used in the pricer
- [React Frontend Architecture](../topics/react-frontend-architecture.md) — full frontend structure
- [Frequency-Severity GLM](../topics/frequency-severity-glm.md) — health insurance pricing (separate from life)
- [FWD Vietnam](../entities/fwd-vietnam.md) — referenced by Peter as AI agent recommendation model
- [Pricing Engine Phases](../topics/pricing-engine-phases.md) — how the pricing layer was built
