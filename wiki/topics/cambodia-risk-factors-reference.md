# Cambodia Risk Factors Reference

**Created**: 2026-04-14  
**Last updated**: 2026-04-14  
**Type**: Technical Reference  
**Used by**: `medical_reader/pricing/assumptions.py` (v3.0)

---

## Quick Reference Tables

### Standard Actuarial Risk Multipliers (Applied by All Cases)

| Risk Factor | Multiplier | Effect | Medical Evidence |
|-------------|-----------|--------|------------------|
| Smoker (current) | 2.00 | +100% mortality | RP-2000 tables |
| Heavy Alcohol | 1.25 | +25% mortality | Liver disease, trauma |
| BMI <18.5 (underweight) | 1.20 | +20% mortality | Nutritional risk |
| BMI 25-29.9 (overweight) | 1.15 | +15% mortality | Metabolic risk |
| BMI 30-34.9 (obese I) | 1.35 | +35% mortality | Cardiovascular risk |
| BMI 35+ (obese II/III) | 1.60 | +60% mortality | Severe metabolic risk |
| BP elevated (120-129/<80) | 1.10 | +10% mortality | JNC-8 guidelines |
| BP Stage 1 (130-139/80-89) | 1.25 | +25% mortality | Hypertension onset |
| BP Stage 2 (≥140/≥90) | 1.50 | +50% mortality | Severe hypertension |
| Diabetes | 1.40 | +40% mortality | T2DM complications |
| Hypertension | 1.25 | +25% mortality | Controlled HTN |
| High Cholesterol | 1.20 | +20% mortality | Cardiovascular risk |
| Family History (CHD) | 1.30 | +30% mortality | Genetic predisposition |

**Application**: All multipliers apply **additively**, not multiplicatively.  
**Formula**: `Mortality Ratio = 1.0 + Σ (multiplier - 1.0)`  
**Example**: Smoker (2.0) + Obese (1.35) = MR = 1.0 + (2.0-1.0) + (1.35-1.0) = 2.35×

---

### Cambodia-Specific: Occupational Multipliers

**Source**: [CambodiaOccupationalMultipliers](../../../medical_reader/pricing/assumptions.py)

#### Motorbike-Related (High-Risk)

| Profile | Multiplier | Rationale | Geographic Relevance |
|---------|-----------|-----------|----------------------|
| Motorbike Courier (professional) | 1.45 | 8+ hours/day on roads, high speed, heavy traffic, limited protective gear | Urban centers (PP, SR) |
| Motorbike Daily (regular commute) | 1.25 | 2+ hours/day road exposure, variable traffic patterns | All provinces |
| Motorbike Occasional (<weekly) | 1.10 | Infrequent use, but higher risk than none | All provinces |
| Motorbike Never | (baseline in occ) | Baseline assumption | All provinces |

**Key Fact**: Motorbike mortality in Cambodia is 4-6× higher than car travel (WHO SEARO 2022). This is **the primary occupational risk lever** in the underwriting model.

#### Construction & Manual Trades (Elevated-Risk)

| Profile | Multiplier | Rationale | Risk Categories |
|---------|-----------|-----------|------------------|
| Construction Worker | 1.35 | Falls, equipment entanglement, heat exhaustion, dehydration | Trauma, occupational disease |
| Manual Labor (general) | 1.20 | Physical hazard exposure (tools, materials, heights) | Trauma |
| Retail/Service | 1.05 | Low-moderate occupational risk | Foot-related strain |

#### Healthcare (Baseline+)

| Profile | Multiplier | Rationale |
|---------|-----------|-----------|
| Healthcare Worker | 1.05 | Bloodborne pathogen exposure, stress, shift work |

#### Sedentary (Baseline/Discount)

| Profile | Multiplier | Rationale |
|---------|-----------|-----------|
| Office/Desk | 1.00 | Baseline, sedentary, low occupational hazard |
| Retired | 0.95 | No ongoing occupational exposure, lower stress |

**Implementation Note**: When both occupation and motorbike usage are provided, **use the higher multiplier** (not both additive). For example:
- Construction + Occasional motorbike → Use 1.35 (construction), not 1.35 + 1.10
- Office + Daily motorbike → Use 1.25 (motorbike daily), not 1.00 + 1.25

---

### Cambodia-Specific: Endemic Disease Multipliers

**Source**: [CambodiaEndemicMultipliers](../../../medical_reader/pricing/assumptions.py)

#### Severity Tiers

