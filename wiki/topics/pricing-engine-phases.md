# Pricing Engine Enhancement: 5-Phase Roadmap

**Created**: 2026-04-11  
**Last updated**: 2026-04-11  
**Source**: [Pricing Engine Enhancement Plan](../sources/2026-04-11_pricing-engine-enhancement-plan.md)  
**Status**: ✅ Plan approved; ready for Phase 1 implementation

---

## Overview

DAC-UW-Agent pricing engine enhancement to achieve production-grade actuarial calculation. Covers two strategic objectives:
- **Option A**: Actuarial calibration infrastructure (ready for claims data when it arrives)
- **Option C**: Risk model enhancement + fairness testing (IRC Prakas 093 compliance)

**Goal**: Make the internal underwriting tool auditable, calibratable, and compliant before Cambodia's first digital life insurer launches.

**Timeline**: 5 sequential phases (dependencies drive order)  
**Team**: 1 senior backend engineer + actuary oversight  
**Estimated Duration**: 3–4 weeks

---

## Current State

The pricing engine (`medical_reader/pricing/`) is a well-designed, tested GLM-based system with a critical limitation: all actuarial parameters are hardcoded as frozen dataclasses in `assumptions.py`. This creates three problems:

1. **No parameter versioning** — Changing any multiplier requires a code edit, process restart, redeploy
2. **Unused precision** — Lab values (HbA1c, cholesterol) are extracted from PDFs but silently dropped
3. **Coarse age bands** — 10-year bands cause a 2.18× premium jump at age 45 (44yo: q(x)=2.20 → 45yo: q(x)=4.80)
4. **No fairness infrastructure** — Wiki documents fairness requirements but zero code exists
5. **No calibration path** — No mechanism to incorporate claims data when it arrives

---

## Phase 1: Parameter Store Decoupling

**Focus**: Foundational infrastructure — every other phase depends on this  
**Output**: JSON parameter files + parameter loader  
**Time**: ~1 week  
**Risk**: Low (backward-compatible; falls back to hardcoded)

### Problem
Hard-coded assumptions require code changes to adjust pricing. No version history. No ability to test scenarios without redeploying.

### Solution
- Create `medical_reader/pricing/param_store/` directory with JSON files:
  - `mortality_v2.0.json` — 10-year age bands (existing values)
  - `risk_factors_v2.0.json` — 13 risk factor multipliers
  - `loading_v2.0.json` — Expense/commission/profit/contingency ratios
  - `tiers_v2.0.json` — Risk tier thresholds
  - `manifest.json` — Version tracking + history

- New `param_loader.py` that:
  - Reads JSON files at import time
  - Instantiates existing frozen dataclasses from JSON
  - Falls back to hardcoded defaults if files are missing
  - Maintains 100% backward compatibility

- New `version_manager.py` that:
  - Compares two assumption versions
  - Runs test cases through both
  - Returns premium deltas + tier changes

### API Changes
- `GET /pricing/assumptions` — Return active assumption set (transparency for IRC)
- `GET /pricing/assumptions/versions` — Version history
- `POST /pricing/assumptions/compare` — Premium diff between versions

### Success Criteria
- `pytest test_pricing_calculator.py` — all pass
- `GET /pricing/assumptions` returns same values as current hardcoded
- Delete JSON files → system still works (fallback to hardcoded)

---

## Phase 2: Finer Age Bands + Term-Length Adjustment

**Focus**: Smooth premium transitions; activate unused policy term field  
**Output**: 5-year mortality table; term-length multiplier  
**Time**: ~3–4 days  
**Risk**: Low (auto-detection of band type; graceful fallback)

### Problem
10-year age bands create commercial cliffs. A 44-year-old and 45-year-old males have dramatically different mortality rates:
- 44yo: q(x) = 2.20 per 1,000/year
- 45yo: q(x) = 4.80 per 1,000/year
- Jump: +2.18× (118% increase)

This is commercially unjustifiable and creates adverse selection risk. Also, `policy_term_years` is stored but never used in premium math.

### Solution
1. **Create `mortality_v3.0.json`** with 5-year bands (geometrically interpolated):
   - 40-44: 2.20 (male)
   - 45-49: 3.50 (male)
   - 50-54: 4.80 (male)
   - Smooth progression (no cliff)

2. **Update `get_base_mortality_rate()`** to auto-detect band type:
   - If `"25-29"` exists in table → use 5-year logic
   - Else → fall back to 10-year (backward compatible)

