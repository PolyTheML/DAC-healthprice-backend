"""
Vietnam pipeline runner. Run this to rebuild everything from scratch.

Usage: python case_study/run_pipeline.py [--records N]

Steps:
  1. Generate synthetic dataset
  2. Train GLM + XGBoost models
  3. Smoke-test that models load and produce predictions
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def step1_generate(n: int):
    print("\n-- Step 1: Generate dataset --")
    from case_study.generate_vietnam_dataset import generate, OUT
    rows = generate(n=n)
    import csv
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  OK {len(rows)} records -> {OUT}")
    return OUT


def step2_train(dataset_path):
    print("\n-- Step 2: Train models --")
    from case_study.train_vietnam_models import train
    results = train(dataset_path=dataset_path)
    h = results["health_model"]
    m = results["mortality_model"]
    print(f"  OK Health XGB R2={h['xgboost']['r2']:.4f}")
    print(f"  OK Mortality XGB R2={m['xgboost']['r2']:.4f}")
    return results


def step3_verify():
    print("\n-- Step 3: Smoke test --")
    model_dir = Path("models/vietnam")
    for fname in ("health_xgb.pkl", "life_xgb.pkl", "glm_coefficients.json", "model_results.json"):
        path = model_dir / fname
        assert path.exists(), f"MISSING: {path}"
        print(f"  OK {fname} ({path.stat().st_size // 1024} KB)")

    import numpy as np
    import pickle
    with open(model_dir / "health_xgb.pkl", "rb") as f:
        health_xgb = pickle.load(f)
    with open(model_dir / "life_xgb.pkl", "rb") as f:
        life_xgb = pickle.load(f)

    # Predict for a 35-year-old non-smoking office worker
    X = np.array([[35, 22.0, 0, 1, 0, 100.0, 0, 0, 0, 0, 0, 0, 7, 4]], dtype=float)
    health = float(health_xgb.predict(X)[0])
    mort = float(life_xgb.predict(X)[0])
    assert 48 <= health <= 95, f"Health score out of range: {health}"
    assert 0.5 <= mort <= 3.5, f"Mortality multiplier out of range: {mort}"
    print(f"  OK Sample prediction -- health={health:.1f}, mortality={mort:.3f}")
    print("\n  Pipeline OK")


def main():
    parser = argparse.ArgumentParser(description="Vietnam pipeline runner")
    parser.add_argument("--records", type=int, default=2000, help="Number of synthetic records to generate")
    args = parser.parse_args()

    csv_path = step1_generate(args.records)
    step2_train(csv_path)
    step3_verify()
    print("\nDone. Start the API server and hit POST /api/vietnam/price to test end-to-end.")


if __name__ == "__main__":
    main()
