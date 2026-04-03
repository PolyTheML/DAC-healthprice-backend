"""
Auto Pricing Lab v2 — Drift Detection & Monitoring (Step 7)

Watches per-segment loss ratios and conversion rates.
Raises alerts when metrics deviate beyond configured thresholds.
Recommends action: log / review coefficients / trigger retraining.

Thresholds (from shared constants):
  Warning:  loss ratio deviation > 15%
  Critical: loss ratio deviation > 25%
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.feedback.metrics import LossRatioMetric

# Thresholds (mirror frontend constants.ts DRIFT_THRESHOLDS)
LOSS_RATIO_WARNING_PCT  = 15.0   # % deviation from expected
LOSS_RATIO_CRITICAL_PCT = 25.0
MIN_POLICIES_FOR_CREDIBILITY = 30  # don't alert on tiny segments


@dataclass
class DriftAlert:
    severity: str           # "info" | "warning" | "critical"
    segment: str
    metric: str             # "loss_ratio"
    expected: float
    actual: float
    deviation_percent: float
    message: str
    recommended_action: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MonitoringReport:
    overall_loss_ratio: float
    expected_loss_ratio: float
    overall_deviation_pct: float
    segments_monitored: int
    segments_at_warning: int
    segments_at_critical: int
    alerts: list[DriftAlert]
    requires_retraining: bool
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["alerts"] = [a.to_dict() for a in self.alerts]
        return d


def run_monitoring(metrics: list[LossRatioMetric]) -> MonitoringReport:
    """
    Evaluate all segment metrics and produce a monitoring report with drift alerts.
    """
    alerts: list[DriftAlert] = []
    warning_count = 0
    critical_count = 0

    credible = [m for m in metrics if m.policy_count >= MIN_POLICIES_FOR_CREDIBILITY]

    for m in credible:
        abs_dev = abs(m.deviation_percent)

        if abs_dev >= LOSS_RATIO_CRITICAL_PCT:
            severity = "critical"
            critical_count += 1
            action = (
                "Trigger model retraining. Review coefficients for this segment. "
                "Consider temporary loading adjustment pending retraining."
            )
        elif abs_dev >= LOSS_RATIO_WARNING_PCT:
            severity = "warning"
            warning_count += 1
            action = (
                "Monitor closely. If trend continues for 2+ periods, "
                "review loading factor and consider coefficient adjustment."
            )
        else:
            continue  # within tolerance, no alert

        direction = "over-pricing" if m.deviation < 0 else "under-pricing"
        alerts.append(DriftAlert(
            severity=severity,
            segment=m.segment,
            metric="loss_ratio",
            expected=m.expected_loss_ratio,
            actual=m.actual_loss_ratio,
            deviation_percent=m.deviation_percent,
            message=(
                f"{m.segment}: actual LR {m.actual_loss_ratio:.1%} vs expected "
                f"{m.expected_loss_ratio:.1%} ({m.deviation_percent:+.1f}%) — {direction}"
            ),
            recommended_action=action,
        ))

    # Portfolio-level stats
    if credible:
        total_premium = sum(
            m.actual_loss_ratio * 1  # normalised — we don't have raw premium here
            for m in credible
        )
        overall_lr = float(sum(m.actual_loss_ratio for m in credible) / len(credible))
        overall_exp = float(sum(m.expected_loss_ratio for m in credible) / len(credible))
    else:
        overall_lr = 0.0
        overall_exp = 0.0

    overall_dev_pct = ((overall_lr - overall_exp) / overall_exp * 100) if overall_exp else 0.0
    requires_retraining = critical_count > 0 or (
        warning_count >= 3 and overall_dev_pct > LOSS_RATIO_WARNING_PCT
    )

    return MonitoringReport(
        overall_loss_ratio=round(overall_lr, 4),
        expected_loss_ratio=round(overall_exp, 4),
        overall_deviation_pct=round(overall_dev_pct, 2),
        segments_monitored=len(credible),
        segments_at_warning=warning_count,
        segments_at_critical=critical_count,
        alerts=sorted(alerts, key=lambda a: ("critical", "warning", "info").index(a.severity)),
        requires_retraining=requires_retraining,
    )
