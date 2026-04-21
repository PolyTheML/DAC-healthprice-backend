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
