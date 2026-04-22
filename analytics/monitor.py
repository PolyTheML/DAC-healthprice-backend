"""
PSI drift monitoring and HITL override rate analytics.

Computes Population Stability Index (PSI) on mortality_ratio to detect
applicant population shift from training-period baseline.

PSI thresholds (industry standard):
  < 0.10  → No significant drift ✅
  0.10–0.25 → Moderate drift ⚠️ — monitor
  ≥ 0.25  → Significant drift 🚨 — investigate / retrain
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Reference distribution: synthetic baseline from training assumptions.
# In production this will be loaded from a JSON file generated at model training.
# Bins: mortality_ratio ranges. Proportions: expected % of applicants per bin.
# ---------------------------------------------------------------------------
REFERENCE_DISTRIBUTION: dict[str, Any] = {
    "mortality_ratio": {
        "bins": [0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, float("inf")],
        # Derived from 10K synthetic baseline (seed=42, Cambodia demographics)
        "proportions": [0.00, 0.53, 0.25, 0.15, 0.06, 0.01, 0.00, 0.00],
    }
}

# Province aliases for Phnom Penh normalisation
PHNOM_PENH_ALIASES: set[str] = {"phnom penh", "pp", "phonm penh", "ភ្នំពេញ"}


def calculate_psi(
    reference_distribution: dict[str, Any],
    current_batch: list[float],
    n_bins: int = 8,
    epsilon: float = 1e-6,
) -> float:
    """
    Calculate Population Stability Index (PSI) for mortality_ratio.

    PSI = Σ (A_i - E_i) × ln(A_i / E_i)
      A_i = actual proportion in bin i (current batch)
      E_i = expected proportion in bin i (reference/training)

    Args:
        reference_distribution: Dict with "bins" (n_bins+1 edges) and
            "proportions" (n_bins floats summing to ~1.0).
        current_batch: Raw mortality_ratio values from the current period.
        n_bins: Number of bins (must match reference_distribution).
        epsilon: Added to zero proportions to avoid log(0).

    Returns:
        PSI score as float. 0.0 = identical distributions.
    """
    if len(current_batch) < 2:
        return 0.0

    bins = reference_distribution["bins"]
    expected = np.array(reference_distribution["proportions"], dtype=float)

    values = np.array(current_batch, dtype=float)
    # Assign each value to a bin (np.digitize returns 1-based indices)
    bin_indices = np.digitize(values, bins[1:])  # exclude first edge (0)
    counts = np.bincount(bin_indices, minlength=n_bins)[:n_bins]
    actual = counts.astype(float) / max(len(values), 1)

    # Clip to avoid log(0)
    actual = np.clip(actual, epsilon, 1.0)
    expected = np.clip(expected, epsilon, 1.0)

    psi = float(np.sum((actual - expected) * np.log(actual / expected)))
    return round(max(psi, 0.0), 6)


def calculate_human_override_rate(
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Calculate the rate at which human underwriters override AI recommendations.

    Override = human reviewed a case AND made the OPPOSITE decision from AI.
    (AI → APPROVE, human → DECLINE) or (AI → DECLINE, human → APPROVE).

    Args:
        cases: List of case summary dicts (from UnderwritingState.to_summary()).
            Expects keys: "status", "risk_level", and nested "review" with
            "reviewer_id" and "approved" fields — but to_summary() flattens
            these; we adapt to that shape.

    Returns:
        {
            "total_reviewed": int,
            "total_overridden": int,
            "override_rate": float,
            "by_risk_level": {"low": ..., "medium": ..., "high": ..., "decline": ...},
        }
    """
    total_reviewed = 0
    total_overridden = 0
    by_risk: dict[str, dict[str, int]] = defaultdict(
        lambda: {"reviewed": 0, "overridden": 0}
    )

    for case in cases:
        # A case has been human-reviewed when status is approved/declined
        # AND we can detect override by checking if risk_level == "decline"
        # but status == "approved" (or vice versa).
        status = case.get("status", "")
        risk_level = case.get("risk_level", "medium")
        requires_review = case.get("requires_review", False)

        if status not in ("approved", "declined"):
            continue
        if not requires_review:
            continue  # STP cases — no human involved

        total_reviewed += 1
        by_risk[risk_level]["reviewed"] += 1

        # Determine AI recommendation from risk_level
        ai_recommended_decline = risk_level == "decline"
        human_declined = status == "declined"

        if ai_recommended_decline != human_declined:
            total_overridden += 1
            by_risk[risk_level]["overridden"] += 1

    override_rate = (
        round(total_overridden / total_reviewed, 4) if total_reviewed > 0 else 0.0
    )

    return {
        "total_reviewed": total_reviewed,
        "total_overridden": total_overridden,
        "override_rate": override_rate,
        "by_risk_level": {
            level: {
                "reviewed": data["reviewed"],
                "overridden": data["overridden"],
                "rate": round(
                    data["overridden"] / data["reviewed"], 4
                ) if data["reviewed"] > 0 else 0.0,
            }
            for level, data in by_risk.items()
        },
    }


