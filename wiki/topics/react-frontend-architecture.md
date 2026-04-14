# React Frontend Architecture

**Created**: 2026-04-14  
**Last updated**: 2026-04-14  
**Source**: [Peter Feedback & Frontend Deployment](../sources/2026-04-14_peter-feedback-frontend-deployment.md)

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

### `LifeInsurancePricer.jsx` — Life Insurance Workbench ⭐ NEW (2026-04-14)

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

---

## Backend API

`https://dac-healthprice-api.onrender.com` — runs `app/main.py` (health pricing platform)

Key endpoints used by frontend:

| Endpoint | Used by |
|----------|---------|
| `/api/v2/price` | PricingWizard |
| `/api/v2/session` | PricingWizard, InsuranceDashboard |
| `/api/v2/chat` | PricingWizard (chat tab) |
| `/api/v2/admin/upload-dataset` | PricingWizard admin panel |
| `/api/v1/health/price` | InsuranceDashboard |

**Note**: The underwriting API (`api/main.py`) with life insurance endpoints (`/cases`, `/pricing/what-if`) is **not deployed** on this Render instance. The `LifeInsurancePricer` runs the actuarial calculation entirely client-side.

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
| Life insurance pricer: local only | Low | Wire to `api/main.py` when deployed |
| Render free tier cold starts (~30s) | Low | Acceptable for demo; upgrade for production |

---

## Cross-references

- [Peter Feedback & Frontend Deployment](../sources/2026-04-14_peter-feedback-frontend-deployment.md) — session context
- [Cambodia Smart Underwriting Engine](./cambodia-smart-underwriting.md) — backend the pricer mirrors
- [Cambodia Risk Factors Reference](./cambodia-risk-factors-reference.md) — assumption tables
- [Pricing Engine Phases](./pricing-engine-phases.md) — pricing methodology evolution
- [Frequency-Severity GLM](./frequency-severity-glm.md) — health insurance model (separate)
- [Automatic Escalation Products](./automatic-escalation-products.md) — escalation feature in PricingWizard
