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
