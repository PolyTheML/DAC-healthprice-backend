"""
Generate 2,000 synthetic Vietnamese insurance applicants.

Produces: case-study/vietnam_dataset.csv

Each row = one applicant with input features + actuarial targets:
  health_score (48–95): lower = sicker = higher claim cost
  mortality_multiplier (0.5–3.5): 1.0 = standard rate

Usage: python case-study/generate_vietnam_dataset.py
"""
import csv
import math
import random
from pathlib import Path

SEED = 42
N = 2000
OUT = Path(__file__).parent / "vietnam_dataset.csv"

REGIONS = [
    "Central Highlands", "Mekong Delta", "North Central", "Northeast",
    "Northwest", "Red River Delta", "South Central Coast", "Southeast",
]
OCCUPATIONS = [
    "Construction Worker", "Factory Worker", "Farmer", "Merchant/Trader",
    "Office Worker", "Retired", "Service Industry",
]
CONDITIONS = ["Hypertension", "Diabetes", "Heart Disease", "COPD/Asthma", "Arthritis"]

# Regional health index: higher = healthier population (less risk)
REGION_HEALTH = {
    "Southeast": 1.05, "Red River Delta": 1.02, "South Central Coast": 1.00,
    "Northeast": 0.98, "Mekong Delta": 0.97, "North Central": 0.95,
    "Central Highlands": 0.93, "Northwest": 0.90,
}
# Occupation risk: higher = more dangerous job
OCC_RISK = {
    "Office Worker": 0.85, "Retired": 0.90, "Service Industry": 1.00,
    "Merchant/Trader": 1.00, "Farmer": 1.10, "Factory Worker": 1.20,
    "Construction Worker": 1.35,
}


def generate(n: int = N, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    rows = []

    for _ in range(n):
        age = rng.randint(18, 75)
        bmi = round(rng.gauss(22.5, 3.5), 1)
        bmi = max(14.0, min(45.0, bmi))
        is_smoking = int(rng.random() < 0.25)
        is_exercise = int(rng.random() < 0.55)
        has_family_history = int(rng.random() < 0.30)
        income = round(rng.gauss(100, 60), 1)
        income = max(10.0, min(500.0, income))
        region = rng.choice(REGIONS)
        occupation = rng.choice(OCCUPATIONS)

        # Sample 0–3 pre-existing conditions, weighted by age
        max_conds = min(3, max(0, int((age - 30) / 15)))
        cond_count = rng.randint(0, max_conds)
        pre_conds = rng.sample(CONDITIONS, k=min(cond_count, len(CONDITIONS)))

        # ── Actuarial targets ───────────────────────────────────────────────
        # Health score: 48–95. Age and BMI are the dominant drivers.
        base_health = 95.0
        base_health -= (age - 18) * 0.45           # age penalty
        base_health -= max(0, bmi - 23) * 1.1      # BMI penalty
        base_health -= is_smoking * 3.5
        base_health += is_exercise * 2.0
        base_health -= has_family_history * 1.2
        base_health -= len(pre_conds) * 2.5
        base_health -= 2.0 if income < 30 else 0.0    # poverty penalty
        base_health *= REGION_HEALTH[region]
        noise = rng.gauss(0, 1.5)
        health_score = round(max(48.0, min(95.0, base_health + noise)), 1)

        # Mortality multiplier: 1.0 = standard.
        log_mort = 0.0
        log_mort += (age - 40) * 0.014
        log_mort += (bmi - 22) * 0.005
        log_mort += is_smoking * 0.18
        log_mort -= is_exercise * 0.09
        log_mort += has_family_history * 0.08
        log_mort += len(pre_conds) * 0.22
        log_mort += math.log(OCC_RISK[occupation])
        log_mort += rng.gauss(0, 0.04)
        mort_mult = round(max(0.5, min(3.5, math.exp(log_mort))), 3)

        rows.append({
            "age": age,
            "bmi": bmi,
            "is_smoking": is_smoking,
            "is_exercise": is_exercise,
            "has_family_history": has_family_history,
            "monthly_income_millions_vnd": income,
            "region": region,
            "occupation": occupation,
            "pre_existing_conditions": "; ".join(pre_conds) if pre_conds else "None",
            "health_score": health_score,
            "mortality_multiplier": mort_mult,
        })

    return rows


def main():
    rows = generate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} records -> {OUT}")
    smokers = sum(r["is_smoking"] for r in rows)
    print(f"  Smoker ratio: {smokers/len(rows):.1%}")
    print(f"  Health score range: {min(r['health_score'] for r in rows)} - {max(r['health_score'] for r in rows)}")
    print(f"  Mortality range: {min(r['mortality_multiplier'] for r in rows)} - {max(r['mortality_multiplier'] for r in rows)}")


if __name__ == "__main__":
    main()
