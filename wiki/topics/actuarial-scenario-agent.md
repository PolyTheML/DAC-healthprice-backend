# Actuarial Scenario Agent (What-If Analysis)

**Created**: 2026-04-12  
**Last updated**: 2026-04-12  
**Status**: ✅ Built — `POST /api/v2/scenario-agent` live in `app/main.py`  
**Related**: [Pricing Engine Phases](./pricing-engine-phases.md) · [Augmented Underwriter Workflow](./augmented-underwriter-workflow.md) · [Medical Doc → Health Pricing Bridge](./medical-doc-health-pricing-bridge.md)

---

## What It Is

A tool-use AI agent endpoint that lets actuaries ask natural language questions about pricing
and receive a narrative synthesis backed by live GLM calculations.

Instead of writing code or constructing JSON payloads, an actuary types:

> *"How does premium change for smokers aged 25–65 in Silver tier?"*

The agent runs the scenarios autonomously, interprets the results actuarially, and returns a
written answer with specific dollar amounts, percentages, and flagged anomalies.

---

## Architecture

```
POST /api/v2/scenario-agent
       │
       ▼
  ScenarioAgentRequest
  { question, base_profile, max_quotes }
       │
       ▼
  Agentic loop (Haiku 4.5, ≤12 steps)
  ┌─────────────────────────────────┐
  │  run_quote tool                 │  → _glm_predict() (direct Python call)
  │  sweep_parameter tool           │  → N × run_quote
  └─────────────────────────────────┘
       │
       ▼
  { narrative, quotes_run, data[], question }
```

**Model**: `claude-haiku-4-5-20251001` — chosen for cost efficiency; a sweep of 30 quotes
uses the cheap model for the tool calls and only pays for narrative generation.

**No HTTP roundtrip**: Both tools call `_glm_predict()` as a direct Python function call
inside the same process, so there is no latency from internal HTTP routing.

---

## Tools Available to the Agent

### `run_quote`

Single health insurance quote. Accepts any subset of the full `PricingRequest` schema;
missing fields fall back to `_AGENT_DEFAULT_PROFILE` (35yo Male, Phnom Penh, Silver, Never).

Key outputs per quote: `total_annual_premium`, `total_monthly_premium`,
`ipd_frequency`, `ipd_severity`, `ipd_expected_cost`, `risk_factors_applied`.

### `sweep_parameter`

Varies one parameter across an ordered list of values, holding everything else constant.
Returns a table of quotes — the standard actuarial sensitivity test.

```json
{
  "param": "age",
  "values": [25, 35, 45, 55, 65],
  "base_profile": { "smoking_status": "Current", "ipd_tier": "Gold", "region": "Phnom Penh" }
}
```

---

## Cost Guard

`max_quotes` (default 30, hard cap 60) limits total GLM calls per request. The quota is
shared across all tool calls in the session, so the agent cannot exceed it regardless of
how many steps it takes. The response always includes `quotes_run` so costs can be audited.

---

## Example Questions Actuaries Can Ask

| Question | What the agent does |
|---|---|
| "How does premium change for smokers aged 25-65?" | `sweep_parameter(age, [25..65])` × 2 smoking groups |
| "Compare Phnom Penh vs Rural Areas for a 45yo with diabetes" | 2 × `run_quote` with region override |
| "Which occupation type has the highest IPD premium?" | `sweep_parameter(occupation_type, all 6 values)` |
| "Show me the Gold vs Silver tier premium difference across age bands" | 2 sweeps on age × tier |
| "How much does adding maternity rider add for 30yo females?" | 2 × `run_quote` with/without maternity |

---

## Integration with Augmented Underwriter Workflow

The scenario agent sits in the **actuarial analysis layer** — between the raw GLM engine and
the human underwriter. It removes the need for an actuary to write Python or craft JSON to
explore the model:

```
Actuary question (NL)
       ↓
Scenario Agent (this)   ← runs GLM scenarios
       ↓
Narrative + data table
       ↓
Actuary reviews, accepts or asks follow-up
```

This pattern follows the [Augmented Underwriter Workflow](./augmented-underwriter-workflow.md)
principle: AI handles the research (scenario sweeps, number crunching), humans handle
interpretation and decisions.

---

## Implementation Notes

- **Location**: `app/main.py` lines after the chat proxy (`POST /api/v2/chat`)
- **Auth**: uses `verify_pricing_auth` dependency (same as all v2 endpoints)
- **Internal helpers**: `_build_glm_req()`, `_execute_run_quote()`, `_execute_sweep()`
- **Bug fix included**: `import httpx` was missing from `app/main.py` (pre-existing); added alongside this feature

---

## Limitations and Future Work

- Extended lifestyle factors (BMI, alcohol, stress) currently fixed to neutral defaults in
  agent-initiated quotes. A future improvement would expose these as additional tool params.
- The `base_profile` override only affects fields explicitly listed; the default profile
  assumes a Cambodian urban non-smoker, which may not suit Vietnam-market questions.
- No streaming yet — the full narrative is returned at once. Streaming via SSE would
  improve perceived latency for long sweeps.
