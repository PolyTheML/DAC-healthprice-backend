"""
Train GLM + XGBoost models for the Vietnam case study.

Reads:  case_study/vietnam_dataset.csv
Writes: models/vietnam/health_xgb.pkl
        models/vietnam/life_xgb.pkl
        models/vietnam/glm_coefficients.json
        models/vietnam/model_results.json

Usage: python case_study/train_vietnam_models.py
"""
from __future__ import annotations

import csv
import json
import math
import pickle
from pathlib import Path
from typing import NamedTuple

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

DATASET = Path("case_study/vietnam_dataset.csv")
MODEL_DIR = Path("models/vietnam")
SEED = 42

REGIONS = sorted([
    "Central Highlands", "Mekong Delta", "North Central", "Northeast",
    "Northwest", "Red River Delta", "South Central Coast", "Southeast",
])
OCCUPATIONS = sorted([
    "Construction Worker", "Factory Worker", "Farmer", "Merchant/Trader",
    "Office Worker", "Retired", "Service Industry",
])
CONDITIONS = ["Hypertension", "Diabetes", "Heart Disease", "COPD/Asthma", "Arthritis"]

REGION_ENC = {r: i for i, r in enumerate(REGIONS)}
OCC_ENC = {o: i for i, o in enumerate(OCCUPATIONS)}

FEATURE_NAMES = [
    "age", "bmi", "is_smoking", "is_exercise", "has_family_history",
    "monthly_income_millions_vnd", "condition_count",
    "has_hypertension", "has_diabetes", "has_heart_disease",
    "has_copd_asthma", "has_arthritis",
    "region_enc", "occupation_enc",
]

FEATURE_LABELS = {
    "age": "Age", "bmi": "BMI", "is_smoking": "Smoker",
    "is_exercise": "Exercises Regularly", "has_family_history": "Family History",
    "monthly_income_millions_vnd": "Monthly Income (MVND)",
    "condition_count": "# Pre-existing Conditions",
    "has_hypertension": "Hypertension", "has_diabetes": "Diabetes",
    "has_heart_disease": "Heart Disease", "has_copd_asthma": "COPD/Asthma",
    "has_arthritis": "Arthritis", "region_enc": "Region", "occupation_enc": "Occupation",
}


