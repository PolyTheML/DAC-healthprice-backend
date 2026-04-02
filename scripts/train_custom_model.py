"""
DAC HealthPrice — Prospect Calibration Pilot: Custom Model Training
====================================================================
Trains a prospect-specific pricing model by calibrating the baseline
Poisson-Gamma GLM coefficients against the prospect's historical claims.

Method: Experience rating (O/E adjustment)
  - Frequency: observed vs expected claim rates per coverage type
  - Severity:  Gamma GLM fitted on prospect claims, age-band factors extracted
  - All other factors (smoking, exercise, occupation, region) inherit baseline

The output is a custom COEFF dict (same schema as the global COEFF in main.py)
stored at models/custom/{prospect_id}/coeff.json, plus a report.json.

Usage:
    python scripts/train_custom_model.py --prospect-id acme-insurance --claims data.csv
    python scripts/train_custom_model.py --prospect-id acme-insurance --claims data.csv --holdout 0.25

Required CSV columns:
    claim_id, customer_age, claim_type, claim_amount, claim_date
    claim_type must be one of: IPD, OPD, Dental, Maternity

Optional CSV columns (improve calibration quality):
    customer_occupation  (Office/Desk | Retail/Service | Healthcare | Manual Labor | Industrial/High-Risk | Retired)
    customer_gender      (Male | Female | Other)
    customer_smoking     (Never | Former | Current)
    region               (Phnom Penh | Siem Reap | Battambang | ...)
    preexist_count       (integer 0-5)
"""

import os, sys, json, argparse
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import GammaRegressor
    from sklearn.model_selection import train_test_split
except ImportError:
    sys.exit("Missing dependencies — run: pip install numpy pandas scikit-learn")

SCRIPT_DIR = Path(__file__).parent
MODEL_DIR  = SCRIPT_DIR.parent / "models"

# Must match main.py
BASELINE_COEFF = {
    "base_freq":  {"ipd": 0.12,  "opd": 2.5,  "dental": 0.80, "maternity": 0.15},
    "base_sev":   {"ipd": 2500,  "opd": 60,   "dental": 120,  "maternity": 3500},
    "age_factors": {"18-24": 0.85, "25-34": 1.00, "35-44": 1.12, "45-54": 1.28, "55-64": 1.48, "65+": 1.72},
    "smoking_factors":    {"Never": 1.00, "Former": 1.15, "Current": 1.40},
    "exercise_factors":   {"Sedentary": 1.20, "Light": 1.05, "Moderate": 0.90, "Active": 0.80},
    "occupation_factors": {"Office/Desk": 0.85, "Retail/Service": 1.00, "Healthcare": 1.05, "Manual Labor": 1.15, "Industrial/High-Risk": 1.30, "Retired": 1.10},
    "region_factors":     {"Phnom Penh": 1.20, "Siem Reap": 1.05, "Battambang": 0.90, "Sihanoukville": 1.10, "Kampong Cham": 0.85, "Ho Chi Minh City": 1.25, "Hanoi": 1.20, "Da Nang": 1.05, "Can Tho": 0.90, "Hai Phong": 0.95, "Rural Areas": 0.75},
    "preexist_per_condition": 0.20,
    "sev_age_gradient": 0.006,
    "family_per_dep": 0.65,
}

CLAIM_TYPE_MAP = {"IPD": "ipd", "OPD": "opd", "Dental": "dental", "Maternity": "maternity"}
AGE_BANDS = [("18-24", 18, 25), ("25-34", 25, 35), ("35-44", 35, 45),
             ("45-54", 45, 55), ("55-64", 55, 65), ("65+", 65, 101)]

def _age_band(age):
    for label, lo, hi in AGE_BANDS:
        if lo <= age < hi:
            return label
    return "65+"


