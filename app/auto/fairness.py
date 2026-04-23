"""Fairness Audit for Auto Continuous Underwriting.

Computes Disparate Impact Ratio (DIR) across protected groups
using the auto_policies table.  DIR must remain >= 0.80 per
Prakas 093 / TCF principles.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class GroupMetric(BaseModel):
    group_name: str
    n_policies: int
    mean_multiplier: float


class FairnessAuditResponse(BaseModel):
    overall_dir: float
    age_dir: float
    region_dir: float
    threshold: float = 0.80
    status: str  # "pass" | "warning" | "fail"
    age_groups: list[GroupMetric]
    region_groups: list[GroupMetric]
    message: str


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def compute_fairness_audit(rows: list[dict]) -> FairnessAuditResponse:
    """Compute DIR from raw auto_policies rows.

    Each row is a dict-like with keys: driver_age, region, deviation_multiplier.
    """
    if not rows:
        return FairnessAuditResponse(
            overall_dir=1.0,
            age_dir=1.0,
            region_dir=1.0,
            threshold=0.80,
            status="pass",
            age_groups=[],
            region_groups=[],
            message="No auto policies found — audit skipped.",
        )

    # ── Age groups ────────────────────────────────────────────────────────────
    young = [r["deviation_multiplier"] for r in rows if r["driver_age"] < 25]
    experienced = [r["deviation_multiplier"] for r in rows if r["driver_age"] >= 25]

    age_groups = []
    if young:
        age_groups.append(GroupMetric(group_name="Young (<25)", n_policies=len(young), mean_multiplier=_mean(young)))
    if experienced:
        age_groups.append(GroupMetric(group_name="Experienced (25+)", n_policies=len(experienced), mean_multiplier=_mean(experienced)))

    age_dir = 1.0
    if young and experienced:
        age_dir = _mean(young) / _mean(experienced)

    # ── Region groups ─────────────────────────────────────────────────────────
    urban_regions = {"phnom_penh", "ho_chi_minh", "hanoi", "da_nang", "can_tho", "hai_phong", "sihanoukville"}
    rural = [r["deviation_multiplier"] for r in rows if r["region"] not in urban_regions]
    urban = [r["deviation_multiplier"] for r in rows if r["region"] in urban_regions]

    region_groups = []
    if rural:
        region_groups.append(GroupMetric(group_name="Rural / Semi-urban", n_policies=len(rural), mean_multiplier=_mean(rural)))
    if urban:
        region_groups.append(GroupMetric(group_name="Urban", n_policies=len(urban), mean_multiplier=_mean(urban)))

    region_dir = 1.0
    if rural and urban:
        region_dir = _mean(rural) / _mean(urban)

    # ── Overall DIR (all policies vs reference = mean of all) ─────────────────
    all_mult = [r["deviation_multiplier"] for r in rows]
    overall_mean = _mean(all_mult)
    # Use lowest-mean group as protected for overall metric
    all_group_means = []
    if young:
        all_group_means.append(("young", _mean(young)))
    if experienced:
        all_group_means.append(("experienced", _mean(experienced)))
    if rural:
        all_group_means.append(("rural", _mean(rural)))
    if urban:
        all_group_means.append(("urban", _mean(urban)))

    if all_group_means:
        min_mean = min(m for _, m in all_group_means)
        overall_dir = min_mean / overall_mean if overall_mean > 0 else 1.0
    else:
        overall_dir = 1.0

    # ── Status ────────────────────────────────────────────────────────────────
    min_dir = min(overall_dir, age_dir, region_dir)
    if min_dir >= 0.80:
        status = "pass"
        message = f"All DIR metrics above 0.80 threshold (min={min_dir:.3f})."
    elif min_dir >= 0.65:
        status = "warning"
        message = f"DIR warning: min ratio = {min_dir:.3f} (threshold 0.80). Review age/region loading."
    else:
        status = "fail"
        message = f"DIR hard fail: min ratio = {min_dir:.3f} (threshold 0.80). Immediate actuarial review required."

    return FairnessAuditResponse(
        overall_dir=round(overall_dir, 4),
        age_dir=round(age_dir, 4),
        region_dir=round(region_dir, 4),
        threshold=0.80,
        status=status,
        age_groups=age_groups,
        region_groups=region_groups,
        message=message,
    )
