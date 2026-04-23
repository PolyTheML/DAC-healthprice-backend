"""
Synthetic Portfolio Generator

Generates a realistic portfolio of historical life insurance policies for Cambodia
to bootstrap the pricing calibration workflow when no real claims data is available.

Hypothesis:
- Product: 10-year term life insurance
- Market: Urban Cambodian adults, age 25-55
- Cambodia adjustment factor: 0.85x (observed mortality ~15% below WHO SEA benchmark)

Output: data/synthetic_portfolio.parquet
"""

import uuid
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from medical_reader.pricing.calculator import (
    calculate_mortality_ratio,
    get_base_mortality_rate,
    calculate_annual_premium,
)
from medical_reader.pricing.assumptions import (
    ASSUMPTIONS,
    LoadingFactors,
)

# ---- Constants ----
CAMBODIA_MORTALITY_ADJ = 0.85   # Cambodia observed mortality ~15% below WHO SEA
ONLINE_COMMISSION = 0.05        # Digital distribution vs. 10% agent commission
N_POLICIES = 2000
RANDOM_SEED = 333

# Cambodia demographics (Cambodian census 2019 + WHO SEA data)
GENDER_MALE_PROB = 0.52
SMOKER_PROB = {"M": 0.30, "F": 0.08}   # WHO SEA smoking prevalence
CAMBODIA_BMI_MEAN = 23.5
CAMBODIA_BMI_STD = 3.5


def _age_band(age: int) -> str:
    if age < 25:
        return "18-24"
    elif age < 35:
        return "25-34"
    elif age < 45:
        return "35-44"
    elif age < 55:
        return "45-54"
    elif age < 65:
        return "55-64"
    else:
        return "65+"


def _age_prob(age: int, base: float, peak: float,
              base_age: int = 25, peak_age: int = 55) -> float:
    """Linear age-dependent probability from base_age to peak_age."""
    slope = (peak - base) / (peak_age - base_age)
    return float(np.clip(base + slope * (age - base_age), base, peak))