3. **Add term-length adjustment** to `calculate_annual_premium()`:
   - 1–5 years: 1.00× (baseline)
   - 6–10 years: 1.03× (longer commitment, better risk profile)
   - 11–15 years: 1.07×
   - 31+ years: 1.25× (risk of mortality improvement over long term)

4. **Update `manifest.json`**: `"mortality": "v3.0"` active

### New Fields
- `PremiumBreakdown.term_adjustment_factor: float = 1.0`

### API Changes
None to existing endpoints; new fields in response bodies are backward-compatible.

### Success Criteria
- Age 44 vs 45 premium: 44yo premium × 1.23 ≈ 45yo premium (vs current 2.18× jump)
- `term_adjustment_factor` appears in `PremiumBreakdown` for all calculations
- `GET /pricing/what-if?age=44` vs `?age=45` shows smooth ~23% increase

---

## Phase 3: Lab Values + New Risk Factors

**Focus**: Precision for complex medical cases; connect dormant lab data  
**Output**: Lab classifiers; occupation/geographic factors  
**Time**: ~1 week  
**Risk**: Low (optional params; None defaults)

### Problem
`LabValues` (HbA1c, cholesterol, triglycerides) are extracted from PDFs by Claude Vision but silently dropped in `ExtractedMedicalData`. A diabetic applicant with:
- HbA1c 6.8% (controlled) gets: ×1.40 (base diabetes multiplier)
- HbA1c 11% (uncontrolled) gets: ×1.40 (same multiplier)

Precision lost. Also, occupation (office worker vs hazardous work) and geographic access (distance to hospital) are not modeled, though they are strong mortality predictors.

### Solution
1. **Extend `ExtractedMedicalData`** with optional lab + demographic fields:
   ```python
   hba1c: Optional[float]
   total_cholesterol: Optional[float]
   hdl_cholesterol: Optional[float]
   ldl_cholesterol: Optional[float]
   triglycerides: Optional[float]
   occupation_class: Optional[str]         # 1=office, 2=light_manual, 3=manual, 4=hazardous
   geographic_zone: Optional[str]          # urban/provincial/rural
   ```

2. **Add classifiers** to `calculator.py`:
   - `classify_hba1c(hba1c)` → "prediabetes", "diabetes_controlled", "diabetes_uncontrolled", "unknown"
   - `classify_cholesterol(total, hdl, ldl, triglycerides)` → "optimal", "borderline_high", "high", "very_high", "unknown" (per ACC/AHA)
   - `classify_occupation(occupation_class)` → "class1", "class2", "class3", "class4", "unknown"

3. **Extend `calculate_mortality_ratio()`** with new optional params (all default None):
   ```python
   hba1c: Optional[float] = None,
   total_cholesterol: Optional[float] = None,
   ...occupation_class, geographic_zone...
   ```

4. **New risk logic** inside `calculate_mortality_ratio()`:
   - **HbA1c Refinement**:
     - Undiagnosed prediabetes (HbA1c 5.7–6.4, no diabetes flag) → +0.10
     - Uncontrolled diabetes (HbA1c ≥ 8) → extra +0.20 on top of base diabetes ×1.40
   - **Cholesterol** (only if `hyperlipidemia` not already flagged):
     - High cholesterol (total >240) → +0.15
     - Very high (LDL >160) → +0.30
   - **Occupation** (new factors):
     - Class 3 (manual labor) → +0.10
     - Class 4 (hazardous work) → +0.30

5. **Create `risk_factors_v2.1.json`** with new multipliers; update manifest: `"risk_factors": "v2.1"`.

6. **Fix silent imputation** in `nodes/pricing.py`:
   - Currently, missing fields default to healthy values without recording the fact
   - Add: `imputation_log = {}; if data.age is None: age=45; imputation_log["age"]="defaulted_45"`
   - Record in audit trail: `state.add_audit_entry(action="field_imputation", details=imputation_log)`

### API Changes
- `GET /pricing/what-if` response gains new optional query params (backward-compatible)

### Success Criteria
- `GET /pricing/what-if?age=45&hba1c=9.5&diabetes=true` returns higher premium than `hba1c=6.8&diabetes=true`
- Imputation audit entries appear in case history when fields are missing
- All existing tests pass; new tests added for lab classifiers

---

## Phase 4: Fairness Testing Module

**Focus**: IRC Prakas 093 compliance; demographic parity auditing  
**Output**: Fairness auditor module; fairness API endpoints  
**Time**: ~1 week  
**Risk**: Very low (independent of other phases; works on synthetic data now)

