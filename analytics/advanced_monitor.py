"""
3-Pillar PSI Monitoring Framework for Continuous Dynamic Pricing.

Pillar 1 — Season-aware comparisons: same-month YoY, rolling-3m YoY.
Pillar 2 — Secondary behavior metrics: alert on secondary features even if
            aggregate primary metric stays GREEN.
Pillar 3 — Cohort-level PSI: per-segment drift detection so tail-risk flips
            are not masked by the full-population aggregate.

Built from the user's thesis research on telematics UBI in emerging markets.
Designed to port cleanly to health, life, and auto pricing.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Thresholds (industry standard, thesis-validated)
# ---------------------------------------------------------------------------
THRESHOLD_GREEN = 0.10
THRESHOLD_AMBER = 0.25
THRESHOLD_RED = 0.25


def _psi_status(score: float) -> str:
    if score < THRESHOLD_GREEN:
        return "green"
    if score < THRESHOLD_AMBER:
        return "amber"
    return "red"


# ---------------------------------------------------------------------------
# Low-level PSI calculation (numpy, no pandas dependency)
# ---------------------------------------------------------------------------
def calculate_psi(
    reference_bins: list[float],
    reference_proportions: list[float],
    current_values: list[float],
    epsilon: float = 1e-6,
) -> float:
    """
    Population Stability Index on a single variable.

    PSI = Σ (A_i - E_i) * ln(A_i / E_i)
    """
    if len(current_values) < 2:
        return 0.0

    bins = reference_bins
    expected = np.array(reference_proportions, dtype=float)
    n_bins = len(expected)

    values = np.array(current_values, dtype=float)
    # np.digitize with right=False: values on bin edge go to left bin
    bin_indices = np.digitize(values, bins[1:-1], right=False)
    counts = np.bincount(bin_indices, minlength=n_bins)[:n_bins]
    actual = counts.astype(float) / max(len(values), 1)

    actual = np.clip(actual, epsilon, 1.0)
    expected = np.clip(expected, epsilon, 1.0)

    psi = float(np.sum((actual - expected) * np.log(actual / expected)))
    return round(max(psi, 0.0), 6)


def build_reference_distribution(
    values: list[float], n_bins: int = 8
) -> dict[str, Any]:
    """Compute equal-frequency bins and proportions from a reference sample."""
    arr = np.array(values, dtype=float)
    if len(arr) < n_bins:
        n_bins = max(2, len(arr))
    # Use percentiles for bins so each bin has roughly equal expected proportion
    quantiles = np.linspace(0, 100, n_bins + 1)
    bins = [float(np.percentile(arr, q)) for q in quantiles]
    # Ensure unique, monotonic bins
    bins = sorted(list(set(bins)))
    if len(bins) < 3:
        # Fallback to min/max with mid
        mn, mx = float(arr.min()), float(arr.max())
        bins = [mn, (mn + mx) / 2, mx]
    # Recompute proportions based on these bins
    bin_indices = np.digitize(arr, bins[1:-1], right=False)
    counts = np.bincount(bin_indices, minlength=len(bins) - 1)
    props = (counts / counts.sum()).tolist()
    return {"bins": bins, "proportions": props}


# ---------------------------------------------------------------------------
# Configuration & Report Models
# ---------------------------------------------------------------------------
@dataclass
class MonitorConfig:
    """Configuration for a full monitoring report."""

    primary_metric: str
    secondary_metrics: list[str] = field(default_factory=list)
    segment_columns: list[str] = field(default_factory=list)
    season_column: str | None = None
    seasonal_strategy: str = "same_month_yoy"  # or "rolling_3m_yoy"
    n_bins: int = 8
    thresholds: dict[str, float] = field(default_factory=lambda: {
        "green": THRESHOLD_GREEN,
        "amber": THRESHOLD_AMBER,
        "red": THRESHOLD_RED,
    })


@dataclass
class MetricPSIResult:
    metric: str
    psi: float
    status: str
    n_samples: int
    reference_n: int | None = None


@dataclass
class CohortPSIResult:
    segment_column: str
    segment_value: str
    metric: str
    psi: float
    status: str
    n_samples: int


@dataclass
class SeasonalPSIResult:
    season_window: str
    metric: str
    psi: float
    status: str
    n_reference: int
    n_current: int


@dataclass
class MonitoringReport:
    generated_at: str
    primary: MetricPSIResult
    secondary: list[MetricPSIResult]
    cohorts: list[CohortPSIResult]
    seasonal: SeasonalPSIResult | None
    overall_status: str  # worst of primary + secondary + cohorts
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "primary": {
                "metric": self.primary.metric,
                "psi": self.primary.psi,
                "status": self.primary.status,
                "n_samples": self.primary.n_samples,
            },
            "secondary": [
                {
                    "metric": m.metric,
                    "psi": m.psi,
                    "status": m.status,
                    "n_samples": m.n_samples,
                }
                for m in self.secondary
            ],
            "cohorts": [
                {
                    "segment_column": c.segment_column,
                    "segment_value": c.segment_value,
                    "metric": c.metric,
                    "psi": c.psi,
                    "status": c.status,
                    "n_samples": c.n_samples,
                }
                for c in self.cohorts
            ],
            "seasonal": (
                {
                    "season_window": self.seasonal.season_window,
                    "metric": self.seasonal.metric,
                    "psi": self.seasonal.psi,
                    "status": self.seasonal.status,
                    "n_reference": self.seasonal.n_reference,
                    "n_current": self.seasonal.n_current,
                }
                if self.seasonal else None
            ),
            "overall_status": self.overall_status,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Advanced Monitor
# ---------------------------------------------------------------------------
class AdvancedMonitor:
    """
    Unified 3-pillar PSI monitor.

    reference_distributions format:
    {
      "mortality_multiplier": {"bins": [...], "proportions": [...]},
      "health_score": {"bins": [...], "proportions": [...]},
      ...
    }
    """

    def __init__(
        self,
        reference_distributions: dict[str, dict[str, Any]],
        thresholds: dict[str, float] | None = None,
    ):
        self.ref = reference_distributions
        self.thresholds = thresholds or {
            "green": THRESHOLD_GREEN,
            "amber": THRESHOLD_AMBER,
            "red": THRESHOLD_RED,
        }

    # -- Pillar 2: Multi-metric PSI -----------------------------------------
    def multi_metric_psi(
        self,
        current_data: dict[str, list[float]],
        metrics: list[str] | None = None,
    ) -> dict[str, MetricPSIResult]:
        """
        Compute PSI for each metric in `metrics` against the reference.
        `current_data` is a dict mapping metric_name -> list of values.
        """
        if metrics is None:
            metrics = list(self.ref.keys())

        results: dict[str, MetricPSIResult] = {}
        for metric in metrics:
            ref = self.ref.get(metric)
            if ref is None:
                results[metric] = MetricPSIResult(
                    metric=metric, psi=0.0, status="green",
                    n_samples=0, reference_n=0,
                )
                continue
            vals = current_data.get(metric, [])
            psi = calculate_psi(ref["bins"], ref["proportions"], vals)
            results[metric] = MetricPSIResult(
                metric=metric,
                psi=psi,
                status=_psi_status(psi),
                n_samples=len(vals),
                reference_n=None,
            )
        return results

    # -- Pillar 3: Cohort-level PSI -----------------------------------------
    def cohort_psi(
        self,
        current_data: dict[str, list[float]],
        segment_values: list[str],
        segment_metric: str,
        primary_metric: str,
    ) -> list[CohortPSIResult]:
        """
        Compute PSI per cohort segment.

        Args:
            current_data: dict with keys including `primary_metric` and
                          `segment_metric` (the column used for grouping).
            segment_values: unique values of the segment column to evaluate.
            segment_metric: name of the segment column in current_data.
            primary_metric: the metric to compute PSI on.
        """
        ref = self.ref.get(primary_metric)
        if ref is None:
            return []

        segments = current_data.get(segment_metric, [])
        values = current_data.get(primary_metric, [])
        if len(segments) != len(values):
            return []

        results: list[CohortPSIResult] = []
        for seg_val in segment_values:
            seg_vals = [v for s, v in zip(segments, values) if str(s) == str(seg_val)]
            if len(seg_vals) < 2:
                continue
            psi = calculate_psi(ref["bins"], ref["proportions"], seg_vals)
            results.append(
                CohortPSIResult(
                    segment_column=segment_metric,
                    segment_value=str(seg_val),
                    metric=primary_metric,
                    psi=psi,
                    status=_psi_status(psi),
                    n_samples=len(seg_vals),
                )
            )
        return results

    # -- Pillar 1: Season-aware PSI -----------------------------------------
    def seasonal_psi(
        self,
        reference_data: dict[str, list[float]],
        current_data: dict[str, list[float]],
        season_col: str,
        target_season: str,
        strategy: str = "same_month_yoy",
        metric: str | None = None,
    ) -> SeasonalPSIResult | None:
        """
        Compare current data for `target_season` against reference data
        for the matching season window.

        Strategies:
          - "same_month_yoy": exact season match (e.g., "rainy" vs "rainy")
          - "rolling_3m_yoy": not used here but reserved for month-level data
        """
        if metric is None:
            metric = list(self.ref.keys())[0]
        ref = self.ref.get(metric)
        if ref is None:
            return None

        ref_seasons = reference_data.get(season_col, [])
        ref_values = reference_data.get(metric, [])
        cur_seasons = current_data.get(season_col, [])
        cur_values = current_data.get(metric, [])

        if len(ref_seasons) != len(ref_values) or len(cur_seasons) != len(cur_values):
            return None

        ref_match = [v for s, v in zip(ref_seasons, ref_values) if str(s) == str(target_season)]
        cur_match = [v for s, v in zip(cur_seasons, cur_values) if str(s) == str(target_season)]

        if len(ref_match) < 2 or len(cur_match) < 2:
            return None

        # Build a reference distribution from the reference season subset
        ref_dist = build_reference_distribution(ref_match, n_bins=self._n_bins_for_metric(metric))
        psi = calculate_psi(ref_dist["bins"], ref_dist["proportions"], cur_match)

        return SeasonalPSIResult(
            season_window=f"{strategy}:{target_season}",
            metric=metric,
            psi=psi,
            status=_psi_status(psi),
            n_reference=len(ref_match),
            n_current=len(cur_match),
        )

    # -- Full Report --------------------------------------------------------
    def full_report(
        self,
        current_data: dict[str, list[float]],
        reference_data: dict[str, list[float]] | None = None,
        config: MonitorConfig | None = None,
    ) -> MonitoringReport:
        """
        Run all three pillars and return a unified report.

        Args:
            current_data: dict of metric_name -> list of values.
            reference_data: optional dict for seasonal comparisons.
            config: what to monitor.
        """
        if config is None:
            config = MonitorConfig(primary_metric=list(self.ref.keys())[0])

        notes: list[str] = []

        # Pillar 2: multi-metric
        all_metrics = [config.primary_metric] + config.secondary_metrics
        mm = self.multi_metric_psi(current_data, metrics=all_metrics)
        primary = mm.get(config.primary_metric, MetricPSIResult(
            metric=config.primary_metric, psi=0.0, status="green", n_samples=0
        ))
        secondary = [mm[m] for m in config.secondary_metrics if m in mm]

        # Pillar 3: cohorts
        cohorts: list[CohortPSIResult] = []
        for seg_col in config.segment_columns:
            seg_values = sorted(set(str(v) for v in current_data.get(seg_col, [])))
            cohorts.extend(
                self.cohort_psi(current_data, seg_values, seg_col, config.primary_metric)
            )

        # Pillar 1: seasonal
        seasonal = None
        if config.season_column and reference_data is not None:
            # Evaluate each unique season in current data
            cur_seasons = set(str(s) for s in current_data.get(config.season_column, []))
            for season in sorted(cur_seasons):
                res = self.seasonal_psi(
                    reference_data, current_data,
                    config.season_column, season,
                    strategy=config.seasonal_strategy,
                    metric=config.primary_metric,
                )
                if res:
                    seasonal = res
                    break  # report first detected season; caller can iterate if needed

        # Overall status = worst across all
        statuses = [primary.status] + [s.status for s in secondary] + [c.status for c in cohorts]
        if seasonal:
            statuses.append(seasonal.status)

        overall = "green"
        if "red" in statuses:
            overall = "red"
        elif "amber" in statuses:
            overall = "amber"

        if overall == "red":
            notes.append("RED alert: at least one metric or cohort crossed the drift threshold.")
        if overall == "amber":
            notes.append("AMBER warning: elevated drift detected — monitor closely.")

        return MonitoringReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            primary=primary,
            secondary=secondary,
            cohorts=cohorts,
            seasonal=seasonal,
            overall_status=overall,
            notes=notes,
        )

    def _n_bins_for_metric(self, metric: str) -> int:
        ref = self.ref.get(metric)
        if ref:
            return len(ref.get("proportions", [8]))
        return 8

    # -- Serialization helpers ----------------------------------------------
    def save_reference(self, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.ref, f, indent=2)

    @classmethod
    def load_reference(cls, path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
