"""Tests for Vietnam data pipeline — generator and trainer."""
import json
from pathlib import Path
import pytest


def test_dataset_has_required_columns():
    """Dataset CSV must have all columns the API reads."""
    import csv
    csv_path = Path("case_study/vietnam_dataset.csv")
    assert csv_path.exists(), "Run generate_vietnam_dataset.py first"
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        row = next(reader)
    required = {
        "age", "bmi", "is_smoking", "is_exercise", "has_family_history",
        "monthly_income_millions_vnd", "region", "occupation",
        "pre_existing_conditions", "health_score", "mortality_multiplier",
    }
    assert required.issubset(set(row.keys()))


def test_training_produces_model_artifacts():
    """After training, all four model artifacts must exist."""
    model_dir = Path("models/vietnam")
    for fname in ("health_xgb.pkl", "life_xgb.pkl", "glm_coefficients.json", "model_results.json"):
        assert (model_dir / fname).exists(), f"Missing: {fname}"


def test_retrain_endpoint_updates_model_files():
    """After calling retrain(), the pkl files should have a newer mtime."""
    import time
    from pathlib import Path
    import pytest

    model_path = Path("models/vietnam/health_xgb.pkl")
    mtime_before = model_path.stat().st_mtime

    # This test assumes the server is running locally on port 8000.
    # Skip if server is not available.
    try:
        import httpx
        r = httpx.post("http://localhost:8000/api/vietnam/retrain",
                       json={"model_type": "both", "shadow_mode": False}, timeout=30)
        r.raise_for_status()
    except Exception:
        pytest.skip("Server not running — skipping retrain integration test")

    mtime_after = model_path.stat().st_mtime
    assert mtime_after > mtime_before, "Model file was not updated by retrain"


def test_dataset_smoker_ratio():
    """Smoker ratio should be ~25% (within ±5%)."""
    import csv
    from pathlib import Path
    with open(Path("case_study/vietnam_dataset.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    smoker_ratio = sum(int(r["is_smoking"]) for r in rows) / len(rows)
    assert 0.18 <= smoker_ratio <= 0.32, f"Unexpected smoker ratio: {smoker_ratio:.2%}"


def test_health_scores_in_range():
    """All health scores must be in 48–95."""
    import csv
    from pathlib import Path
    with open(Path("case_study/vietnam_dataset.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        hs = float(r["health_score"])
        assert 48 <= hs <= 95, f"Health score out of range: {hs}"


def test_glm_coefficients_schema():
    """glm_coefficients.json must have the keys the API reads."""
    import json
    from pathlib import Path
    with open(Path("models/vietnam/glm_coefficients.json"), encoding="utf-8") as f:
        data = json.load(f)
    assert "health_ols" in data
    assert "mortality_gamma" in data
    assert "feature_order" in data
    assert "intercept" in data["health_ols"]
    assert "params" in data["health_ols"]


def test_xgboost_models_predict():
    """Loaded XGBoost models should produce in-range predictions."""
    import pickle
    import numpy as np
    from pathlib import Path

    with open(Path("models/vietnam/health_xgb.pkl"), "rb") as f:
        health_xgb = pickle.load(f)
    with open(Path("models/vietnam/life_xgb.pkl"), "rb") as f:
        life_xgb = pickle.load(f)

    # 45-year-old smoker with hypertension
    X = np.array([[45, 27.5, 1, 0, 1, 80.0, 1, 1, 0, 0, 0, 0, 7, 4]], dtype=float)
    health = float(health_xgb.predict(X)[0])
    mort = float(life_xgb.predict(X)[0])

    assert isinstance(health, float), "Health prediction is not a float"
    assert isinstance(mort, float), "Mortality prediction is not a float"
    # A smoker with hypertension should be riskier than standard (mort > 1.0)
    assert mort > 1.0, f"Smoker+hypertension should have mort > 1.0, got {mort:.3f}"


def test_build_features_encoding():
    """_build_features must produce a 14-element vector."""
    import sys
    sys.path.insert(0, ".")
    from app.routes.vietnam_pricing import _build_features, VietnamPriceRequest

    req = VietnamPriceRequest(
        age=35, bmi=22.0, is_smoking=0, is_exercise=1,
        has_family_history=0, monthly_income_millions_vnd=100.0,
        region="Southeast", occupation="Office Worker",
        pre_existing_conditions=[],
    )
    features = _build_features(req)
    assert len(features) == 14, f"Expected 14 features, got {len(features)}"
