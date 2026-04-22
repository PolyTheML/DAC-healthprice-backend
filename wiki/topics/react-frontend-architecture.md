# React Frontend Architecture

**Created**: 2026-04-14  
**Last updated**: 2026-04-15  
**Sources**: [Peter Feedback & Frontend Deployment](../sources/2026-04-14_peter-feedback-frontend-deployment.md) · [Dashboard Deployment](../sources/2026-04-15_dashboard-drift-monitor-deployment.md)

---

## Overview

The DAC platform frontend is a React SPA deployed on Vercel (free tier) at:  
**`https://dac-healthprice-frontend.vercel.app`**

It functions as an **internal actuarial workbench** — not a customer-facing tool. Access is gated by a simple hard-coded login (3 staff users). Per [Peter's guidance](../sources/2026-04-14_peter-feedback-frontend-deployment.md), the UI is "well designed for demonstration/sample"; the priority is strengthening the background calculation logic.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 19 + Vite 8 |
| Styling | Inline styles (no CSS framework) |
| State | `useState` / `useMemo` (no external state library) |
| Routing | Manual `page` state + conditional rendering |
| Deployment | Vercel (free tier, auto-deploys on git push) |
| Backend | `https://dac-healthprice-api.onrender.com` (Render free tier) |

---

## Component Map

### `App.jsx` — Shell

- Login gate (`sessionStorage` persistence)
- Top navbar with page state routing
- Pages: Home | Pricing | Life Insurance | About | Contact

### `PricingWizard.jsx` — Health Insurance Quoting

6-step wizard for health insurance quotes (Profile → Health → Lifestyle → Plan → Review → Quote).

**Pricing logic:**
- Primary: calls `/api/v2/price` on backend (Poisson-GLM model)
- Fallback: local log-linear GLM calculation in JS when backend unavailable
- Features: escalation product toggle, jitter-based price banding, underwriting rule engine

**API**: `https://dac-healthprice-api.onrender.com`  
(Previously proxied through Cloudflare Worker — removed 2026-04-14)

### `InsuranceDashboard.jsx` — Internal Admin

Admin dashboard for insurance company pilots. Two workflows:
1. Quick Quote — instant GLM-based health insurance pricing
2. Claims data upload + GLM calibration

Hard-coded GLM coefficients (v2.2) stored in `COEFF` object — actuaries can see the full model.

### `ModelRetrainingDashboard.jsx` — Model Improvement Visualisation

Shows how model metrics improve as claims data accumulates. Currently uses mock data (v2.3 → v2.4 transition). Intended for stakeholder education.

### `DriftMonitor.jsx` — PSI Drift Chart ⭐ NEW (2026-04-15)

Shows 30-day PSI trend fetched from `GET /dashboard/stats`. Recharts `LineChart` with reference lines at 0.10 (warning) and 0.25 (drift). Graceful fallback message when backend is unavailable.

**Reads**: `json.psi.current`, `json.psi.status`, `json.psi_time_series`

### `UnderwriterQueue.jsx` — HITL Review Queue ⭐ NEW (2026-04-15)

Lists pending `manual_review` quotes from `hitl_queue.pending_cases`. Each row expands to show the AI `reasoning_trace`. Approve / Decline buttons `POST /cases/{id}/review`.

**Reads**: `json.hitl_queue.pending_cases`  
**Writes**: `POST /cases/{case_id}/review`

### `LifeInsurancePricer.jsx` — Life Insurance Workbench + Dashboard (updated 2026-04-15)

Internal actuarial tool implementing the **Mortality Ratio Method** — an exact JS port of the Python backend calculator. See [Pricing Engine Phases](./pricing-engine-phases.md) for the full methodology.

**Inputs**: age, gender, face amount, policy term, BMI, alcohol use, health flags (smoker, diabetes, hypertension, hyperlipidemia, family CHD), blood pressure (systolic/diastolic)

**Outputs** (all computed live with no API call):
- Base mortality rate from WHO SEA table × Cambodia 0.85 adjustment
- Mortality ratio (additive risk factor accumulation)
- Risk tier: LOW / MEDIUM / HIGH / DECLINE
- Premium build-up: pure → expense (12%) → commission (10%) → profit (5%) → contingency (5%) → gross
- Per-factor marginal cost table
- IRC audit footer with assumption version

**Assumption version**: `v3.0-cambodia-2026-04-14` (matches `medical_reader/pricing/assumptions.py`)

Now hosts a two-tab layout: **Pricing Calculator** | **Underwriter Dashboard**. The dashboard tab renders `DriftMonitor` and `UnderwriterQueue`.

---

## Backend API

`https://dac-healthprice-api.onrender.com` — runs `C:\DAC\dac-health\backend\app\main.py`  
Repo: `PolyTheML/DAC-healthprice-backend` (submodule of `C:\DAC\dac-health`)

Key endpoints used by frontend:

| Endpoint | Used by |
|----------|---------|
| `/api/v2/price` | PricingWizard |
| `/api/v2/session` | PricingWizard, InsuranceDashboard |
| `/api/v2/chat` | PricingWizard (chat tab) |
| `/api/v1/health/price` | InsuranceDashboard |
| `/dashboard/stats` | DriftMonitor, UnderwriterQueue ⭐ NEW |
| `/cases/{id}/review` | UnderwriterQueue (approve/decline) ⭐ NEW |

**Note**: The underwriting agent (`C:\DAC-UW-Agent`) with `/cases`, `/pricing/what-if` endpoints is **not deployed**. `LifeInsurancePricer` pricing runs entirely client-side. Dashboard endpoints are on the health backend, adapted to `hp_quote_log` schema.

---

## Deployment Flow

```
git push → GitHub (PolyTheML/dac-healthprice-frontend)
              ↓
          Vercel auto-build (Vite)
              ↓
    https://dac-healthprice-frontend.vercel.app
```

The Render backend is a separate deployment triggered from `PolyTheML/DAC-healthprice-backend`.

---

## Known Limitations

| Issue | Severity | Notes |
|-------|----------|-------|
| Credentials hardcoded in `App.jsx` | Medium | Acceptable for pilot; move to backend auth before production |
| `ModelRetrainingDashboard` uses mock data | Low | Replace with live `/api/v2/model-info` data when ready |
| Life insurance pricer: local only | Low | Wire to `api/main.py` when deployed on Render |
| Render free tier cold starts (~30s) | Low | Acceptable for demo; upgrade for production |
| `human_override_rate` always zero | Low | Health backend has no UW override tracking yet; implement if needed |
| PSI reference distribution is synthetic | Low | Replace `_HEALTH_PSI_REF` with production-fitted distribution after 6+ months of quote data |

---

## Cross-references

- [Peter Feedback & Frontend Deployment](../sources/2026-04-14_peter-feedback-frontend-deployment.md) — session context
- [Cambodia Smart Underwriting Engine](./cambodia-smart-underwriting.md) — backend the pricer mirrors
- [Cambodia Risk Factors Reference](./cambodia-risk-factors-reference.md) — assumption tables
- [Pricing Engine Phases](./pricing-engine-phases.md) — pricing methodology evolution
- [Frequency-Severity GLM](./frequency-severity-glm.md) — health insurance model (separate)
- [Automatic Escalation Products](./automatic-escalation-products.md) — escalation feature in PricingWizard