### Problem
The wiki extensively documents fairness requirements (`underwriting-fairness-audit.md`) but zero code exists. IRC Prakas 093 requires:
- Demographic parity testing (approval rates by gender, age, other protected attributes)
- Explainability per applicant (right to explanation — GDPR/CCPA)
- Audit trail of all decisions for human review
- Appeal mechanism for declined applicants

### Solution
1. **New module**: `medical_reader/pricing/fairness/auditor.py`

2. **Data structures**:
   ```python
   @dataclass
   class FairnessResult:
       metric_name: str                       # "demographic_parity", "premium_disparity", etc.
       groups: Dict[str, float]               # group_label -> metric_value
       max_disparity: float                   # max - min across groups
       within_tolerance: bool
       threshold: float                       # Configured tolerance (e.g., 0.10 = ±10%)
       alert_groups: List[str]
       computed_at: datetime
       n_cases: int
   
   @dataclass
   class FairnessReport:
       report_id: str
       assumption_version: str
       generated_at: datetime
       n_cases: int
       metrics: List[FairnessResult]
       overall_pass: bool
       recommendations: List[str]
   ```

3. **Core functions**:
   - `compute_demographic_parity(cases, group_field, outcome_field="risk_tier", outcome_value="LOW", tolerance=0.10)` → Compare approval rates across groups (e.g., gender); alert if disparity >10%
   - `compute_premium_disparity(cases, group_field, control_for_risk=True, tolerance_pct=0.15)` → Compare mean premiums; optionally control for mortality ratio to detect unexplained disparity
   - `compute_factor_importance(cases)` → Leave-one-out attribution (no ML library); returns Dict[str, float] where each factor's importance = its dollar contribution / total mortality loading. Sums to 1.0. GDPR-compliant right-to-explanation.
   - `run_fairness_audit(cases, assumption_version, demographic_fields=None, include_factor_importance=True)` → Run all metrics; IRC-reportable format
   - `generate_age_band(age: int)` → IRC age brackets: 18–30, 31–45, 46–55, 56–65, 66+

4. **IRC Tests** (per Prakas 093):
   - **Demographic Parity by Gender**: M vs F approval rate disparity ±10%
   - **Demographic Parity by Age Band**: 5 IRC bands; ±10% approval disparity each
   - **Premium Disparity Unadjusted**: M vs F mean premium ±15%
   - **Premium Disparity Risk-Adjusted**: M vs F at same mortality ratio ±5%
   - **Factor Dominance**: Alert if any single factor >40% of total loading (too concentrated)

5. **Add `factor_importance` to `PremiumBreakdown`**:
   ```python
   factor_importance: Dict[str, float] = field(default_factory=dict)
   # e.g., {"smoking": 0.42, "diabetes": 0.28, "bp_stage2": 0.18, ...}
   # Sums to 1.0; no ML library needed
   ```

6. **API Endpoints**:
   - `POST /pricing/fairness-audit` — Run audit on provided cases (or synthetic 500-case portfolio if none provided)
   - `GET /pricing/fairness-audit/latest` — Cached latest report

### Works Without Real Data
- `generate_reference_portfolio(n=1000, seed=42)` creates synthetic Cambodia-like population using WHO prevalence rates (35%/5% smoking M/F, 10% diabetes, 22% HTN, 3.9% obesity)
- `run_fairness_audit()` with no cases provided → uses synthetic portfolio
- **TODAY**: Actuaries can audit pricing for bias without waiting for real applicants
- **LATER**: When cases arrive, same functions work on real data

### Success Criteria
- `POST /pricing/fairness-audit` with no body returns 500-case synthetic report in <5 seconds
- `overall_pass` reflects actual disparity checks (True if all metrics within tolerance)
- `factor_importance` on every `PremiumBreakdown` sums to 1.0
- Plaintext FairnessReport is IRC-submission-ready (all required metrics, transparent)

---

## Phase 5: Calibration Scaffold

**Focus**: Infrastructure for when claims data arrives  
**Output**: Calibration functions; batch what-if API  
**Time**: ~1 week  
**Risk**: Very low (pure functions; no-op when no claims data)

### Problem
No claims data exists yet. But when Cambodia's first digital insurer accumulates claims history (6–12 months), they'll need to:
1. Adjust mortality multipliers based on observed vs. predicted claims
2. Test sensitivity of pricing to each parameter (e.g., "what if smoking multiplier is 1.8 instead of 2.0?")
3. Compare model versions (v2.0 vs v2.1 impact on loss ratio)
4. Understand which factors drive the most premium variance

