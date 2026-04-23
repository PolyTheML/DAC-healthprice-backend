"""
Pricing Calibration Engine

Compares observed claims experience (from ClaimsAnalyzer) against assumed
risk factor multipliers and proposes updated values with Poisson confidence intervals.

Key output: CalibrationReport — current vs. proposed multipliers + overall A/E summary.
This feeds into RiskFactorMultipliers.from_calibration() to hot-swap calibrated
assumptions into the live pricing engine.
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from medical_reader.pricing.assumptions import (
    ASSUMPTIONS,
    RiskFactorMultipliers,
    ASSUMPTION_VERSION,
)


@dataclass
class FactorCalibration:
    risk_factor: str
    current_multiplier: float
    proposed_multiplier: Optional[float]      # None if insufficient data
    ci_lower: Optional[float]
    ci_upper: Optional[float]
    n_policies: int
    observed_deaths: int
    status: str                               # "confirm" | "revise" | "flag" | "insufficient"


@dataclass
class CalibrationReport:
    overall_ae_ratio: float                   # Cambodia mortality vs. WHO SEA assumed
    overall_ae_interpretation: str
    factor_calibrations: List[FactorCalibration]
    proposed_version: str
    recommendation_summary: str

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


_CHANGE_THRESHOLD = 0.05    # Propose revision if |proposed - current| / current > 5%
_MIN_DEATHS = 5             # Minimum deaths for a statistically meaningful calibration


def _status(current: float, proposed: float, deaths: int) -> str:
    if deaths < _MIN_DEATHS:
        return "insufficient"
    rel_change = abs(proposed - current) / current
    if rel_change <= _CHANGE_THRESHOLD:
        return "confirm"
    elif rel_change <= 0.20:
        return "revise"
    else:
        return "flag"


def calibrate_assumptions(
    ae_df: pd.DataFrame,
    lift_df: pd.DataFrame,
    overall_ae: float,
    current_assumptions: RiskFactorMultipliers = None,
) -> CalibrationReport:
    """
    Produce a CalibrationReport from the claims analysis outputs.

    Args:
        ae_df:              Output of ClaimsAnalyzer.experience_vs_expected()
        lift_df:            Output of ClaimsAnalyzer.risk_factor_lift()
        overall_ae:         Output of ClaimsAnalyzer.overall_ae_ratio()
        current_assumptions: RiskFactorMultipliers to compare against (default: global ASSUMPTIONS)

    Returns:
        CalibrationReport with current vs. proposed multipliers.
    """
    if current_assumptions is None:
        current_assumptions = ASSUMPTIONS["risk_factors"]

    # ---- Overall A/E interpretation ----
    if overall_ae < 0.80:
        interp = f"Cambodia mortality is significantly below WHO SEA ({overall_ae:.0%} of expected). Consider downward revision of base mortality tables."
    elif overall_ae < 0.92:
        interp = f"Cambodia mortality is moderately below WHO SEA ({overall_ae:.0%} of expected). A calibration factor of {overall_ae:.2f}x is recommended."
    elif overall_ae < 1.08:
        interp = f"Cambodia mortality is broadly in line with WHO SEA ({overall_ae:.0%} of expected). No structural revision needed."
    else:
        interp = f"Cambodia mortality exceeds WHO SEA ({overall_ae:.0%} of expected). Consider upward revision of base mortality tables."

    # ---- Factor-level calibrations ----
    factor_map = lift_df.set_index("risk_factor").to_dict(orient="index")
    calibrations: List[FactorCalibration] = []

    for flag, current_val in [
        ("smoker",             current_assumptions.smoking),
        ("diabetes",           current_assumptions.diabetes),
        ("hypertension",       current_assumptions.hypertension),
        ("hyperlipidemia",     current_assumptions.hyperlipidemia),
        ("family_history_chd", current_assumptions.family_history_chd),
        ("alcohol_heavy",      current_assumptions.alcohol_heavy),
    ]:
        row = factor_map.get(flag, {})
        obs_lift = row.get("observed_lift")
        ci_half = row.get("ci_half")
        n_pol = int(row.get("n_policies", 0))
        deaths = int(row.get("observed_deaths", 0))

        if obs_lift is None or deaths < _MIN_DEATHS:
            calibrations.append(FactorCalibration(
                risk_factor=flag,
                current_multiplier=current_val,
                proposed_multiplier=None,
                ci_lower=None,
                ci_upper=None,
                n_policies=n_pol,
                observed_deaths=deaths,
                status="insufficient",
            ))
            continue

        # Scale observed lift by overall A/E to remove Cambodia base-mortality effect.
        # This isolates the relative risk from the factor itself.
        adj_lift = obs_lift / overall_ae if overall_ae > 0 else obs_lift
        proposed = round(max(1.0, adj_lift), 3)   # Multiplier ≥ 1.0

        ci_lower = round(max(1.0, proposed - (ci_half or 0)), 3)
        ci_upper = round(proposed + (ci_half or 0), 3)

        calibrations.append(FactorCalibration(
            risk_factor=flag,
            current_multiplier=round(current_val, 3),
            proposed_multiplier=proposed,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_policies=n_pol,
            observed_deaths=deaths,
            status=_status(current_val, proposed, deaths),
        ))

    # ---- Summary recommendation ----
    revise_count = sum(1 for c in calibrations if c.status in ("revise", "flag"))
    confirm_count = sum(1 for c in calibrations if c.status == "confirm")
    insufficient_count = sum(1 for c in calibrations if c.status == "insufficient")

    summary = (
        f"Overall A/E = {overall_ae:.3f}. "
        f"{confirm_count} factor(s) confirmed, {revise_count} factor(s) need revision, "
        f"{insufficient_count} factor(s) have insufficient data. "
        f"Recommended action: {'Apply calibration' if revise_count > 0 else 'Assumptions validated — no changes needed'}."
    )

    return CalibrationReport(
        overall_ae_ratio=overall_ae,
        overall_ae_interpretation=interp,
        factor_calibrations=calibrations,
        proposed_version=f"v2.1-calibrated-{ASSUMPTION_VERSION[-10:]}",
        recommendation_summary=summary,
    )


def build_calibrated_assumptions(report: CalibrationReport) -> RiskFactorMultipliers:
    """
    Construct a new RiskFactorMultipliers using the proposed values from the report.

    Only replaces factors with status 'revise' or 'flag'.
    Factors with status 'confirm' or 'insufficient' keep their current values.
    """
    current = ASSUMPTIONS["risk_factors"]
    overrides: Dict[str, float] = {}

    for fc in report.factor_calibrations:
        if fc.status in ("revise", "flag") and fc.proposed_multiplier is not None:
            overrides[fc.risk_factor] = fc.proposed_multiplier

    return RiskFactorMultipliers(
        smoking=overrides.get("smoker", current.smoking),
        alcohol_heavy=overrides.get("alcohol_heavy", current.alcohol_heavy),
        bmi_underweight=current.bmi_underweight,
        bmi_overweight=current.bmi_overweight,
        bmi_obese_1=current.bmi_obese_1,
        bmi_obese_2=current.bmi_obese_2,
        bp_elevated=current.bp_elevated,
        bp_stage1=current.bp_stage1,
        bp_stage2=current.bp_stage2,
        diabetes=overrides.get("diabetes", current.diabetes),
        hypertension=overrides.get("hypertension", current.hypertension),
        hyperlipidemia=overrides.get("hyperlipidemia", current.hyperlipidemia),
        family_history_chd=overrides.get("family_history_chd", current.family_history_chd),
    )


if __name__ == "__main__":
    from portfolio.generator import load_portfolio
    from portfolio.analysis import ClaimsAnalyzer

    df = load_portfolio()
    analyzer = ClaimsAnalyzer(df)

    ae_df = analyzer.experience_vs_expected()
    lift_df = analyzer.risk_factor_lift()
    overall_ae = analyzer.overall_ae_ratio()

    report = calibrate_assumptions(ae_df, lift_df, overall_ae)

    print(f"\n=== Calibration Report ===")
    print(f"Overall A/E:   {report.overall_ae_ratio:.3f}")
    print(f"Interpretation: {report.overall_ae_interpretation}")
    print(f"\n{report.recommendation_summary}")

    print(f"\n{'Factor':<22} {'Current':>8} {'Proposed':>10} {'CI':>20}  Status")
    print("-" * 72)
    for fc in report.factor_calibrations:
        ci = f"[{fc.ci_lower:.3f}, {fc.ci_upper:.3f}]" if fc.ci_lower else "—"
        proposed = f"{fc.proposed_multiplier:.3f}" if fc.proposed_multiplier else "N/A"
        print(f"{fc.risk_factor:<22} {fc.current_multiplier:>8.3f} {proposed:>10}  {ci:>20}  {fc.status}")