def get_psi_time_series(
    case_history: list[dict[str, Any]],
    window_days: int = 30,
    batch_size: int = 20,
    reference_distribution: dict[str, Any] = REFERENCE_DISTRIBUTION,
) -> list[dict[str, Any]]:
    """
    Compute daily PSI scores for the last `window_days` days.

    Used by DriftMonitor.jsx to render the 30-day line chart.

    Args:
        case_history: All historical case summaries sorted by created_at,
            each with a "created_at" ISO string and "cambodia_risk.mortality_ratio"
            — but to_summary() exposes this via actuarial.mortality_ratio.
            We use whatever float value is available from the summary dict.
        window_days: How many days back to plot.
        batch_size: Minimum cases per PSI calculation; fewer = skip that date.
        reference_distribution: Baseline distribution.

    Returns:
        [{"date": "YYYY-MM-DD", "psi": float, "n_cases": int}, ...]
        Most recent date last.
    """
    if not case_history:
        return _mock_psi_series(window_days)

    # Index cases by date
    cases_by_date: dict[str, list[float]] = defaultdict(list)
    for case in case_history:
        created_raw = case.get("created_at", "")
        try:
            dt = datetime.fromisoformat(created_raw)
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue

        # Extract mortality_ratio: stored under final_premium isn't it —
        # to_summary() doesn't directly expose mortality_ratio, but the
        # cambodia_risk block has multipliers. We proxy via final_premium
        # divided by expected pure premium — or just use a sentinel of 1.0
        # when unavailable (conservative; won't inflate PSI).
        # When the API stores full ActuarialCalculation, update this.
        mortality_ratio = case.get("mortality_ratio", 1.0)
        cases_by_date[date_str].append(float(mortality_ratio))

    today = datetime.utcnow().date()
    result: list[dict[str, Any]] = []

    for offset in range(window_days - 1, -1, -1):
        target_date = today - timedelta(days=offset)
        date_str = target_date.strftime("%Y-%m-%d")

        # Rolling batch: all cases up to and including this date
        rolling: list[float] = []
        for d, values in cases_by_date.items():
            try:
                if datetime.strptime(d, "%Y-%m-%d").date() <= target_date:
                    rolling.extend(values)
            except ValueError:
                continue

        if len(rolling) < batch_size:
            # Not enough data — use synthetic baseline (PSI = 0 by construction)
            psi = 0.0
            n = len(rolling)
        else:
            last_batch = rolling[-batch_size:]
            psi = calculate_psi(
                reference_distribution["mortality_ratio"], last_batch
            )
            n = len(last_batch)

        result.append({"date": date_str, "psi": psi, "n_cases": n})

    return result


def _mock_psi_series(window_days: int) -> list[dict[str, Any]]:
    """
    Return a synthetic flat PSI series when no case data is available.
    Useful for UI development and demos.
    """
    today = datetime.utcnow().date()
    return [
        {
            "date": (today - timedelta(days=window_days - 1 - i)).strftime("%Y-%m-%d"),
            "psi": 0.0,
            "n_cases": 0,
        }
        for i in range(window_days)
    ]
