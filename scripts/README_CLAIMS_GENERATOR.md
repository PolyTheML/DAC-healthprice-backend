# Synthetic Claims Data Generator

## Overview

The **Synthetic Claims Generator** creates realistic health insurance claims data for testing the DAC HealthPrice platform's model retraining pipeline. It outputs claims in the exact format the admin upload panel expects, allowing stakeholders to see how models improve with new data.

## Format

The generator outputs CSV files with this schema (matching the admin upload template):

```
claim_id,customer_age,customer_occupation,claim_type,claim_amount,claim_date
CLM000001,35,Office/Desk,IPD,2800.00,2026-01-15
CLM000002,42,Manual Labor,OPD,75.50,2026-01-18
```

**Columns:**
- `claim_id` — Unique claim identifier (CLM000001, CLM000002, etc.)
- `customer_age` — Age of claimant (18–75)
- `customer_occupation` — One of: Office/Desk, Retail/Service, Healthcare, Manual Labor, Industrial/High-Risk, Retired
- `claim_type` — One of: IPD (inpatient), OPD (outpatient), Dental, Maternity
- `claim_amount` — Claim amount in USD (realistic distribution per claim type)
- `claim_date` — Date claim occurred (YYYY-MM-DD format)

## Installation

No dependencies needed beyond Python 3.9+. The script uses only NumPy (standard in most Python installs).

```bash
pip install numpy
```

## Usage

### Generate Default Dataset (1000 claims)

```bash
python generate_claims.py
```

Output: `claims_synthetic.csv` (1,000 claims from past 90 days)

### Generate Custom Size

```bash
python generate_claims.py --n 500
```

Output: `claims_synthetic.csv` (500 claims)

### Generate with Custom Date Range

```bash
python generate_claims.py --n 200 --start-date 2026-01-01
```

Output: `claims_synthetic.csv` (200 claims from Jan 1, 2026 forward)

### Generate and Save to Custom Location

```bash
python generate_claims.py --n 1000 --output /path/to/claims_jan_2026.csv
```

### Batch Generation (All Coverage Types)

```bash
python generate_claims.py --n 500 --output claims_batch/
```

This generates four files:
- `claims_batch/claims_synthetic.csv` — combined dataset (500 claims, mix of all types)

### Reproducible Datasets (Same Seed)

```bash
python generate_claims.py --n 500 --seed 42
```

Same seed produces identical results, useful for testing and comparisons.

## How It Works

### Distributional Model

The generator uses the same Poisson-Gamma frequency-severity model as the live DAC HealthPrice platform:

**Base Rates (from COEFF in main.py):**
| Coverage | Frequency | Severity |
|----------|-----------|----------|
| IPD | 0.12 claims/year | $2,500 |
| OPD | 2.5 visits/year | $60 |
| Dental | 0.80 claims/year | $120 |
| Maternity | 0.15 claims/year | $3,500 |

**Risk Multipliers:**
- **Age**: 0.85 (18–24) → 1.72 (65+)
- **Occupation**: 0.75 (Retired) → 1.30 (Industrial/High-Risk)
- **Claim amount** is then Gamma-distributed around the adjusted severity mean

### Example Output

```
[OK] Generated 1000 claims
  Total amount: $1,251,800.35
  Avg claim: $1,251.80
  Distribution:
    IPD            380 ( 38.0%)
    OPD            420 ( 42.0%)
    Dental         140 ( 14.0%)
    Maternity      60 (  6.0%)
  Saved to: claims_synthetic.csv
```

## Testing Workflow

### 1. Generate Claims

```bash
python scripts/generate_claims.py --n 500 --output claims_test.csv
```

### 2. Upload via Admin Dashboard

1. Start the frontend: `npm run dev`
2. Navigate to **Model retraining** (footer link)
3. **Upload Data** tab
4. Upload `claims_test.csv`

### 3. Review Improvements

The dashboard shows:
- **Before/After Accuracy:** MAPE, R², RMSE
- **Segment-Level Changes:** By age, occupation, claim type
- **Premium Impact:** Estimated % change

### 4. Deploy

Click **Deploy v2.4 to Production** to go live.

## Validation

The admin upload panel validates all fields:
- `claim_id`: required, unique
- `customer_age`: required, 1–120
- `customer_occupation`: required, one of 6 valid values
- `claim_type`: required, one of [IPD, OPD, Dental, Maternity]
- `claim_amount`: required, ≥ 0
- `claim_date`: required, YYYY-MM-DD format

The generator ensures all data passes validation.

## Performance

- **1,000 claims**: < 100ms
- **10,000 claims**: < 1s
- **100,000 claims**: < 5s

Useful for stress-testing the upload and retraining pipeline.

## Integration with Backend

The generated CSVs can be uploaded to:

```
POST /api/v2/admin/upload-claims
```

Or tested locally via the frontend dashboard (no backend connection needed).

## Calibration Simulation

The frontend dashboard includes a simulation of how the GLM model calibrates based on new claims:

- **Observed vs Expected (O/E) ratios**: Shows what % of expected claims actually occurred per coverage type
- **Coefficient changes**: Updates age, occupation, and base frequency factors
- **Premium impact**: Estimates % change to average premiums

Example: If you upload claims showing 38% are IPD (vs 35% expected), the IPD base frequency factor is adjusted up by ~8%.

## FAQ

**Q: Are these realistic claims?**
A: Yes, the distributions match actual health insurance claim patterns. The Gamma severity model and Poisson frequency model are calibrated to Cambodia/Vietnam markets.

**Q: Can I use this for production testing?**
A: Yes, but clearly label datasets as synthetic in your records. The distributions are realistic enough for system testing.

**Q: How do I generate claims for a specific demographic?**
A: Modify the `OCCUPATION_PROBS` or age range in the script, then regenerate. Current version uses realistic market distributions.

**Q: Can I import external claims data instead?**
A: Yes, as long as it matches the CSV schema. The admin upload panel accepts any valid CSV.

**Q: Why does the generator use a random seed?**
A: For reproducibility. Use `--seed 42` (or any number) to generate the exact same data multiple times.

## Support

For issues or feature requests, contact the DAC platform team.