def load_and_validate(csv_path: str) -> pd.DataFrame:
    print(f"\n── Loading claims: {csv_path}")
    df = pd.read_csv(csv_path)
    required = {"claim_id", "customer_age", "claim_type", "claim_amount", "claim_date"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"Missing required columns: {sorted(missing)}\nRequired: {sorted(required)}")

    df["customer_age"]  = pd.to_numeric(df["customer_age"], errors="coerce")
    df["claim_amount"]  = pd.to_numeric(df["claim_amount"], errors="coerce")
    df["preexist_count"] = pd.to_numeric(df.get("preexist_count", 0), errors="coerce").fillna(0).astype(int)

    # Normalise claim_type
    df["claim_type_norm"] = df["claim_type"].str.strip()
    valid_types = set(CLAIM_TYPE_MAP.keys())
    bad = df[~df["claim_type_norm"].isin(valid_types)]
    if len(bad):
        print(f"  ⚠  {len(bad)} rows with unrecognised claim_type dropped: {bad['claim_type_norm'].unique().tolist()}")
    df = df[df["claim_type_norm"].isin(valid_types)].copy()
    df = df.dropna(subset=["customer_age", "claim_amount"])
    df = df[(df["customer_age"] >= 18) & (df["customer_age"] <= 70)]
    df = df[df["claim_amount"] > 0]
    df["cov"] = df["claim_type_norm"].map(CLAIM_TYPE_MAP)
    df["age_band"] = df["customer_age"].astype(int).apply(_age_band)

    print(f"  Valid rows: {len(df):,}")
    print(f"  Coverage mix: {df['cov'].value_counts().to_dict()}")
    print(f"  Age range: {int(df['customer_age'].min())}–{int(df['customer_age'].max())}")
    print(f"  Amount range: ${df['claim_amount'].min():,.0f}–${df['claim_amount'].max():,.0f}")
    return df


def calibrate_frequency(df: pd.DataFrame, train_idx) -> dict:
    """Compute O/E frequency ratios per coverage type from training set."""
    train = df.iloc[train_idx]
    total = len(train)
    adjustments = {}
    for cov, baseline_rate in BASELINE_COEFF["base_freq"].items():
        obs_count = (train["cov"] == cov).sum()
        obs_rate  = obs_count / total if total > 0 else baseline_rate
        ratio     = obs_rate / baseline_rate if baseline_rate > 0 else 1.0
        ratio     = float(np.clip(ratio, 0.3, 3.0))   # guard against extreme sparse data
        adjustments[cov] = {
            "baseline_rate": baseline_rate,
            "observed_rate": round(obs_rate, 6),
            "observed_count": int(obs_count),
            "ratio": round(ratio, 4),
            "new_base_freq": round(baseline_rate * ratio, 6),
        }
    return adjustments


def calibrate_severity(df: pd.DataFrame, train_idx, cov: str = "ipd") -> dict:
    """
    Fit Gamma GLM on IPD severity. Extract:
    - calibrated base_sev (intercept at reference profile)
    - calibrated age_factors (from model predictions per age band)
    - calibrated sev_age_gradient
    """
    train = df.iloc[train_idx]
    ipd   = train[train["cov"] == cov].copy()

    if len(ipd) < 30:
        print(f"  ⚠  Only {len(ipd)} {cov.upper()} claims in training set — skipping severity calibration, using baseline")
        return {
            "skipped": True,
            "reason": f"Insufficient data ({len(ipd)} records, need ≥30)",
            "base_sev": BASELINE_COEFF["base_sev"][cov],
            "age_factors": BASELINE_COEFF["age_factors"],
            "sev_age_gradient": BASELINE_COEFF["sev_age_gradient"],
        }

    # Feature: just age (continuous) for simplicity + interpretability
    X = ipd["customer_age"].values.reshape(-1, 1)
    y = ipd["claim_amount"].values

    model = GammaRegressor(alpha=0.01, max_iter=500)
    model.fit(X, y)

    # Predict at reference age 30 → base_sev
    ref_pred = float(model.predict([[30]])[0])

    # Predict at each age band midpoint → age_factors (normalised to 25-34 band)
    band_mids = {"18-24": 21, "25-34": 29, "35-44": 39, "45-54": 49, "55-64": 59, "65+": 69}
    preds     = {band: float(model.predict([[mid]])[0]) for band, mid in band_mids.items()}
    norm      = preds["25-34"]
    age_factors = {band: round(pred / norm, 4) for band, pred in preds.items()}

    # Linear slope of age coefficient (log-link, so coef[0] is slope on age in log space)
    sev_age_gradient = round(float(model.coef_[0]), 6)   # per year, in log scale ≈ multiplicative

    # Overall O/E severity ratio for base_sev calibration
    observed_mean_sev = float(ipd["claim_amount"].mean())
    baseline_mean_sev = BASELINE_COEFF["base_sev"][cov]
    sev_ratio         = observed_mean_sev / baseline_mean_sev if baseline_mean_sev > 0 else 1.0
    sev_ratio         = float(np.clip(sev_ratio, 0.2, 5.0))
    calibrated_base_sev = round(baseline_mean_sev * sev_ratio, 2)

    print(f"  Severity GLM ({cov.upper()}): base ${calibrated_base_sev:,.0f}  (baseline ${baseline_mean_sev:,})  O/E={sev_ratio:.3f}")
    print(f"  Age factors: {age_factors}")

    return {
        "skipped": False,
        "n_claims": len(ipd),
        "observed_mean_sev": round(observed_mean_sev, 2),
        "baseline_mean_sev": baseline_mean_sev,
        "sev_ratio": round(sev_ratio, 4),
        "base_sev": calibrated_base_sev,
        "age_factors": age_factors,
        "sev_age_gradient": round(max(sev_age_gradient, 0.001), 6),
    }


