"""
Auto Pricing Lab v2 — ML Model Training (Step 4)

Trains a LightGBM model to learn residuals:
  target = actual_loss - glm_pure_premium

The ML layer corrects systematic GLM biases for specific segments
(e.g. "sedans in Hanoi are 30% cheaper than GLM predicts").

Usage:
  python -m app.ml.train_model [--claims-csv path/to/claims.csv]

If no claims CSV is provided, generates synthetic training data.
Outputs:
  models/auto_ml_v{n}.pkl   — trained LightGBM model
  models/auto_ml_meta.json  — training metrics (MAPE, R2, RMSE)
"""
from __future__ import annotations
import argparse, json, os, sys, pickle, warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_percentage_error, r2_score, mean_squared_error

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.COEFF_AUTO import (
    BASE_RATES, VEHICLE_AGE_MULTIPLIERS, DRIVER_AGE_MULTIPLIERS,
    REGION_MULTIPLIERS, ACCIDENT_HISTORY_MULTIPLIERS, COVERAGE_MULTIPLIERS,
    LOADING_FACTORS, TIER_MULTIPLIERS, DEDUCTIBLE_CREDITS,
    get_vehicle_age_bracket, get_driver_age_bracket,
)
from app.data.features import VehicleProfile, extract_features, ExtractedFeatures

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False
    warnings.warn("lightgbm not installed — falling back to sklearn GradientBoostingRegressor")
    from sklearn.ensemble import GradientBoostingRegressor

MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))
MODEL_DIR.mkdir(exist_ok=True)

N_SYNTHETIC = 10_000
RANDOM_SEED = 42


# ─── Synthetic data generation ────────────────────────────────────────────────

def _generate_synthetic_claims(n: int = N_SYNTHETIC, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """
    Generate synthetic auto insurance claims for initial model training.
    Actual loss = GLM pure premium × noise factor (log-normal, mean≈1.0).
    Real data will replace this when available.
    """
    rng = np.random.default_rng(seed)
    vehicle_types = ["motorcycle", "sedan", "suv", "truck"]
    regions = list(REGION_MULTIPLIERS.keys())
    coverages = list(COVERAGE_MULTIPLIERS.keys())
    tiers = list(TIER_MULTIPLIERS.keys())

    rows = []
    for _ in range(n):
        vt = rng.choice(vehicle_types, p=[0.55, 0.25, 0.12, 0.08])  # Cambodia/VN mix
        yom = int(rng.integers(2005, 2024))
        region = rng.choice(regions)
        driver_age = int(rng.integers(18, 70))
        accident_history = bool(rng.random() < 0.15)  # 15% have prior claim
        coverage = rng.choice(coverages, p=[0.40, 0.60])
        tier = rng.choice(tiers, p=[0.20, 0.50, 0.20, 0.10])
        family_size = int(rng.integers(1, 5))

        profile = VehicleProfile(
            vehicle_type=vt,
            year_of_manufacture=yom,
            region=region,
            driver_age=driver_age,
            accident_history=accident_history,
            coverage=coverage,
            tier=tier,
            family_size=family_size,
        )
        feats = extract_features(profile)

        # Simulate actual loss: GLM pure + segment-specific bias + noise
        # Inject realistic patterns the ML should learn:
        bias = 1.0
        if vt == "sedan" and region in ("hanoi", "ho_chi_minh"):
            bias = 0.82  # urban sedans over-priced by GLM
        if vt == "motorcycle" and accident_history:
            bias = 1.35  # repeat accident risk under-weighted
        if vt == "truck" and region == "rural_cambodia":
            bias = 0.75  # rural trucks lower than GLM

        noise = float(rng.lognormal(mean=0.0, sigma=0.18))
        actual_loss = feats.glm_pure_premium * bias * noise

        row = {f: getattr(feats, f) for f in ExtractedFeatures.feature_names()}
        row["actual_loss"] = actual_loss
        row["residual"] = actual_loss - feats.glm_pure_premium
        rows.append(row)

    return pd.DataFrame(rows)


# ─── Training ─────────────────────────────────────────────────────────────────

def train(claims_csv: str | None = None) -> dict:
    """Train ML adjustment model. Returns metrics dict."""
    if claims_csv and Path(claims_csv).exists():
        df = pd.read_csv(claims_csv)
        # Expect columns: all ExtractedFeatures.feature_names() + actual_loss
        df["residual"] = df["actual_loss"] - df["glm_pure_premium"]
        print(f"[train] Loaded {len(df)} real claims from {claims_csv}")
    else:
        print(f"[train] No claims CSV — generating {N_SYNTHETIC} synthetic samples")
        df = _generate_synthetic_claims()

    feature_names = ExtractedFeatures.feature_names()
    X = df[feature_names].values
    y = df["residual"].values   # target: actual - GLM prediction

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_SEED
    )

    if LGB_AVAILABLE:
        model = lgb.LGBMRegressor(
            n_estimators=400,
            learning_rate=0.05,
            num_leaves=31,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=0.1,
            random_state=RANDOM_SEED,
            verbose=-1,
        )
    else:
        from sklearn.ensemble import GradientBoostingRegressor
        model = GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05,
            max_depth=4, random_state=RANDOM_SEED
        )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_val)

    # Metrics on residual prediction
    rmse = float(np.sqrt(mean_squared_error(y_val, y_pred)))
    r2 = float(r2_score(y_val, y_pred))

    # Also compute MAPE on final price (GLM + adjustment vs actual)
    glm_val = df.loc[X_val[:, 0] == X_val[:, 0], "glm_pure_premium"].values[-len(y_val):]
    final_pred = glm_val + y_pred
    final_actual = glm_val + y_val
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mape = float(mean_absolute_percentage_error(
            np.abs(final_actual) + 1, np.abs(final_pred) + 1
        ))

    metrics = {
        "rmse_residual": rmse,
        "r2_residual": r2,
        "mape_final_price": mape,
        "n_train": len(X_train),
        "n_val": len(X_val),
        "feature_names": feature_names,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model_type": "lightgbm" if LGB_AVAILABLE else "gradient_boosting",
    }

    # Determine next version number
    existing = list(MODEL_DIR.glob("auto_ml_v*.pkl"))
    version = len(existing) + 1

    model_path = MODEL_DIR / f"auto_ml_v{version}.pkl"
    meta_path = MODEL_DIR / "auto_ml_meta.json"

    with open(model_path, "wb") as f:
        pickle.dump({"model": model, "feature_names": feature_names, "version": version}, f)

    metrics["model_path"] = str(model_path)
    metrics["version"] = version
    with open(meta_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"[train] Saved model → {model_path}")
    print(f"[train] RMSE={rmse:,.0f} VND  R²={r2:.4f}  MAPE={mape:.2%}")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--claims-csv", default=None, help="Path to real claims CSV")
    args = parser.parse_args()
    train(args.claims_csv)
