"""
Claims Analysis Engine

Analyzes the synthetic (or real) claims portfolio to produce:
- Portfolio summary KPIs (loss ratio, claim rate, tier distribution)
- Cohort mortality rates by age band / gender vs. WHO SEA assumed
- Risk factor lifts (observed vs. clean-lives mortality rate ratio)
- A/E (Actual/Expected) experience table

The A/E ratio validates the Cambodia hypothesis:
  A/E ≈ 0.85 → Cambodia mortality ~15% below WHO SEA → pricing needs calibration downward.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from medical_reader.pricing.assumptions import ASSUMPTIONS
from medical_reader.pricing.calculator import get_base_mortality_rate


@dataclass
class PortfolioSummary:
    total_policies: int
    total_exposure_years: float
    total_claims: int
    crude_mortality_rate_per_1000: float
    total_benefit_paid: float
    total_premium_collected: float
    loss_ratio: float
    avg_face_amount: float
    avg_annual_premium: float
    risk_tier_distribution: Dict[str, int]
    gender_split: Dict[str, int]
    mean_age: float

    def to_dict(self) -> dict:
        return asdict(self)


class ClaimsAnalyzer:
    """
    Analyzes a claims portfolio DataFrame.

    Input: DataFrame from portfolio/generator.py (or real data with same schema).
    """

    AGE_BAND_MIDPOINTS = {
        "18-24": 21, "25-34": 30, "35-44": 40,
        "45-54": 50, "55-64": 60, "65+": 68,
    }
    RISK_FLAGS = ["smoker", "diabetes", "hypertension",
                  "hyperlipidemia", "family_history_chd", "alcohol_heavy"]
    ASSUMED_MULTIPLIERS = {
        "smoker":              ASSUMPTIONS["risk_factors"].smoking,
        "diabetes":            ASSUMPTIONS["risk_factors"].diabetes,
        "hypertension":        ASSUMPTIONS["risk_factors"].hypertension,
        "hyperlipidemia":      ASSUMPTIONS["risk_factors"].hyperlipidemia,
        "family_history_chd":  ASSUMPTIONS["risk_factors"].family_history_chd,
        "alcohol_heavy":       ASSUMPTIONS["risk_factors"].alcohol_heavy,
    }

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._mort = ASSUMPTIONS["mortality"]

    # ------------------------------------------------------------------
    def portfolio_summary(self) -> PortfolioSummary:
        """High-level portfolio KPIs."""
        df = self.df
        total_prem = df["total_premium_collected"].sum()
        total_ben = df["actual_benefit_paid"].sum()
        exp = df["exposure_years"].sum()

        return PortfolioSummary(
            total_policies=len(df),
            total_exposure_years=round(float(exp), 1),
            total_claims=int(df["claim_event"].sum()),
            crude_mortality_rate_per_1000=round(float(df["claim_event"].sum() / exp * 1000), 3) if exp > 0 else 0.0,
            total_benefit_paid=float(total_ben),
            total_premium_collected=float(total_prem),
            loss_ratio=round(float(total_ben / total_prem), 4) if total_prem > 0 else 0.0,
            avg_face_amount=round(float(df["face_amount"].mean()), 2),
            avg_annual_premium=round(float(df["annual_premium"].mean()), 2),
            risk_tier_distribution=df["risk_tier"].value_counts().to_dict(),
            gender_split=df["gender"].value_counts().to_dict(),
            mean_age=round(float(df["issue_age"].mean()), 1),
        )

    # ------------------------------------------------------------------
    def cohort_mortality_rates(self) -> pd.DataFrame:
        """
        Observed vs. assumed q(x) per 1,000 by (age_band, gender).

        ae_ratio = observed_q / assumed_q.  Should be ~0.85 overall if the
        Cambodia mortality adjustment hypothesis holds.
        """
        rows = []
        for (band, gender), grp in self.df.groupby(["age_band", "gender"]):
            rep_age = self.AGE_BAND_MIDPOINTS.get(str(band), 40)
            assumed_q = get_base_mortality_rate(rep_age, str(gender), self._mort)
            exp = float(grp["exposure_years"].sum())
            deaths = int(grp["claim_event"].sum())
            obs_q = deaths / exp * 1000 if exp > 0 else 0.0
            rows.append({
                "age_band": band,
                "gender": gender,
                "policies": len(grp),
                "exposure_years": round(exp, 1),
                "observed_deaths": deaths,
                "observed_q_per_1000": round(obs_q, 3),
                "assumed_q_per_1000": round(assumed_q, 3),
                "ae_ratio": round(obs_q / assumed_q, 3) if assumed_q > 0 else None,
            })
        return pd.DataFrame(rows).sort_values(["gender", "age_band"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    def risk_factor_lift(self) -> pd.DataFrame:
        """
        Observed mortality lift per risk flag vs. clean lives (no risk flags).

        Returns observed_lift alongside assumed_multiplier.
        Differences reveal which assumptions need calibrating.
        """
        df = self.df
        clean_mask = ~df[self.RISK_FLAGS].any(axis=1)
        clean = df[clean_mask]
        exp_clean = float(clean["exposure_years"].sum())

        if exp_clean > 0 and clean["claim_event"].sum() > 0:
            baseline_rate = clean["claim_event"].sum() / exp_clean * 1000
        else:
            # Fallback: use average q(x) for 35yo male (representative)
            baseline_rate = get_base_mortality_rate(35, "M", self._mort)

        rows = []
        for flag in self.RISK_FLAGS:
            grp = df[df[flag] == True]
            if len(grp) == 0:
                continue
            exp = float(grp["exposure_years"].sum())
            deaths = int(grp["claim_event"].sum())
            flag_rate = deaths / exp * 1000 if exp > 0 else 0.0
            obs_lift = round(flag_rate / baseline_rate, 3) if baseline_rate > 0 else None

            # Poisson CI on observed lift: ±1.96 × sqrt(D) / expected_D
            ci_half = None
            if deaths > 0 and baseline_rate > 0 and exp > 0:
                # CI on the rate, then translate to lift
                ci_rate = 1.96 * np.sqrt(deaths) / exp * 1000
                ci_half = round(ci_rate / baseline_rate, 3)

            rows.append({
                "risk_factor": flag,
                "n_policies": len(grp),
                "observed_deaths": deaths,
                "observed_lift": obs_lift,
                "assumed_multiplier": self.ASSUMED_MULTIPLIERS.get(flag),
                "ci_half": ci_half,
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    def experience_vs_expected(self) -> pd.DataFrame:
        """
        A/E table by (age_band, gender, risk_tier).

        Expected deaths = exposure × assumed_q(x)/1000 × avg_mortality_ratio
        A/E = actual / expected
        """
        rows = []
        for (band, gender, tier), grp in self.df.groupby(["age_band", "gender", "risk_tier"]):
            rep_age = self.AGE_BAND_MIDPOINTS.get(str(band), 40)
            assumed_q = get_base_mortality_rate(rep_age, str(gender), self._mort)
            exp = float(grp["exposure_years"].sum())
            actual = int(grp["claim_event"].sum())
            avg_mr = float(grp["mortality_ratio"].mean())
            expected = exp * (assumed_q / 1000.0) * avg_mr
            ae = round(actual / expected, 3) if expected > 0 else None
            rows.append({
                "age_band": band,
                "gender": gender,
                "risk_tier": tier,
                "policies": len(grp),
                "exposure_years": round(exp, 1),
                "actual_deaths": actual,
                "expected_deaths": round(expected, 2),
                "ae_ratio": ae,
            })
        return (
            pd.DataFrame(rows)
            .sort_values(["gender", "age_band", "risk_tier"])
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------
    def overall_ae_ratio(self) -> float:
        """
        Aggregate A/E ratio computed at the individual policy level.

        Uses each policy's own base_q_x and mortality_ratio to compute
        expected deaths, avoiding midpoint-age bias from cohort grouping.

        Expected deaths (policy i) = base_q_x_i/1000 × MR_i × exposure_i
        A/E = sum(actual_deaths) / sum(expected_deaths)

        Should converge to ~0.85 as portfolio grows (validates Cambodia hypothesis).
        """
        df = self.df
        df = df.copy()
        df["expected_death_prob"] = (
            df["base_q_x_per_1000"] / 1000.0
        ) * df["mortality_ratio"] * df["exposure_years"]
        total_expected = df["expected_death_prob"].sum()
        total_actual = df["claim_event"].sum()
        return round(float(total_actual / total_expected), 4) if total_expected > 0 else 1.0


if __name__ == "__main__":
    from portfolio.generator import load_portfolio
    df = load_portfolio()
    a = ClaimsAnalyzer(df)

    s = a.portfolio_summary()
    print(f"\n=== Portfolio Summary ===")
    print(f"Policies:        {s.total_policies:,}")
    print(f"Exposure:        {s.total_exposure_years:,.0f} person-years")
    print(f"Claims:          {s.total_claims:,}")
    print(f"Loss ratio:      {s.loss_ratio:.1%}")
    print(f"Risk tier dist:  {s.risk_tier_distribution}")

    print(f"\n=== Cohort Mortality (sample) ===")
    print(a.cohort_mortality_rates().head(8).to_string(index=False))

    print(f"\n=== Risk Factor Lifts ===")
    print(a.risk_factor_lift().to_string(index=False))

    print(f"\n=== Overall A/E Ratio ===")
    print(f"A/E = {a.overall_ae_ratio():.3f}  (hypothesis: ~0.85)")
