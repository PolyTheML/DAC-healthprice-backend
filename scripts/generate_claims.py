"""
DAC HealthPrice — Synthetic Claims Data Generator (New Format)

Generates realistic synthetic claims data matching the admin upload template.
Format: claim_id, customer_age, customer_occupation, claim_type, claim_amount, claim_date

Usage:
  python generate_claims.py --n 1000 --output claims_synthetic.csv
  python generate_claims.py --n 500 --start-date 2026-01-01 --output claims_jan.csv
"""
import argparse
import csv
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np

# COEFF factors from main.py — defines the live pricing model
COEFF = {
    "base_freq": {"IPD": 0.12, "OPD": 2.5, "Dental": 0.80, "Maternity": 0.15},
    "base_sev": {"IPD": 2500, "OPD": 60, "Dental": 120, "Maternity": 3500},
    "age_factors": {"18-24": 0.85, "25-34": 1.00, "35-44": 1.12, "45-54": 1.28, "55-64": 1.48, "65+": 1.72},
    "occupation_factors": {
        "Office/Desk": 0.85,
        "Retail/Service": 1.00,
        "Healthcare": 1.05,
        "Manual Labor": 1.15,
        "Industrial/High-Risk": 1.30,
        "Retired": 0.75
    },
}

OCCUPATIONS = list(COEFF["occupation_factors"].keys())
CLAIM_TYPES = ["IPD", "OPD", "Dental", "Maternity"]

# Probability distributions
OCCUPATION_PROBS = [0.35, 0.25, 0.15, 0.15, 0.05, 0.05]  # 6 occupations
CLAIM_TYPE_PROBS = [0.35, 0.40, 0.15, 0.10]  # IPD, OPD, Dental, Maternity


def get_age_factor(age):
    """Return age factor based on COEFF brackets."""
    if age < 25:
        return COEFF["age_factors"]["18-24"]
    elif age < 35:
        return COEFF["age_factors"]["25-34"]
    elif age < 45:
        return COEFF["age_factors"]["35-44"]
    elif age < 55:
        return COEFF["age_factors"]["45-54"]
    elif age < 65:
        return COEFF["age_factors"]["55-64"]
    else:
        return COEFF["age_factors"]["65+"]


def generate_synthetic_claims(n_records, seed=42, start_date=None):
    """
    Generate synthetic claims data.

    Args:
        n_records: Number of claims to generate
        seed: Random seed for reproducibility
        start_date: Start date for claims (YYYY-MM-DD), default today - 90 days

    Returns:
        List of dicts with keys: claim_id, customer_age, customer_occupation,
                                 claim_type, claim_amount, claim_date
    """
    rng = np.random.default_rng(seed)

    if start_date:
        base_date = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        base_date = datetime.now() - timedelta(days=90)

    records = []

    for i in range(n_records):
        # Claim ID
        claim_id = f"CLM{i+1:06d}"

        # Sample customer demographics (from claim records)
        age = int(rng.integers(18, 76))
        occupation = rng.choice(OCCUPATIONS, p=OCCUPATION_PROBS)

        # Sample claim type (age-adjusted — fewer maternity for older customers)
        if age < 20 or age > 45:
            claim_type_probs = [0.40, 0.45, 0.15, 0.00]  # no maternity
        else:
            claim_type_probs = CLAIM_TYPE_PROBS

        claim_type = rng.choice(CLAIM_TYPES, p=claim_type_probs)

        # Compute severity multiplier
        sev_mult = 1.0
        sev_mult *= get_age_factor(age)
        sev_mult *= COEFF["occupation_factors"][occupation]

        # Claim amount ~ Gamma distribution
        base_sev = COEFF["base_sev"][claim_type]
        severity_mean = base_sev * sev_mult

        # Gamma(shape=4, scale=mean/4) gives reasonable claim amounts
        claim_amount = float(rng.gamma(shape=4.0, scale=severity_mean / 4.0))

        # Claim date (spread over the range)
        days_offset = int(rng.integers(0, 90))
        claim_date = (base_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")

        records.append({
            "claim_id": claim_id,
            "customer_age": age,
            "customer_occupation": occupation,
            "claim_type": claim_type,
            "claim_amount": round(claim_amount, 2),
            "claim_date": claim_date
        })

    return records


def write_csv(records, output_path):
    """Write records to CSV in the admin upload format."""
    if not records:
        print("No records to write.")
        return

    with open(output_path, "w", newline="") as f:
        fieldnames = ["claim_id", "customer_age", "customer_occupation", "claim_type", "claim_amount", "claim_date"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def print_summary(records, output_path):
    """Print summary statistics."""
    if not records:
        return

    claim_amounts = [r["claim_amount"] for r in records]
    claim_types = [r["claim_type"] for r in records]

    type_dist = {}
    for ct in CLAIM_TYPES:
        type_dist[ct] = sum(1 for c in claim_types if c == ct)

    total_amount = sum(claim_amounts)

    print(f"\n[OK] Generated {len(records)} claims")
    print(f"  Total amount: ${total_amount:,.2f}")
    print(f"  Avg claim: ${total_amount / len(records):,.2f}")
    print(f"  Distribution:")
    for ct, count in type_dist.items():
        pct = 100 * count / len(records)
        print(f"    {ct:12} {count:4} ({pct:5.1f}%)")
    print(f"  Saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic health insurance claims for testing the admin upload & retraining pipeline."
    )
    parser.add_argument("--n", type=int, default=1000, help="Number of claims to generate (default: 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--start-date", default=None, help="Claim date range start (YYYY-MM-DD). Default: 90 days ago")
    parser.add_argument("--output", default="claims_synthetic.csv", help="Output file (default: claims_synthetic.csv)")

    args = parser.parse_args()

    records = generate_synthetic_claims(args.n, seed=args.seed, start_date=args.start_date)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    write_csv(records, str(output_path))
    print_summary(records, str(output_path))


if __name__ == "__main__":
    main()