| Tier | Provinces | Multiplier Range | Disease Profile |
|------|-----------|-----------------|-----------------|
| **Urban Baseline** | Phnom Penh | 1.00 | Low endemic disease risk (sanitation, healthcare access) |
| **Low-Moderate** | Kandal, Takeo, Battambang | 1.03–1.05 | Seasonal dengue, low malaria |
| **Moderate** | Siem Reap, Kampong Cham, Kampong Thom | 1.05–1.08 | Dengue prevalence 10-20%, sporadic malaria |
| **Moderate-High** | Sihanoukville, Pursat | 1.07–1.08 | Dengue 15-25%, warm climate |
| **High** | Kratie, Preah Vihear | 1.15–1.18 | Forested areas, malaria transmission |
| **Very High** | Mondulkiri, Ratanakiri | 1.28–1.30 | **Endemic belt**: High malaria + dengue + TB transmission |

#### Disease Breakdown by Province (2024 WHO/CDC Data)

| Province | Dengue Risk | Malaria Risk | TB Prevalence | Net Multiplier |
|----------|------------|-------------|---------------|-----------------|
| Phnom Penh | Low (2-5%) | None | Moderate | 1.00 |
| Kandal (near PP) | Low | None | Low | 1.03 |
| Siem Reap | Moderate (8-12%) | Low | Low-Moderate | 1.05 |
| Sihanoukville | High (15-20%) | None | Low | 1.08 |
| Battambang | Low-Moderate | Low | Low | 1.05 |
| Kampong Cham | Moderate (10-15%) | Moderate | Moderate | 1.07 |
| Kampong Thom | Moderate | Moderate | Moderate | 1.08 |
| Takeo | Low | None | Low | 1.04 |
| Pursat | Moderate | Low | Low | 1.07 |
| Kratie | Moderate-High | Moderate-High | High | 1.15 |
| Preah Vihear | High | High | High | 1.18 |
| Mondulkiri | **High** | **High** | **Very High** | **1.30** |
| Ratanakiri | **High** | **High** | **Very High** | **1.28** |
| Rural (unknown) | Moderate | Moderate | High | 1.12 |

**Key Insight**: **Mondulkiri and Ratanakiri are epidemiological hotspots.** The +30% surcharge reflects:
- Malaria transmission zone (entomological surveillance)
- Limited healthcare infrastructure (delays in treatment)
- High TB prevalence (respiratory comorbidity)
- Poor road access (medical evacuation delays)

These provinces historically show 2-3× higher claims experience than urban areas.

---

### Cambodia-Specific: Healthcare Tier Reliability Discount

**Source**: [CambodiaHealthcareTierDiscount](../../../medical_reader/pricing/assumptions.py)

#### Facility Classification

| Tier | Examples | Standards | Discount Factor |
|------|----------|-----------|-----------------|
| **TierA** | Calmette Hosp., Royal Phnom Penh, Select private chains | Certified labs, EHR systems, senior radiologists, ACS/CAP accreditation | **0.97** (−3%) |
| **TierB** | Provincial hospitals (Siem Reap, Battambang refs), mid-tier private | Basic labs, equipment maintenance, experienced techs but no intl. accred. | 1.00 (no change) |
| **Clinic** | Local health centers, solo practitioners, NGO clinics | Basic equipment, no lab certification, limited specialty referral | 1.05 (+5%) |
| **Unknown** | Not specified on exam document | Conservative assumption | 1.03 (+3%) |

#### Rationale

**TierA Discount (−3%)**: High-confidence exam reduces underwriting uncertainty.
- Multiple verification (physical exam + imaging + labs)
- Lower chance of missed cardiovascular, renal, or metabolic disease
- Reduces post-issue claims surprise

**TierB (No change)**: Adequate but not superior to baseline.
- Meets IRC minimum standards
- Standard uncertainty level

**Clinic Surcharge (+5%)**: Lower facility reliability increases uncertainty risk.
- Limited diagnostic capability (no imaging)
- Higher chance of missed findings (aneurysm, malignancy, etc.)
- **Triggers human review flag** for completeness

**Unknown Surcharge (+3%)**: Conservative when facility unclear.
- Default assumption: local clinic standard

#### Implementation

Applied as **multiplicative factor** to gross premium (not pure premium):

```
Final Premium = Gross Premium × Healthcare Tier Discount
```

**Example**:
- Case with gross premium $500/year and clinic exam
- Final = $500 × 1.05 = $525/year (+$25 risk surcharge)

---

## Mortality Ratio Calculation: Full Pipeline

