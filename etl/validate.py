"""
Schema validation and outlier detection for incoming quote rows.

Validation is pragmatic: we don't reject rows with missing optional fields,
only rows where a required field is absent or type-incorrect. Outlier
detection is statistical and non-destructive — outliers are *quarantined*
(flagged), not dropped, so the audit trail retains them.
"""

from __future__ import annotations

import statistics
from typing import Any

from etl.config import ETLConfig

REQUIRED_FIELDS = ("id", "created_at", "mortality_ratio", "total_annual_premium")


class SchemaValidator:
    def __init__(self, config: ETLConfig):
        self._config = config

    def validate_quote(self, record: dict[str, Any]) -> tuple[bool, str | None]:
        for field in REQUIRED_FIELDS:
            if field not in record or record[field] is None:
                return False, f"missing required field: {field}"

        try:
            mr = float(record["mortality_ratio"])
            premium = float(record["total_annual_premium"])
        except (TypeError, ValueError) as exc:
            return False, f"non-numeric numeric field: {exc}"

        if mr <= 0:
            return False, f"mortality_ratio must be positive, got {mr}"
        if premium <= 0:
            return False, f"total_annual_premium must be positive, got {premium}"

        profile = record.get("applicant_profile") or {}
        if isinstance(profile, dict):
            age = profile.get("age")
            if age is not None:
                try:
                    age_val = float(age)
                    if not (self._config.min_age <= age_val <= self._config.max_age):
                        return False, f"age out of range: {age_val}"
                except (TypeError, ValueError):
                    return False, f"age is not numeric: {age!r}"
            bmi = profile.get("bmi")
            if bmi is not None:
                try:
                    bmi_val = float(bmi)
                    if not (self._config.min_bmi <= bmi_val <= self._config.max_bmi):
                        return False, f"bmi out of range: {bmi_val}"
                except (TypeError, ValueError):
                    return False, f"bmi is not numeric: {bmi!r}"

        return True, None


class OutlierDetector:
    """Flag records whose premium is an order of magnitude above the batch median."""

    def __init__(self, config: ETLConfig):
        self._config = config

    def detect_outliers(self, records: list[dict[str, Any]]) -> set[int]:
        """Return set of indices (into `records`) flagged as outliers."""
        premiums: list[float] = []
        for rec in records:
            try:
                premiums.append(float(rec["total_annual_premium"]))
            except (KeyError, TypeError, ValueError):
                premiums.append(0.0)

        finite_positive = [p for p in premiums if p > 0]
        if len(finite_positive) < 5:
            return set()

        median = statistics.median(finite_positive)
        threshold = median * self._config.outlier_premium_multiplier
        return {i for i, p in enumerate(premiums) if p > threshold}