def _load_dataset(dataset_path: Path = DATASET) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns X (features), y_health, y_mort as numpy arrays."""
    rows = []
    with open(dataset_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            conds = {c.strip() for c in row["pre_existing_conditions"].split(";")
                     if c.strip().lower() != "none"}
            vec = {
                "age": float(row["age"]),
                "bmi": float(row["bmi"]),
                "is_smoking": int(row["is_smoking"]),
                "is_exercise": int(row["is_exercise"]),
                "has_family_history": int(row["has_family_history"]),
                "monthly_income_millions_vnd": float(row["monthly_income_millions_vnd"]),
                "condition_count": len(conds),
                "has_hypertension": int("Hypertension" in conds),
                "has_diabetes": int("Diabetes" in conds),
                "has_heart_disease": int("Heart Disease" in conds),
                "has_copd_asthma": int("COPD/Asthma" in conds),
                "has_arthritis": int("Arthritis" in conds),
                "region_enc": REGION_ENC.get(row["region"], 7),
                "occupation_enc": OCC_ENC.get(row["occupation"], 4),
                "_health": float(row["health_score"]),
                "_mort": float(row["mortality_multiplier"]),
            }
            rows.append(vec)

    X = np.array([[r[f] for f in FEATURE_NAMES] for r in rows], dtype=float)
    y_health = np.array([r["_health"] for r in rows])
    y_mort = np.array([r["_mort"] for r in rows])
    return X, y_health, y_mort


def _train_glm(X_train, y_health_train, y_mort_train) -> dict:
    """
    Train two GLMs using sklearn on the 7 core features the GLM uses.
    Returns coefficient dict matching glm_coefficients.json schema.
    """
    GLM_FEATURES = [
        "age", "bmi", "is_smoking", "is_exercise",
        "has_family_history", "condition_count", "monthly_income_millions_vnd",
    ]
    glm_idx = [FEATURE_NAMES.index(f) for f in GLM_FEATURES]
    Xg = X_train[:, glm_idx]

    # OLS health score
    ols = LinearRegression().fit(Xg, y_health_train)

    # Gamma GLM via log-link: fit OLS on log(y) then exponentiate predictions
    log_mort = np.log(np.clip(y_mort_train, 1e-6, None))
    gamma = LinearRegression().fit(Xg, log_mort)

    return {
        "health_ols": {
            "intercept": float(ols.intercept_),
            "params": {f: float(c) for f, c in zip(GLM_FEATURES, ols.coef_)},
            "method": "OLS (Gaussian, identity link)",
        },
        "mortality_gamma": {
            "intercept": float(gamma.intercept_),
            "params": {f: float(c) for f, c in zip(GLM_FEATURES, gamma.coef_)},
            "method": "GLM (Gamma, log link) — predict = exp(X @ params)",
        },
        "feature_order": GLM_FEATURES,
    }


def _metrics(y_true, y_pred, label: str) -> dict:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    return {
        "model": label,
        "rmse": round(rmse, 4),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
    }


def train(dataset_path: Path = DATASET) -> dict:
    """Train all models. Returns metrics dict. dataset_path allows override in tests."""
    print(f"Loading dataset: {dataset_path}")
    X, y_health, y_mort = _load_dataset(dataset_path)
    n = len(X)
    print(f"  {n} records loaded")

    X_train, X_test, yh_train, yh_test, ym_train, ym_test = train_test_split(
        X, y_health, y_mort, test_size=0.20, random_state=SEED
    )

    # GLM
    print("Training GLM...")
    glm_coeffs = _train_glm(X_train, yh_train, ym_train)

    GLM_FEATURES = glm_coeffs["feature_order"]
    glm_idx = [FEATURE_NAMES.index(f) for f in GLM_FEATURES]
    Xg_test = X_test[:, glm_idx]

    ols_params = np.array([glm_coeffs["health_ols"]["params"][f] for f in GLM_FEATURES])
    glm_health_pred = glm_coeffs["health_ols"]["intercept"] + Xg_test @ ols_params
    glm_health_pred = np.clip(glm_health_pred, 48.0, 95.0)

    gam_params = np.array([glm_coeffs["mortality_gamma"]["params"][f] for f in GLM_FEATURES])
    glm_mort_pred = np.exp(glm_coeffs["mortality_gamma"]["intercept"] + Xg_test @ gam_params)
    glm_mort_pred = np.clip(glm_mort_pred, 0.5, 3.5)

    glm_health_metrics = _metrics(yh_test, glm_health_pred, "GLM (OLS)")
    glm_mort_metrics = _metrics(ym_test, glm_mort_pred, "GLM (Gamma/log)")

    # XGBoost
    print("Training XGBoost health model...")
    health_xgb = XGBRegressor(
        n_estimators=300, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        objective="reg:squarederror", random_state=SEED, verbosity=0,
    )
    health_xgb.fit(X_train, yh_train)
    xgb_health_pred = health_xgb.predict(X_test)
    xgb_health_metrics = _metrics(yh_test, xgb_health_pred, "XGBoost")

    print("Training XGBoost life/mortality model...")
    life_xgb = XGBRegressor(
        n_estimators=300, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        objective="reg:tweedie", tweedie_variance_power=1.5,
        random_state=SEED, verbosity=0,
    )
    life_xgb.fit(X_train, ym_train)
    xgb_mort_pred = life_xgb.predict(X_test)
    xgb_mort_metrics = _metrics(ym_test, xgb_mort_pred, "XGBoost")

    def _top_features(model, n=5):
        imp = model.feature_importances_
        total = imp.sum()
        idx = np.argsort(imp)[::-1][:n]
        return [{"feature": FEATURE_NAMES[i], "label": FEATURE_LABELS[FEATURE_NAMES[i]],
                 "importance": round(float(imp[i] / total), 4)} for i in idx]

    model_results = {
        "health_model": {
            "target": "health_score",
            "description": "Predicts health risk score (48-95). Lower = higher claim risk.",
            "glm": glm_health_metrics,
            "xgboost": xgb_health_metrics,
            "top_features": _top_features(health_xgb),
            "train_size": len(X_train),
            "test_size": len(X_test),
        },
        "mortality_model": {
            "target": "mortality_multiplier",
            "description": "Predicts mortality risk multiplier. 1.0 = standard rate.",
            "glm": glm_mort_metrics,
            "xgboost": xgb_mort_metrics,
            "top_features": _top_features(life_xgb),
            "train_size": len(X_train),
            "test_size": len(X_test),
        },
        "feature_names": FEATURE_NAMES,
        "feature_labels": FEATURE_LABELS,
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    with open(MODEL_DIR / "health_xgb.pkl", "wb") as f:
        pickle.dump(health_xgb, f)
    with open(MODEL_DIR / "life_xgb.pkl", "wb") as f:
        pickle.dump(life_xgb, f)
    with open(MODEL_DIR / "glm_coefficients.json", "w", encoding="utf-8") as f:
        json.dump(glm_coeffs, f, indent=2)
    with open(MODEL_DIR / "model_results.json", "w", encoding="utf-8") as f:
        json.dump(model_results, f, indent=2)

    print(f"\nResults:")
    print(f"  Health GLM  R2={glm_health_metrics['r2']:.4f}  RMSE={glm_health_metrics['rmse']:.2f}")
    print(f"  Health XGB  R2={xgb_health_metrics['r2']:.4f}  RMSE={xgb_health_metrics['rmse']:.2f}")
    print(f"  Mortality GLM  R2={glm_mort_metrics['r2']:.4f}  RMSE={glm_mort_metrics['rmse']:.4f}")
    print(f"  Mortality XGB  R2={xgb_mort_metrics['r2']:.4f}  RMSE={xgb_mort_metrics['rmse']:.4f}")
    print(f"\nSaved to {MODEL_DIR}/")
    return model_results


if __name__ == "__main__":
    train()
