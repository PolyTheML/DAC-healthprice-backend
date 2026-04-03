"""
Auto Pricing Lab v2 — Claims Aggregation (Step 6a)

Aggregates raw claim events into per-segment loss ratios.
A "segment" is a (vehicle_type, region) pair.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional
import math


@dataclass
class ClaimEvent:
    policy_id: str
    vehicle_type: str
    region: str
    written_premium: float      # VND
    claim_amount: float         # VND (0 if no claim)
    has_claim: bool


@dataclass
class SegmentAggregate:
    segment: str                # e.g. "motorcycle_phnom_penh"
    vehicle_type: str
    region: str
    policy_count: int = 0
    total_written_premium: float = 0.0
    total_claims: float = 0.0
    claim_count: int = 0

    @property
    def loss_ratio(self) -> float:
        if self.total_written_premium == 0:
            return 0.0
        return self.total_claims / self.total_written_premium

    @property
    def claim_frequency(self) -> float:
        if self.policy_count == 0:
            return 0.0
        return self.claim_count / self.policy_count

    @property
    def avg_severity(self) -> float:
        if self.claim_count == 0:
            return 0.0
        return self.total_claims / self.claim_count


def aggregate_claims(events: list[ClaimEvent]) -> dict[str, SegmentAggregate]:
    """Aggregate a list of claim events into per-segment metrics."""
    segments: dict[str, SegmentAggregate] = {}

    for ev in events:
        key = f"{ev.vehicle_type}_{ev.region}"
        if key not in segments:
            segments[key] = SegmentAggregate(
                segment=key,
                vehicle_type=ev.vehicle_type,
                region=ev.region,
            )
        seg = segments[key]
        seg.policy_count += 1
        seg.total_written_premium += ev.written_premium
        if ev.has_claim:
            seg.claim_count += 1
            seg.total_claims += ev.claim_amount

    return segments