def evaluate_holdout(df: pd.DataFrame, test_idx, custom_coeff: dict) -> dict:
    """Compute MAPE on holdout: predicted severity vs actual claim_amount for IPD claims."""
    test = df.iloc[test_idx]
    ipd  = test[test["cov"] == "ipd"].copy()

    if len(ipd) == 0:
        return {"mape": None, "n": 0, "note": "No IPD claims in holdout"}

    def _predict_sev(row):
        age  = int(row["customer_age"])
        band = _age_band(age)
        af   = custom_coeff["age_factors"].get(band, 1.0)
        rf   = custom_coeff["region_factors"].get(row.get("region", "Phnom Penh"), 1.0) if "region" in row else 1.0
        sev  = custom_coeff["base_sev"]["ipd"] * af * rf * (1 + max(0, age - 30) * custom_coeff["sev_age_gradient"])
        return sev

    ipd["predicted_sev"] = ipd.apply(_predict_sev, axis=1)
    ipd = ipd[ipd["claim_amount"] > 0]
    mape = float(np.mean(np.abs(ipd["predicted_sev"] - ipd["claim_amount"]) / ipd["claim_amount"]) * 100)

    # Also compute mean absolute error for context
    mae = float(np.mean(np.abs(ipd["predicted_sev"] - ipd["claim_amount"])))

    print(f"\n  Holdout evaluation ({len(ipd)} IPD claims):")
    print(f"    MAPE: {mape:.1f}%")
    print(f"    MAE:  ${mae:,.0f}")
    print(f"    Target: ≤ 30% MAPE (insurance industry standard for small datasets)")

    return {
        "n": len(ipd),
        "mape_pct": round(mape, 2),
        "mae_usd": round(mae, 2),
        "mean_actual": round(float(ipd["claim_amount"].mean()), 2),
        "mean_predicted": round(float(ipd["predicted_sev"].mean()), 2),
        "pass": mape <= 30.0,
    }


def build_custom_coeff(prospect_id: str, freq_adj: dict, sev_adj: dict) -> dict:
    import copy
    coeff = copy.deepcopy(BASELINE_COEFF)

    # Apply frequency adjustments
    for cov, adj in freq_adj.items():
        coeff["base_freq"][cov] = adj["new_base_freq"]

    # Apply severity adjustments (IPD only if calibrated)
    if not sev_adj.get("skipped"):
        coeff["base_sev"]["ipd"]    = sev_adj["base_sev"]
        coeff["age_factors"]        = sev_adj["age_factors"]
        coeff["sev_age_gradient"]   = sev_adj["sev_age_gradient"]

    coeff["version"]      = f"custom-{prospect_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    coeff["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    coeff["updated_by"]   = "calibration-pilot"
    coeff["prospect_id"]  = prospect_id
    return coeff


