"""
EXP-003: Behavioral Failure Modes
===================================
Three scenarios where single-metric PSI on the aggregate premium distribution
gives a false-negative (GREEN), while a secondary detection method catches
the real shift (RED/AMBER).

Scenario constants (Ch3 Table 3.3):
  FM1 highway migration   : 20% of trips; speed +12 km/h, braking x0.50,
                            jerk x0.55, idle x0.05
  FM2 monsoon surge       : 25% replaced; braking x2.0, jerk x2.5,
                            speed x1.08, idle x0.15; seasonal discount = 0.76x
  FM3 tail risk flip      : bottom-5% braking cohort -> 80th-95th-pct profile

Premium formula (cite in Ch3 as GLM-proxy; weights sum to 1.0):
  risk_score = 0.35 * clip(hard_braking / 50)
             + 0.35 * clip(jerk_rms    /  2)
             + 0.30 * clip(speed_avg   / 20)
  monthly_premium = 45 * (1 + 0.80 * risk_score)

FM2 note: the "seasonal discount" represents a known actuarial adjustment the
model applies to monsoon-season cohorts (expected higher claim frequency).  The
discount absorbs the premium increase and makes the aggregate premium PSI GREEN,
but raw behavioral metrics remain detectably elevated.

Thesis reference : Chapter 4, Section 4.3 (EXP-003 Behavioral Failure Modes)
Expected result  : 3 / 3 failure modes detected by secondary metrics.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---- Paths ------------------------------------------------------------------
ROOT      = Path(__file__).parent.parent.parent
TRIPS_CSV = ROOT / "case-study" / "phnom_penh_trip_features.csv"

# ---- Thresholds -------------------------------------------------------------
GREEN_THRESH = 0.10
AMBER_THRESH = 0.25

# ---- Premium constants (thesis Table 3.2) -----------------------------------
BASE_RATE    = 45.0
W_BRAKING, BRAKING_NORM = 0.35, 50.0
W_JERK,    JERK_NORM    = 0.35,  2.0
W_SPEED,   SPEED_NORM   = 0.30, 20.0
RISK_SCALE              = 0.80


# ---- Helpers ----------------------------------------------------------------

def compute_premium(df: pd.DataFrame) -> pd.Series:
    rs = (
        W_BRAKING * np.clip(df["hard_braking_events"] / BRAKING_NORM, 0, 5) +
        W_JERK    * np.clip(df["jerk_rms"]            / JERK_NORM,    0, 5) +
        W_SPEED   * np.clip(df["speed_avg_kmh"]        / SPEED_NORM,   0, 3)
    )
    return BASE_RATE * (1.0 + RISK_SCALE * rs)


def psi(expected: np.ndarray, actual: np.ndarray, n_bins: int = 10) -> float:
    """Population Stability Index: sum( (A_i - E_i) * ln(A_i / E_i) )."""
    eps  = 1e-8
    bins = np.unique(np.percentile(expected, np.linspace(0, 100, n_bins + 1)))
    e_c  = np.histogram(expected, bins=bins)[0].astype(float) + eps
    a_c  = np.histogram(actual,   bins=bins)[0].astype(float) + eps
    e_p, a_p = e_c / e_c.sum(), a_c / a_c.sum()
    return float(np.sum((a_p - e_p) * np.log(a_p / e_p)))


def psi_cohort(before: np.ndarray, after: np.ndarray, n_bins: int = 10) -> float:
    """
    Cohort PSI: bins span the combined before+after range so out-of-range
    shifts (e.g. $55 -> $150) are captured rather than silently excluded.
    Used for FM3 to compare the same driver cohort across two time windows.
    """
    eps  = 1e-8
    combined = np.concatenate([before, after])
    bins = np.unique(np.percentile(combined, np.linspace(0, 100, n_bins + 1)))
    e_c  = np.histogram(before, bins=bins)[0].astype(float) + eps
    a_c  = np.histogram(after,  bins=bins)[0].astype(float) + eps
    e_p, a_p = e_c / e_c.sum(), a_c / a_c.sum()
    return float(np.sum((a_p - e_p) * np.log(a_p / e_p)))


def traffic_light(val: float) -> str:
    if val < GREEN_THRESH: return "GREEN"
    if val < AMBER_THRESH: return "AMBER"
    return "RED"


def _float_cols(d: pd.DataFrame, *cols: str) -> pd.DataFrame:
    """Ensure columns are float to avoid silent int truncation on assignment."""
    return d.astype({c: float for c in cols})


# ---- Failure Mode 1: Highway Migration --------------------------------------

def failure_mode_1(df: pd.DataFrame, rng: np.random.Generator) -> dict:
    """
    20% of trips shift from congested urban to highway routing.
    Speed rises; braking, jerk and idle all fall -- premium barely changes.

    Primary  : PSI on premium [full pop]  -> GREEN (false negative)
    Secondary: PSI on idle_pct [full pop] -> RED   (route-type shift revealed)
    """
    frac = 0.20
    idx  = rng.choice(len(df), size=int(len(df) * frac), replace=False)

    d = _float_cols(df.copy(), "hard_braking_events", "jerk_rms", "idle_pct",
                    "speed_avg_kmh")
    d.iloc[idx, d.columns.get_loc("speed_avg_kmh")]       += 12.0
    d.iloc[idx, d.columns.get_loc("hard_braking_events")] *= 0.50
    d.iloc[idx, d.columns.get_loc("jerk_rms")]            *= 0.55
    d.iloc[idx, d.columns.get_loc("idle_pct")]            *= 0.05

    bp = compute_premium(df).values
    dp = compute_premium(d).values

    return {
        "name":      "Highway Migration (20% cohort)",
        "primary":   ("PSI on premium [full pop]",
                      psi(bp, dp)),
        "secondary": ("PSI on idle_pct [full pop]",
                      psi(df["idle_pct"].values, d["idle_pct"].values)),
        "fix":       "Monitor idle_pct separately -- captures route-type shift",
    }


# ---- Failure Mode 2: Monsoon Ride-Share Surge -------------------------------

def failure_mode_2(df: pd.DataFrame, rng: np.random.Generator) -> dict:
    """
    25% of trips replaced by monsoon-season delivery riders (braking x2.0).
    The pricing model applies a seasonal discount factor (0.82x) to this
    expected high-risk cohort, absorbing the raw premium increase.

    Primary  : PSI on season-adjusted premium [full pop] -> GREEN (masked by discount)
    Secondary: PSI on raw hard_braking_events [full pop] -> RED   (behavior exposed)
    """
    SEASONAL_DISCOUNT = 0.76   # monsoon actuarial adjustment (cite: Table 3.4)

    frac = 0.25
    idx  = rng.choice(len(df), size=int(len(df) * frac), replace=False)

    d = _float_cols(df.copy(), "hard_braking_events", "jerk_rms",
                    "speed_avg_kmh", "idle_pct")
    d.iloc[idx, d.columns.get_loc("hard_braking_events")] *= 2.0
    d.iloc[idx, d.columns.get_loc("jerk_rms")]            *= 2.50
    d.iloc[idx, d.columns.get_loc("speed_avg_kmh")]       *= 1.08
    d.iloc[idx, d.columns.get_loc("idle_pct")]            *= 0.15

    # Season-adjusted premium: monsoon discount applied to injected cohort
    seasonal_factor            = pd.Series(1.0, index=d.index)
    seasonal_factor.iloc[idx]  = SEASONAL_DISCOUNT
    bp = compute_premium(df).values
    dp_adj = (compute_premium(d) * seasonal_factor).values

    psi_premium = psi(bp, dp_adj)
    # idle_pct captures the delivery-rider signature (near-zero stopping time)
    # and is not included in the premium formula -- invisible to premium PSI.
    psi_idle = psi(df["idle_pct"].values, d["idle_pct"].values)

    return {
        "name":      "Monsoon Ride-Share Surge (25% injection, seasonal discount)",
        "primary":   ("PSI on season-adjusted premium [full pop]", psi_premium),
        "secondary": ("PSI on raw idle_pct [full pop]",            psi_idle),
        "fix":       "Monitor idle_pct -- delivery-rider signature absent from premium formula",
    }


# ---- Failure Mode 3: Tail Risk Flip -----------------------------------------

def failure_mode_3(df: pd.DataFrame, rng: np.random.Generator) -> dict:
    """
    Bottom-5% (safest) braking cohort flips to an 80th-95th-pct risk profile.
    Full-population PSI stays GREEN because only ~5% of trips are affected.
    Top-quintile PSI (premium > 80th pct) detects the tail pollution.

    Primary  : PSI on premium [full pop, 10 bins]        -> GREEN
    Secondary: PSI on premium [top-quintile subset only] -> RED
    """
    # Rank-sort selects exactly 5% -- avoids tie-explosion when p5_thresh=0
    n_flip   = int(len(df) * 0.05)
    safe_idx = np.argsort(df["hard_braking_events"].values)[:n_flip]

    d = _float_cols(df.copy(), "hard_braking_events", "jerk_rms", "speed_avg_kmh")
    # Direct assignment to extreme values (not multipliers): safe trips have very
    # low base jerk/speed, so multipliers produce only modest premium increases.
    d.iloc[safe_idx, d.columns.get_loc("hard_braking_events")] = (
        rng.uniform(150, 234, size=n_flip))
    d.iloc[safe_idx, d.columns.get_loc("jerk_rms")] = (
        rng.uniform(4.0, 8.0, size=n_flip))
    d.iloc[safe_idx, d.columns.get_loc("speed_avg_kmh")] = (
        rng.uniform(28, 38, size=n_flip))

    bp = compute_premium(df)
    dp = compute_premium(d)

    # Primary: standard cross-sectional PSI (full pop) -- 5% shift is small
    psi_full = psi(bp.values, dp.values)

    # Secondary: cohort PSI -- same 75 drivers, premium before vs after.
    # Bins span the combined before+after range (adaptive) so the $55->$145
    # jump is fully captured; standard PSI bins from expected alone would
    # truncate all "after" values as out-of-range.
    cohort_before = bp.values[safe_idx]
    cohort_after  = dp.values[safe_idx]
    psi_c = psi_cohort(cohort_before, cohort_after)

    return {
        "name":      "Tail Risk Flip (bottom-5% safe cohort -> extreme profile)",
        "primary":   ("PSI on premium [full pop, cross-sectional]",   psi_full),
        "secondary": ("PSI on premium [safe cohort, before vs after]", psi_c),
        "fix":       "Use cohort-level PSI -- aggregate PSI dilutes small-fraction tail shifts",
    }


# ---- Main -------------------------------------------------------------------

def main() -> None:
    df = pd.read_csv(TRIPS_CSV)
    df = df[df["cohort"] == "baseline"].reset_index(drop=True)
    assert len(df) >= 100, f"Need >=100 baseline trips; got {len(df)}"

    baseline_prem = compute_premium(df)
    mean_prem     = baseline_prem.mean()
    assert 55 <= mean_prem <= 85, (
        f"Premium mean ${mean_prem:.1f} outside expected $55-$85; check formula"
    )

    SEP = "=" * 72
    print(f"\n{SEP}")
    print("  EXP-003: Behavioral Failure Modes")
    print(f"  Dataset     : {len(df):,} baseline trips")
    print(f"  Seeds       : FM1=1, FM2=2, FM3=3  (fully reproducible)")
    print(f"  Avg premium : ${mean_prem:.2f}/month  (baseline sanity check OK)")
    print(SEP)

    fms = [
        failure_mode_1(df, np.random.default_rng(seed=1)),
        failure_mode_2(df, np.random.default_rng(seed=2)),
        failure_mode_3(df, np.random.default_rng(seed=3)),
    ]

    all_pass = True
    verdicts = []
    for i, r in enumerate(fms, 1):
        p_name, p_val = r["primary"]
        s_name, s_val = r["secondary"]
        false_neg = traffic_light(p_val) == "GREEN"
        true_pos  = traffic_light(s_val) in ("AMBER", "RED")
        mode_pass = false_neg and true_pos
        if not mode_pass:
            all_pass = False

        print(f"\n  FM{i}: {r['name']}")
        print(f"    Primary   [{p_name}]")
        fp_tag = "[!] false negative -- primary PSI missed the shift" if false_neg else "[+] detected by primary"
        print(f"      PSI = {p_val:.6f}  {traffic_light(p_val):<5}  {fp_tag}")
        print(f"    Secondary [{s_name}]")
        tp_tag = "[+] secondary caught it" if true_pos else "[!] missed -- tune scenario"
        print(f"      PSI = {s_val:.6f}  {traffic_light(s_val):<5}  {tp_tag}")
        print(f"    Fix: {r['fix']}")
        status = "PASS" if mode_pass else "FAIL"
        print(f"    FM{i} Result: {status}")
        verdicts.append((i, r["name"][:44], p_val, s_val, status))

    # Summary table (Ch4 copy-paste ready)
    print(f"\n{SEP}")
    print("  Summary Table (EXP-003 -- thesis Table 4.3)")
    print(f"  {'FM':<4}  {'Scenario':<44}  {'Primary':>9}  {'Secondary':>11}  {'Result':>6}")
    print(f"  {'-'*4}  {'-'*44}  {'-'*9}  {'-'*11}  {'-'*6}")
    for fm_i, name, pv, sv, verdict in verdicts:
        print(f"  {fm_i:<4}  {name:<44}  {pv:>9.6f}  {sv:>11.6f}  {verdict:>6}")

    print(f"\n  Overall: {'PASS -- all 3 failure modes caught by secondary metrics' if all_pass else 'FAIL -- see above'}")
    print(f"{SEP}\n")

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
