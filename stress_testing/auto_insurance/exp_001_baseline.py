"""
EXP-001: Baseline PSI Validation
=================================
Split the 1,500-trip dataset into two random halves drawn from the same
distribution.  PSI on every telematics feature must be 0.000 ± 0.010.

Thesis reference: Chapter 4, Section 4.1 (EXP-001 Baseline Validation)
Expected result:  PSI = 0.000000 for all features (by construction).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent
TRIPS_CSV = ROOT / "case-study" / "phnom_penh_trip_features.csv"

# ── PSI features (thesis Table 3.1) ───────────────────────────────────────────
FEATURES = [
    "speed_avg_kmh",
    "speed_p90_kmh",
    "hard_braking_events",
    "harsh_jerk_events",
    "jerk_rms",
    "idle_pct",
    "vibration_avg",
]

N_BINS = 10
PASS_THRESHOLD = 0.10   # GREEN < 0.10 per industry convention


# ── PSI calculation ────────────────────────────────────────────────────────────
def psi(expected: np.ndarray, actual: np.ndarray, n_bins: int = N_BINS) -> float:
    """Population Stability Index.  PSI = Σ (A_i - E_i) * ln(A_i / E_i)."""
    eps = 1e-8
    bins = np.percentile(expected, np.linspace(0, 100, n_bins + 1))
    bins = np.unique(bins)                           # collapse identical edges
    e_counts = np.histogram(expected, bins=bins)[0].astype(float) + eps
    a_counts = np.histogram(actual,   bins=bins)[0].astype(float) + eps
    e_pct = e_counts / e_counts.sum()
    a_pct = a_counts / a_counts.sum()
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    df = pd.read_csv(TRIPS_CSV)
    assert len(df) >= 100, f"Need ≥100 trips; got {len(df)}"

    rng = np.random.default_rng(seed=42)
    idx = rng.permutation(len(df))
    half = len(df) // 2
    expected = df.iloc[idx[:half]]
    actual   = df.iloc[idx[half:]]

    SEP = "=" * 60
    print(f"\n{SEP}")
    print(f"  EXP-001: Baseline PSI Validation")
    print(f"  Dataset  : {len(df):,} trips  ->  {len(expected):,} expected / {len(actual):,} actual")
    print(f"  Seed     : 42 (reproducible)")
    print(f"  N bins   : {N_BINS} (percentile-based)")
    print(SEP)
    print(f"\n  {'Feature':<25} {'PSI':>10}  {'Status':>8}")
    print(f"  {'-'*25}  {'-'*10}  {'-'*8}")

    results = {}
    all_pass = True
    for feat in FEATURES:
        val = psi(expected[feat].values, actual[feat].values)
        status = "GREEN OK" if val < PASS_THRESHOLD else "RED FAIL"
        if val >= PASS_THRESHOLD:
            all_pass = False
        results[feat] = val
        print(f"  {feat:<25} {val:>10.6f}  {status:>8}")

    max_psi = max(results.values())
    print(f"\n  {'Max PSI':<25} {max_psi:>10.6f}")
    print(f"  {'Threshold':<25} {'< 0.100000':>10}")
    result_str = "PASS - All features GREEN" if all_pass else "FAIL - Unexpected drift detected"
    print(f"\n  Result: {result_str}")
    print(f"{SEP}\n")

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