def save_outputs(prospect_id: str, custom_coeff: dict, freq_adj: dict, sev_adj: dict,
                 holdout_eval: dict, df: pd.DataFrame):
    out_dir = MODEL_DIR / "custom" / prospect_id
    out_dir.mkdir(parents=True, exist_ok=True)

    coeff_path  = out_dir / "coeff.json"
    report_path = out_dir / "report.json"

    with open(coeff_path, "w") as f:
        json.dump(custom_coeff, f, indent=2)

    report = {
        "prospect_id":       prospect_id,
        "trained_at":        datetime.now(timezone.utc).isoformat(),
        "status":            "pass" if holdout_eval.get("pass") else "warn",
        "dataset": {
            "total_claims":  len(df),
            "coverage_mix":  df["cov"].value_counts().to_dict(),
            "age_range":     [int(df["customer_age"].min()), int(df["customer_age"].max())],
            "date_range":    [str(df["claim_date"].min()), str(df["claim_date"].max())] if "claim_date" in df.columns else [],
        },
        "frequency_calibration": {
            cov: {
                "baseline_rate":   v["baseline_rate"],
                "observed_rate":   v["observed_rate"],
                "ratio":           v["ratio"],
                "new_base_freq":   v["new_base_freq"],
            } for cov, v in freq_adj.items()
        },
        "severity_calibration": sev_adj,
        "holdout_evaluation":   holdout_eval,
        "coeff_path":           str(coeff_path),
        "notes": (
            "Model passes accuracy target (MAPE ≤ 30%)."
            if holdout_eval.get("pass")
            else f"MAPE {holdout_eval.get('mape_pct', '?')}% exceeds target (30%). Consider providing more claims data."
        ),
    }

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n── Saved to {out_dir}/")
    print(f"   coeff.json  — custom pricing coefficients")
    print(f"   report.json — training report")
    return report


def main():
    parser = argparse.ArgumentParser(description="Train prospect-specific calibration model")
    parser.add_argument("--prospect-id", required=True, help="Unique ID for this prospect (e.g. acme-insurance)")
    parser.add_argument("--claims",      required=True, help="Path to claims CSV")
    parser.add_argument("--holdout",     type=float, default=0.20, help="Holdout fraction for evaluation (default 0.20)")
    args = parser.parse_args()

    if not 0.05 <= args.holdout <= 0.40:
        sys.exit("--holdout must be between 0.05 and 0.40")

    print("=" * 60)
    print("DAC HealthPrice — Calibration Pilot: Custom Model Training")
    print(f"Prospect: {args.prospect_id}")
    print("=" * 60)

    df = load_and_validate(args.claims)

    if len(df) < 50:
        sys.exit(f"Too few valid claims ({len(df)}). Need at least 50 records for calibration.")

    # Train/holdout split (random; use date-based if enough rows and claim_date available)
    train_idx, test_idx = train_test_split(
        range(len(df)), test_size=args.holdout, random_state=42
    )
    print(f"\n── Train/holdout split: {len(train_idx)} train / {len(test_idx)} holdout")

    print("\n── Frequency calibration ──")
    freq_adj = calibrate_frequency(df, train_idx)
    for cov, adj in freq_adj.items():
        print(f"  {cov.upper():<10}  baseline={adj['baseline_rate']:.4f}  observed={adj['observed_rate']:.4f}  ratio={adj['ratio']:.3f}  → new={adj['new_base_freq']:.4f}")

    print("\n── Severity calibration (IPD) ──")
    sev_adj = calibrate_severity(df, train_idx, cov="ipd")

    custom_coeff = build_custom_coeff(args.prospect_id, freq_adj, sev_adj)

    holdout_eval = evaluate_holdout(df, test_idx, custom_coeff)

    report = save_outputs(args.prospect_id, custom_coeff, freq_adj, sev_adj, holdout_eval, df)

    print("\n── Summary ──")
    print(f"  Prospect ID    : {args.prospect_id}")
    print(f"  Claims used    : {len(df):,}")
    print(f"  Holdout MAPE   : {holdout_eval.get('mape_pct', 'N/A')}%")
    status = "✅ PASS" if holdout_eval.get("pass") else "⚠  WARN"
    print(f"  Status         : {status}")
    print(f"\n  Next step: run the backend pilot endpoint to load this model into the API")
    print(f"  POST /api/v2/pilot/load  {{\"prospect_id\": \"{args.prospect_id}\"}}")


if __name__ == "__main__":
    main()