```
Base Mortality Rate (q_x)
    ↓ (per 1,000/year from WHO tables)
    × CAMBODIA_MORTALITY_ADJ (0.85)
    ↓
Base q_x (Cambodia-adjusted)
    ↓
Mortality Ratio = 1.0 + Σ Risk Factors
    ├─ Standard factors (smoking, BMI, BP, conditions)
    ├─ Cambodia Occupational multiplier
    ├─ Cambodia Endemic multiplier
    └─ (Capped at 5.0x max)
    ↓
Adjusted Mortality Ratio
    ↓
Pure Premium = Face Amount × (q_x / 1000) × MR
    ↓
Loading Factors (32% total)
    ├─ Expense: 12%
    ├─ Commission: 10% (Cambodia agent rate)
    ├─ Profit: 5%
    └─ Contingency: 5%
    ↓
Gross Premium = Pure Premium × (1 + 0.32)
    ↓
Healthcare Tier Discount
    ↓
Final Premium = Gross Premium × Healthcare Tier Factor
```

---

## IRC Disclosure Examples

### Example Case: 45M Construction Worker, Smoker, Mondulkiri

**Premium Calculation Disclosure**:

```
BASE MORTALITY RATE (q_x):     4.8 per 1,000/year (age 45, male)
CAMBODIA ADJUSTMENT (0.85):     4.08 per 1,000/year

MORTALITY RATIO ADJUSTMENTS:
  + Smoking:                    +100% (2.00x multiplier)
  + Blood Pressure Stage 1:     +25%  (1.25x multiplier)
  + Construction (occupational): +25%  (1.25x multiplier)
  + Mondulkiri (endemic):       +30%  (1.30x multiplier)
  ────────────────────────────────────
  = Final Mortality Ratio:      2.80x

PURE PREMIUM:
  Face Amount:                  $75,000
  Pure Premium = $75,000 × (4.08/1000) × 2.80 = $860.00

LOADING FACTORS (32%):
  Expense (12%):                $103.20
  Commission (10%):              $86.00
  Profit (5%):                   $43.00
  Contingency (5%):              $43.00
  ────────────────────────────────────
  Total Loading:                $275.20

GROSS PREMIUM:                  $1,135.20

HEALTHCARE TIER (Local Clinic):
  Discount Factor:              1.05 (+5%)
  ────────────────────────────────────

FINAL ANNUAL PREMIUM:           $1,191.96
FINAL MONTHLY PREMIUM:          $99.33
```

**IRC-Required Justification**: "Premium reflects high occupational hazard (construction), endemic disease risk in Mondulkiri province (+30% surcharge per WHO SEARO epidemiology), and smoking status (+100%). Healthcare exam conducted at local clinic (reliability surcharge +5%). All assumptions transparent per v3.0-cambodia-2026-04-14."

---

## Maintenance & Calibration (Quarterly)

### A/E Monitoring

Track actual claims vs. expected:
- **Target A/E Ratio**: ~0.95–1.05 (actual costs ÷ expected costs)
- **Cambodia baseline**: 0.85 (from portfolio historical experience)

If A/E > 1.10 → Assumptions too conservative, consider parameter adjustment  
If A/E < 0.80 → Assumptions too aggressive, consider recalibration

### Seasonal Adjustments (Future Enhancement)

- **Dengue Season (June–November)**: Consider +5% endemic surcharge for provinces with Dengue risk >10%
- **Construction Season (Nov–May)**: Consider +10% occupational surcharge during peak building season

---

## References & Sources

- **WHO South-East Asia Region mortality tables**: https://www.who.int/teams/noncommunicable-diseases/cancer/tools/mortality-trends
- **Cambodia malaria epidemiology**: CDC Malaria Atlas Project
- **Dengue surveillance 2024**: Ministry of Health Cambodia weekly reports
- **Occupational risk**: ICMR occupational mortality studies (India analogues, adjusted for Cambodia)
- **1994 GAM & RP-2000**: North American baseline tables (adapted)


---

## Cross-references

- [Cambodia Smart Underwriting Engine](./cambodia-smart-underwriting.md) — implementation that uses these tables
- [React Frontend Architecture](./react-frontend-architecture.md) — JS port of these assumptions in LifeInsurancePricer.jsx
- [Pricing Engine Phases](./pricing-engine-phases.md) — how these assumptions evolved across versions
- [Underwriting Risk Classification](./underwriting-risk-classification.md) — tier thresholds that use these multipliers
- [Underwriting Audit Trail](./underwriting-audit-trail.md) — IRC compliance and assumption versioning
- [Frequency-Severity GLM](./frequency-severity-glm.md) — health insurance model (separate from life)
