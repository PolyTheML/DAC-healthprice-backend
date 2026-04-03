"""
Auto Pricing Lab v2 — Loss Ratio Tracking & Feedback Loop (Step 6b)

Computes expected vs actual loss ratios per segment.
Flags segments where experience deviates from GLM predictions.
Designed to feed into the monitoring layer (Step 7).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.COEFF_AUTO import LOADING_FACTORS

from app.feedback.claims import SegmentAggregate


@dataclass
class LossRatioMetric:
    segment: str
    vehicle_type: str
    region: str
    policy_count: int
    actual_loss_ratio: float
    expected_loss_ratio: float       # derived from GLM loading factor
    deviation: float                 # actual - expected
    deviation_percent: float         # deviation / expected × 100
    trend: str                       # "stable" | "deteriorating" | "improving"


def expected_loss_ratio(vehicle_type: str) -> float:
    """
    Expected loss ratio = 1 - loading_factor.
    E.g. motorcycle loading=0.32 → expected LR = 0.68 (insurers pay 68¢ per ₫1 premium).
    """
    load = LOADING_FACTORS.get(vehicle_type, 0.30)
    return round(1.0 - load, 4)


def compute_loss_ratio_metrics(
    segments: dict[str, SegmentAggregate],
    prior_loss_ratios: Optional[dict[str, float]] = None,
) -> list[LossRatioMetric]:
    """
    For each segment, compute actual vs expected loss ratio and trend.

    prior_loss_ratios: {segment_key: prior_actual_LR} for trend calculation.
    """
    metrics = []
    for key, seg in segments.items():
        actual_lr = seg.loss_ratio
        expected_lr = expected_loss_ratio(seg.vehicle_type)
        deviation = actual_lr - expected_lr
        deviation_pct = (deviation / expected_lr * 100) if expected_lr > 0 else 0.0

        # Trend: compare to prior period if available
        trend = "stable"
        if prior_loss_ratios and key in prior_loss_ratios:
            prior_lr = prior_loss_ratios[key]
            delta = actual_lr - prior_lr
            if delta > 0.03:
                trend = "deteriorating"
            elif delta < -0.03:
                trend = "improving"

        metrics.append(LossRatioMetric(
            segment=key,
            vehicle_type=seg.vehicle_type,
            region=seg.region,
            policy_count=seg.policy_count,
            actual_loss_ratio=round(actual_lr, 4),
            expected_loss_ratio=expected_lr,
            deviation=round(deviation, 4),
            deviation_percent=round(deviation_pct, 2),
            trend=trend,
        ))

    return sorted(metrics, key=lambda m: abs(m.deviation_percent), reverse=True)