The infrastructure must be ready NOW, even though it has no data to work with yet.

### Solution
1. **New module**: `medical_reader/pricing/calibration/scaffold.py`

2. **Data structures**:
   ```python
   @dataclass
   class CalibrationResult:
       input_version: str                     # e.g., "v2.0"
       output_version: str                    # e.g., "v2.1"
       parameter_deltas: Dict[str, float]     # factor_name -> suggested new multiplier
       sensitivity_scores: Dict[str, float]   # factor_name -> sensitivity (elasticity)
       loss_ratio_implied: float              # Implied L/R under suggested params
       confidence: float                      # 0–1; low if synthetic, higher with real claims
       is_synthetic: bool                     # True if no real claims used
       notes: str                             # Human-readable explanation
   ```

3. **Core functions**:
   - `generate_reference_portfolio(n=1000, gender_ratio=0.5, seed=42)` → List[Dict]
     - Synthetic cases with Cambodia-appropriate distributions (WHO prevalence rates)
     - Same fields as `ExtractedMedicalData` so it can flow through pricing engine
     - Repeatable (seed-based)

   - `estimate_implied_loss_ratio(assumptions: Dict, portfolio: List[Dict])` → float
     - Run each case through `calculate_annual_premium()`
     - Implied L/R = sum(face_amount × q(x) × MR / 1000) / sum(gross_premium)
     - Sanity-check: does current pricing target reasonable L/R (e.g., 65% for life insurance)?
     - Works with synthetic portfolio TODAY; works with real claims LATER

   - `calibrate_from_claims(claims_data: Optional[List[Dict]], current_assumptions: Dict, learning_rate=0.3)` → CalibrationResult
     - **If `claims_data is None`**: Return no-op result with `is_synthetic=True`, all `parameter_deltas = 0`, `confidence = 0.0`
     - **If `claims_data provided`**: Simple GLM credibility approach:
       - For each risk factor:
         - Compute observed claim rate in group WITH factor
         - Compute predicted claim rate using current model
         - Adjustment = observed / predicted
         - New multiplier = current × (1 + learning_rate × (adjustment - 1))
         - Clamp to [1.0, 8.0] (reasonable bounds)
     - **Pure function**: Does NOT write to param store; does NOT update ASSUMPTIONS
     - Actuaries call `save_assumptions(result, version=...)` after review

   - `sensitivity_sweep(base_assumptions: Dict, factor_name: str, sweep_range=(0.8, 1.3), n_steps=11, test_portfolio=None)` → Dict
     - Sweep one parameter (e.g., smoking multiplier) across range
     - For each value, compute premiums on test portfolio
     - Return: premium impact curve, implied L/R at each step, portfolio statistics
     - Used for: "What if smoking multiplier is 20% lower? How does loss ratio change?"

4. **API Endpoints**:
   - `POST /pricing/batch-what-if` — Run multiple scenarios (max 500 cases) in one call
     - Request: list of case dicts + assumption version
     - Response: list of PremiumBreakdown results + portfolio summary stats
   - `POST /pricing/sensitivity-sweep` — Sweep one parameter
     - Request: factor name, sweep range, base case
     - Response: premium impact curve, implied L/R, portfolio stats

### Current Utility (No Claims Data)
- `estimate_implied_loss_ratio(ASSUMPTIONS, generate_reference_portfolio())` → Verify current pricing targets sensible loss ratio
- `sensitivity_sweep(ASSUMPTIONS, "smoking")` → Understand premium sensitivity to smoking (high sensitivity = high impact factor)
- `batch_what_if([case1, case2, ...], version="v2.0")` → Compare multiple scenarios (e.g., "how many LOW-tier cases at each risk multiplier level?")

### Future Utility (With Claims Data)
- `calibrate_from_claims(claims_data, ASSUMPTIONS)` → Suggested multiplier adjustments
- Store suggested deltas, review with actuary, save new version, compare loss ratios

### Success Criteria
- `POST /pricing/batch-what-if` with 500 cases completes in <5 seconds
- `POST /pricing/sensitivity-sweep?factor_name=smoking&n_steps=11` returns 11-point curve with premium + L/R at each step
- `calibrate_from_claims(None, ASSUMPTIONS)` returns `is_synthetic=True` with all `parameter_deltas = 0`
- `generate_reference_portfolio(n=1000)` produces 1000 cases matching WHO prevalence distributions

---

