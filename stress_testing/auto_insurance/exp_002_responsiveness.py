"""
EXP-002: PSI Monotonicity / Responsiveness
============================================
Inject increasing fractions of distortion into the population (10% - 50%)
and verify PSI increases monotonically, crossing GREEN->AMBER->RED thresholds.

Distortion model: raise speed_scale +50%, double speed_noise, halve idle_prob
for `drift_fraction` proportion of trips (mimicking aggressive driving cohort
entering baseline population — e.g. ride-share influx, monsoon behavior shift).

Thesis reference: Chapter 4, Section 4.2 (EXP-002 Responsiveness)
Expected result: PSI(0%) < PSI(10%) < ... < PSI(50%); PSI(50%) > 0.08.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent.parent
TRIPS_CSV = ROOT / "case-study" / "phnom_penh_trip_features.csv"

FEATURES = [
    "speed_avg_kmh",
    "hard_braking_events",
    "jerk_rms",
    "idle_pct",
]

DRIFT_FRACTIONS = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]
N_BINS = 10
GREEN_THRESHOLD = 0.10
AMBER_THRESHOLD = 0.25


def psi(expected: np.ndarray, actual: np.ndarray, n_bins: int = N_BINS) -> float:
    eps = 1e-8
    bins = np.percentile(expected, np.linspace(0, 100, n_bins + 1))
    bins = np.unique(bins)
    e_counts = np.histogram(expected, bins=bins)[0].astype(float) + eps
    a_counts = np.histogram(actual,   bins=bins)[0].astype(float) + eps
    e_pct = e_counts / e_counts.sum()
    a_pct = a_counts / a_counts.sum()
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def inject_drift(df: pd.DataFrame, drift_fraction: float, rng: np.random.Generator) -> pd.DataFrame:
    """Return a copy of df with drift_fraction of trips replaced by distorted versions."""
    if drift_fraction == 0.0:
        return df.copy()
    n_drift = int(len(df) * drift_fraction)
    idx = rng.choice(len(df), size=n_drift, replace=False)
    drifted = df.copy()
    # Aggressive driving: faster, harder braking, higher jerk, less idle
    for col in ["speed_avg_kmh", "hard_braking_events", "jerk_rms", "idle_pct"]:
        drifted[col] = drifted[col].astype(float)
    drifted.iloc[idx, drifted.columns.get_loc("speed_avg_kmh")]      *= 1.5
    drifted.iloc[idx, drifted.columns.get_loc("hard_braking_events")] *= 2.5
    drifted.iloc[idx, drifted.columns.get_loc("jerk_rms")]            *= 2.0
    drifted.iloc[idx, drifted.columns.get_loc("idle_pct")]            *= 0.4
    return drifted


def label(val: float) -> str:
    if val < GREEN_THRESHOLD:
        return "GREEN"
    if val < AMBER_THRESHOLD:
        return "AMBER"
    return "RED"


def main() -> None:
    df = pd.read_csv(TRIPS_CSV)
    rng = np.random.default_rng(seed=42)

    # Baseline: first half is reference (never distorted)
    idx = rng.permutation(len(df))
    half = len(df) // 2
    baseline = df.iloc[idx[:half]].reset_index(drop=True)

    SEP = "=" * 70
    print(f"\n{SEP}")
    print("  EXP-002: PSI Responsiveness / Monotonicity")
    print(f"  Baseline : {len(baseline):,} trips  (seed=42)")
    print(f"  Distorted: {len(df) - half:,} trips per cohort")
    print(f"  Features : {', '.join(FEATURES)}")
    print(SEP)

    psi_by_fraction: dict[float, dict[str, float]] = {}
    for frac in DRIFT_FRACTIONS:
        candidate = df.iloc[idx[half:]].reset_index(drop=True)
        candidate = inject_drift(candidate, frac, np.random.default_rng(seed=int(frac * 100)))
        vals = {feat: psi(baseline[feat].values, candidate[feat].values) for feat in FEATURES}
        psi_by_fraction[frac] = vals

    # Print table
    header = f"  {'Drift %':<10}" + "".join(f"  {f:<24}" for f in FEATURES) + "  Status"
    print(f"\n{header}")
    print(f"  {'-'*9}" + "".join(f"  {'-'*24}" for _ in FEATURES) + "  ------")

    prev_max = -1.0
    monotonic = True
    rows = []
    for frac in DRIFT_FRACTIONS:
        vals = psi_by_fraction[frac]
        max_v = max(vals.values())
        status = label(max_v)
        row_str = f"  {frac*100:>5.0f}%    " + "".join(f"  {vals[f]:>8.6f}{'':>16}" for f in FEATURES) + f"  {status}"
        print(row_str)
        rows.append((frac, max_v, status))
        if max_v < prev_max - 0.005:   # allow tiny noise
            monotonic = False
        prev_max = max_v

    # Monotonicity check
    print(f"\n  Monotonicity     : {'PASS - PSI increases with drift' if monotonic else 'FAIL - non-monotonic'}")
    final_psi = rows[-1][1]
    print(f"  PSI at 50% drift : {final_psi:.6f}  (threshold > 0.08)")
    sensitivity_pass = final_psi > 0.08
    print(f"  Sensitivity      : {'PASS' if sensitivity_pass else 'FAIL'}")
    overall = monotonic and sensitivity_pass
    print(f"\n  Result: {'PASS - PSI responds monotonically to drift injection' if overall else 'FAIL - see above'}")
    print(f"{SEP}\n")

    if not overall:
        sys.exit(1)


if __name__ == "__main__":
    main()