def generate_portfolio(
    n: int = N_POLICIES,
    seed: int = RANDOM_SEED,
    cambodia_adj: float = CAMBODIA_MORTALITY_ADJ,
) -> pd.DataFrame:
    """
    Generate 2,000 synthetic historical policies with claim outcomes.

    Returns a DataFrame with demographics, risk factors, claim outcomes, and premiums.
    """
    rng = np.random.default_rng(seed)
    rf_obj = ASSUMPTIONS["risk_factors"]
    mort_obj = ASSUMPTIONS["mortality"]
    tier_obj = ASSUMPTIONS["tiers"]

    # Online loading (lower commission for digital distribution)
    online_loading = LoadingFactors(
        expense_ratio=0.12,
        commission_ratio=ONLINE_COMMISSION,
        profit_margin=0.05,
        contingency=0.05,
    )
    online_assumptions = dict(ASSUMPTIONS)
    online_assumptions["loading"] = online_loading

    records = []

    for _ in range(n):
        # ---- Demographics ----
        gender = "M" if rng.random() < GENDER_MALE_PROB else "F"
        age = int(np.clip(rng.normal(38, 8), 25, 55))
        bmi = float(np.clip(rng.normal(CAMBODIA_BMI_MEAN, CAMBODIA_BMI_STD), 16.0, 45.0))

        # ---- Risk Factors (age-correlated) ----
        smoker = bool(rng.random() < SMOKER_PROB[gender])
        diabetes = bool(rng.random() < _age_prob(age, 0.04, 0.14))
        hypertension = bool(rng.random() < _age_prob(age, 0.08, 0.32))
        hyperlipidemia = bool(rng.random() < _age_prob(age, 0.06, 0.22))
        family_history_chd = bool(rng.random() < 0.12)
        alcohol_heavy = bool(rng.random() < 0.05)

        # ---- Blood Pressure (correlated with hypertension flag) ----
        if hypertension:
            systolic = int(np.clip(rng.normal(145, 12), 130, 190))
            diastolic = int(np.clip(rng.normal(90, 8), 82, 120))
        else:
            systolic = int(np.clip(rng.normal(115, 10), 95, 130))
            diastolic = int(np.clip(rng.normal(75, 8), 60, 84))

        alcohol_use = "heavy" if alcohol_heavy else "none"

        # ---- Face Amount (log-normal, mode ~$25K, clipped $10K-$100K) ----
        face_amount = float(np.clip(np.exp(rng.normal(np.log(25000), 0.7)), 10000, 100000))
        face_amount = round(face_amount / 1000) * 1000

        # ---- Mortality Ratio (via existing engine) ----
        mortality_ratio, _ = calculate_mortality_ratio(
            age=age, gender=gender, bmi=bmi, smoker=smoker,
            alcohol_use=alcohol_use, diabetes=diabetes,
            hypertension=hypertension, hyperlipidemia=hyperlipidemia,
            family_history_chd=family_history_chd,
            systolic=systolic, diastolic=diastolic,
            assumptions=rf_obj,
        )

        # ---- Risk Tier ----
        if mortality_ratio <= tier_obj.low_max:
            risk_tier = "LOW"
        elif mortality_ratio <= tier_obj.medium_max:
            risk_tier = "MEDIUM"
        elif mortality_ratio <= tier_obj.high_max:
            risk_tier = "HIGH"
        else:
            risk_tier = "DECLINE"

        # ---- Policy Timeline ----
        issue_year = int(rng.integers(2015, 2024))   # 2015-2023 inclusive
        exposure_years = min(2025 - issue_year, 10)

        # ---- Claim Event ----
        base_q_x = get_base_mortality_rate(age, gender, mort_obj)  # per 1,000/yr
        annual_p = (base_q_x / 1000.0) * mortality_ratio * cambodia_adj
        claim_prob = 1.0 - (1.0 - annual_p) ** exposure_years
        claim_event = bool(rng.random() < claim_prob)
        benefit_paid = face_amount if claim_event else 0.0
        claim_year = int(issue_year + rng.integers(1, exposure_years + 1)) if claim_event else None

        # ---- Premium ----
        pb = calculate_annual_premium(
            face_amount=face_amount, policy_term_years=10,
            age=age, gender=gender, bmi=bmi, smoker=smoker,
            alcohol_use=alcohol_use, diabetes=diabetes,
            hypertension=hypertension, hyperlipidemia=hyperlipidemia,
            family_history_chd=family_history_chd,
            systolic=systolic, diastolic=diastolic,
            assumptions=online_assumptions,
        )

        years_paying = (claim_year - issue_year) if (claim_event and claim_year) else exposure_years
        total_premium = pb.gross_annual_premium * years_paying

        records.append({
            "policy_id": str(uuid.uuid4())[:8],
            "issue_year": issue_year,
            "issue_age": age,
            "gender": gender,
            "bmi": round(bmi, 1),
            "smoker": smoker,
            "diabetes": diabetes,
            "hypertension": hypertension,
            "hyperlipidemia": hyperlipidemia,
            "family_history_chd": family_history_chd,
            "alcohol_heavy": alcohol_heavy,
            "systolic": systolic,
            "diastolic": diastolic,
            "face_amount": face_amount,
            "policy_term_years": 10,
            "exposure_years": exposure_years,
            "mortality_ratio": round(mortality_ratio, 3),
            "risk_tier": risk_tier,
            "age_band": _age_band(age),
            "base_q_x_per_1000": round(base_q_x, 3),
            "claim_event": claim_event,
            "claim_year": claim_year,
            "actual_benefit_paid": benefit_paid,
            "annual_premium": round(pb.gross_annual_premium, 2),
            "total_premium_collected": round(total_premium, 2),
        })

    return pd.DataFrame(records)


def save_portfolio(df: pd.DataFrame, path: str = None) -> str:
    """Save portfolio to parquet. Returns the saved file path."""
    if path is None:
        data_dir = Path(__file__).parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        path = str(data_dir / "synthetic_portfolio.parquet")
    df.to_parquet(path, index=False)
    return path


def load_portfolio(path: str = None) -> pd.DataFrame:
    """Load portfolio from parquet."""
    if path is None:
        path = str(Path(__file__).parent.parent / "data" / "synthetic_portfolio.parquet")
    return pd.read_parquet(path)


if __name__ == "__main__":
    print("Generating synthetic portfolio...")
    df = generate_portfolio()
    out = save_portfolio(df)
    print(f"\n{len(df):,} policies saved → {out}")
    print(f"\nRisk tier distribution:\n{df['risk_tier'].value_counts()}")
    print(f"\nClaim rate:       {df['claim_event'].mean():.2%}")
    print(f"Avg annual prem:  ${df['annual_premium'].mean():.2f}")
    print(f"Total benefits:   ${df['actual_benefit_paid'].sum():,.0f}")
    print(f"Gender split:     {df['gender'].value_counts().to_dict()}")
    print(f"Age range:        {df['issue_age'].min()}-{df['issue_age'].max()}, mean {df['issue_age'].mean():.1f}")