## Implementation Sequence

### Recommended Order (Driven by Dependencies)

1. **Phase 1 (Param Store)** ← Foundation; everything else depends on this
2. **Phase 2 (Age Bands)** ← Simple, high-value; uses param store
3. **Phase 3 (Lab Values)** ← Extends risk model; uses param store
4. **Phase 4 (Fairness)** ← Independent; can run on synthetic data immediately
5. **Phase 5 (Calibration)** ← Depends on all others for full functionality

This is NOT the phase numbering; it's the implementation order.

---

## Backward Compatibility

**100% preserved.** All new features are additive or use `Optional` params with `None` defaults.

| Existing Usage | Preserved How |
|---|---|
| `from medical_reader.pricing import ASSUMPTIONS` | Falls back to hardcoded frozen dataclasses if JSON missing |
| `calculate_annual_premium(...)` | Signature unchanged; new optional params all default to None |
| `GET /pricing/what-if` | Unchanged; response gains new optional fields |
| `test_pricing_calculator.py` | All 27 tests pass; new tests are additive |
| LangGraph nodes | No changes; optional fields in state default to None |
| FastAPI routes | Existing endpoints unchanged; new endpoints added |

---

## File Changes Summary

### New Files (8)
- `medical_reader/pricing/param_loader.py` — Parameter loader
- `medical_reader/pricing/version_manager.py` — Version comparison
- `medical_reader/pricing/param_store/manifest.json` — Version manifest
- `medical_reader/pricing/param_store/mortality_v*.json` — Mortality tables (2 files: v2.0, v3.0)
- `medical_reader/pricing/param_store/risk_factors_v*.json` — Risk factors (2 files: v2.0, v2.1)
- `medical_reader/pricing/param_store/loading_v2.0.json` — Loading factors
- `medical_reader/pricing/param_store/tiers_v2.0.json` — Tier thresholds
- `medical_reader/pricing/calibration/scaffold.py` — Calibration functions
- `medical_reader/pricing/fairness/auditor.py` — Fairness testing

### Modified Files (8)
- `medical_reader/pricing/assumptions.py` — Add param_loader fallback
- `medical_reader/pricing/calculator.py` — Add lab classifiers, term adjustment, new optional params
- `medical_reader/state.py` — Add lab + occupation fields to ExtractedMedicalData
- `medical_reader/nodes/intake.py` — Extend extraction prompt to request new fields
- `medical_reader/nodes/pricing.py` — Pass new fields to calculator; record imputation audit entries
- `api/routers/pricing.py` — Add 7 new endpoints (batch-what-if, sensitivity-sweep, fairness-audit, assumptions-endpoints)
- `api/models.py` — Add response models for new endpoints
- `test_pricing_calculator.py` — Add tests for new classifiers, term adjustment, phases 2–5

---

## Success Metrics

| Metric | Target | Notes |
|---|---|---|
| **Parameter versioning** | 100% — all multipliers in JSON files | Phase 1 |
| **Age band smoothness** | 44yo→45yo jump <30% (vs current 2.18×) | Phase 2 |
| **Lab precision** | Uncontrolled diabetes premium >controlled | Phase 3 |
| **Fairness audit ready** | Works on synthetic 500-case portfolio | Phase 4 |
| **Calibration scaffold ready** | Pure functions callable with/without claims data | Phase 5 |
| **Backward compatibility** | 100% — all existing tests pass | All phases |
| **IRC compliance** | Fairness report contains all Prakas 093 metrics | Phase 4 |

---

## Related Pages

- [Pricing Engine Enhancement Plan (Source)](../sources/2026-04-11_pricing-engine-enhancement-plan.md) — Approved implementation plan
- [Frequency-Severity GLM](./frequency-severity-glm.md) — Mortality ratio formula and theory
- [Underwriting Fairness Audit](./underwriting-fairness-audit.md) — IRC Prakas 093 requirements and test framework
- [DAC Underwriting Integration](./dac-underwriting-integration.md) — Health insurance pricing engine (related system)
- [Underwriting Audit Trail](./underwriting-audit-trail.md) — Compliance logging framework
- [Operational Architecture](./operational-architecture.md) — Kubernetes/FastAPI deployment stack
- [Actuarial Scenario Agent](./actuarial-scenario-agent.md) — NL what-if agent layered on top of this engine (2026-04-12)
- [Medical Doc → Health Pricing Bridge](./medical-doc-health-pricing-bridge.md) — PDF → health quote bridge using this engine (2026-04-12)
