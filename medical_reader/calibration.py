"""
Recalibration engine: distribution monitoring + candidate multiplier suggestions.

Important honesty about what this engine can and cannot do:

- We have **no real claims outcomes** yet. Every `mortality_ratio` on a quote
  row was computed by the *current* assumptions themselves, so using it to
  "recalibrate" those same multipliers is circular. We mitigate this two ways:
    1. Multiplier proposals are heavily weight-averaged toward the current
       value (stability weighting), capped by ``max_change_pct``.
    2. Proposals only cover occupational & healthcare-tier multipliers.
       Endemic-disease multipliers require real mortality/infection data
       per province — we monitor their distribution but never propose a
       change from quote data alone.
- The fairness check (disparate impact on approval rates) is outcome-agnostic
  and therefore trustworthy even without claims.
- Any candidate version document records these caveats inline in
  ``data_provenance.notes`` so downstream auditors can see the weak-signal
  caveat next to the numbers.

When a candidate version is created, it auto-promotes iff fairness passes
(per user decision #5). If fairness fails the candidate is written but left
as ``status=candidate`` in the manifest for manual review.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from analytics.monitor import REFERENCE_DISTRIBUTION, calculate_psi
from etl.config import ETLConfig, get_config
from etl.storage import LocalDatasetWriter
from medical_reader.pricing import versioning

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning — conservative defaults. The engine will not override cfg-derived
# guardrails; these constants set what is *separately* enforced by the engine
# on top of the ETL-level caps.
# ---------------------------------------------------------------------------
MIN_COHORT_N = 5                      # skip cohorts smaller than this
STABILITY_WEIGHT = 0.9                # proposed = 0.9 * current + 0.1 * empirical
ABSOLUTE_MULTIPLIER_BOUNDS = (0.75, 1.50)
FAIRNESS_DI_PASS = 0.80               # Prakas 093: pass threshold
FAIRNESS_DI_WARN = 0.90               # cosmetic warn band

OCCUPATION_BASELINE = "office_desk"
HEALTHCARE_BASELINE = "tier_b"


# ---------------------------------------------------------------------------
# Report models
# ---------------------------------------------------------------------------

@dataclass
class CohortStats:
    cohort: str
    cohort_type: str                  # "occupation" | "province" | "healthcare_tier" | "gender"
    n: int
    approvals: int
    declines: int
    manual_reviews: int
    approval_rate: float
    manual_override_rate: float
    mean_mortality_ratio: float
    current_multiplier: float | None  # None for province (we don't propose changes there)
    proposed_multiplier: float | None
    change_pct: float | None
    notes: str = ""


@dataclass
class FairnessReport:
    disparate_impact_ratio: float
    by_gender: dict[str, float] = field(default_factory=dict)
    by_occupation: dict[str, float] = field(default_factory=dict)
    by_province: dict[str, float] = field(default_factory=dict)
    status: str = "pass"              # "pass" | "warn" | "fail"
    flags: list[str] = field(default_factory=list)


@dataclass
class CalibrationReport:
    status: str                       # "candidate_created" | "candidate_created_fairness_fail"
                                      # | "no_change_needed" | "insufficient_data" | "error"
    trigger: str                      # "manual" | "scheduled" | "drift_detected"
    analyzed_at: str
    parent_version: str
    candidate_version: str | None
    auto_promoted: bool
    days_back: int
    total_valid_quotes: int
    psi: dict[str, Any]               # {"score": float, "status": str}
    cohort_stats: list[CohortStats]
    fairness: FairnessReport | None
    proposed_changes: dict[str, dict[str, float]]   # {"cambodia_occupational": {"motorbike_courier": 1.38}}
    reasoning: list[str]
    caveats: list[str]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        def _convert(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _convert(v) for k, v in asdict(obj).items()}
            if isinstance(obj, list):
                return [_convert(x) for x in obj]
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            return obj
        return _convert(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract(row: dict[str, Any], group: str, key: str, default=None):
    container = row.get(group) or {}
    if isinstance(container, dict):
        return container.get(key, default)
    return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_version_id(parent_id: str, *, existing: set[str]) -> str:
    """Bump minor from parent (e.g. v3.0 → v3.1) and stamp today's date.

    If v3.1-cambodia-<today>.json already exists, keep bumping minor.
    """
    # parent_id example: "v3.0-cambodia-2026-04-14"
    head, *_rest = parent_id.split("-", 1)  # "v3.0"
    major_minor = head.lstrip("v")
    major_s, minor_s = major_minor.split(".")
    major = int(major_s)
    minor = int(minor_s) + 1
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    while True:
        candidate = f"v{major}.{minor}-cambodia-{today}"
        if candidate not in existing:
            return candidate
        minor += 1


def _default(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CalibrationEngine:
    def __init__(
        self,
        config: ETLConfig | None = None,
        *,
        writer: LocalDatasetWriter | None = None,
    ):
        self._config = config or get_config()
        self._writer = writer or LocalDatasetWriter(self._config)

    # ----- Public API -----

    def run_analysis(
        self,
        *,
        trigger: str = "manual",
        days_back: int = 90,
    ) -> CalibrationReport:
        """Compute cohort stats + fairness + proposed deltas without writing a version."""
        quotes = self._writer.load_valid_quotes(days_back=days_back)
        parent_version = versioning.get_active_version_id()
        parent_payload = versioning.load_version_raw(parent_version)

        caveats = [
            "No real claims outcomes available — multiplier proposals are "
            "distribution-derived and stability-weighted. Treat as monitoring "
            "signals, not empirical risk lifts.",
            "Endemic-disease multipliers are monitored only; changes require "
            "per-province claim data and are not proposed automatically.",
        ]

        if len(quotes) < self._config.recalibration_min_quotes:
            return CalibrationReport(
                status="insufficient_data",
                trigger=trigger,
                analyzed_at=_now_iso(),
                parent_version=parent_version,
                candidate_version=None,
                auto_promoted=False,
                days_back=days_back,
                total_valid_quotes=len(quotes),
                psi={"score": 0.0, "status": "stable"},
                cohort_stats=[],
                fairness=None,
                proposed_changes={},
                reasoning=[
                    f"Need at least {self._config.recalibration_min_quotes} valid "
                    f"quotes; have {len(quotes)}."
                ],
                caveats=caveats,
            )

        mr_values = [_default(q.get("mortality_ratio"), 0.0) for q in quotes]
        mr_values = [v for v in mr_values if v > 0]
        psi = 0.0
        if len(mr_values) >= 5:
            psi = calculate_psi(REFERENCE_DISTRIBUTION["mortality_ratio"], mr_values)
        psi_status = "stable" if psi < 0.10 else ("warning" if psi < 0.25 else "drift")

        occ_cohorts = self._cohort_stats(
            quotes,
            cohort_type="occupation",
            key_extractor=lambda q: _extract(q, "extracted_from", "occupation"),
            current_multipliers=parent_payload["parameters"]["cambodia_occupational"],
            baseline_cohort=OCCUPATION_BASELINE,
            propose_changes=True,
        )
        tier_cohorts = self._cohort_stats(
            quotes,
            cohort_type="healthcare_tier",
            key_extractor=lambda q: _extract(q, "extracted_from", "healthcare_tier"),
            current_multipliers=parent_payload["parameters"]["cambodia_healthcare_tier"],
            baseline_cohort=HEALTHCARE_BASELINE,
            propose_changes=True,
        )
        province_cohorts = self._cohort_stats(
            quotes,
            cohort_type="province",
            key_extractor=lambda q: _extract(q, "extracted_from", "province"),
            current_multipliers=parent_payload["parameters"]["cambodia_endemic"],
            baseline_cohort="phnom_penh",
            propose_changes=False,   # endemic: monitor only
        )
        gender_cohorts = self._cohort_stats(
            quotes,
            cohort_type="gender",
            key_extractor=lambda q: _extract(q, "applicant_profile", "gender"),
            current_multipliers={},
            baseline_cohort=None,
            propose_changes=False,
        )

        proposed_changes = self._collect_proposed(occ_cohorts, tier_cohorts)
        reasoning = self._reasoning_lines(proposed_changes, occ_cohorts, tier_cohorts)

        fairness = self._fairness_report(occ_cohorts, province_cohorts, gender_cohorts)

        return CalibrationReport(
            status="candidate_ready" if proposed_changes else "no_change_needed",
            trigger=trigger,
            analyzed_at=_now_iso(),
            parent_version=parent_version,
            candidate_version=None,
            auto_promoted=False,
            days_back=days_back,
            total_valid_quotes=len(quotes),
            psi={"score": round(psi, 4), "status": psi_status},
            cohort_stats=occ_cohorts + tier_cohorts + province_cohorts + gender_cohorts,
            fairness=fairness,
            proposed_changes=proposed_changes,
            reasoning=reasoning,
            caveats=caveats,
        )

    def propose_candidate_version(
        self,
        *,
        trigger: str = "manual",
        days_back: int = 90,
    ) -> CalibrationReport:
        """Runs analysis, writes a new version JSON if changes warranted, auto-promotes on fairness pass."""
        report = self.run_analysis(trigger=trigger, days_back=days_back)

        if report.status == "insufficient_data" or not report.proposed_changes:
            return report
        if report.fairness is None:
            return report

        parent_version = report.parent_version
        parent_payload = versioning.load_version_raw(parent_version)

        existing = {entry["version"] for entry in versioning.read_manifest().get("versions", [])}
        new_id = _next_version_id(parent_version, existing=existing)

        new_payload = self._build_candidate_payload(
            parent_payload=parent_payload,
            proposed_changes=report.proposed_changes,
            new_version_id=new_id,
            report=report,
        )

        fairness_ok = report.fairness.status == "pass"
        versioning.register_candidate_version(
            version_id=new_id,
            payload=new_payload,
            reason=f"Recalibration ({trigger}): {len(report.proposed_changes)} multiplier group(s) updated",
            parent_version=parent_version,
            auto_promote=fairness_ok,
        )

        report.candidate_version = new_id
        report.auto_promoted = fairness_ok
        report.status = (
            "candidate_created" if fairness_ok else "candidate_created_fairness_fail"
        )
        if not fairness_ok:
            report.reasoning.append(
                f"Fairness check did not pass (DI={report.fairness.disparate_impact_ratio:.2f}); "
                f"candidate {new_id} written but NOT auto-promoted."
            )
        else:
            report.reasoning.append(
                f"Fairness passed (DI={report.fairness.disparate_impact_ratio:.2f}); "
                f"{new_id} auto-promoted to active."
            )
        return report

    # ----- Internals -----

    def _cohort_stats(
        self,
        quotes: list[dict[str, Any]],
        *,
        cohort_type: str,
        key_extractor,
        current_multipliers: dict[str, float],
        baseline_cohort: str | None,
        propose_changes: bool,
    ) -> list[CohortStats]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for q in quotes:
            raw = key_extractor(q)
            if raw is None or raw == "":
                continue
            key = str(raw).strip().lower().replace(" ", "_")
            groups.setdefault(key, []).append(q)

        baseline_mean_mr: float | None = None
        if baseline_cohort and baseline_cohort in groups and len(groups[baseline_cohort]) >= MIN_COHORT_N:
            baseline_mean_mr = statistics.mean(
                _default(q.get("mortality_ratio"), 0.0) for q in groups[baseline_cohort]
            )

        results: list[CohortStats] = []
        for cohort, items in sorted(groups.items()):
            n = len(items)
            approvals = sum(1 for q in items if q.get("underwriting_status") == "approved")
            declines = sum(1 for q in items if q.get("underwriting_status") == "declined")
            manual_reviews = sum(1 for q in items if q.get("underwriting_status") == "manual_review")
            override_n = sum(1 for q in items if q.get("manual_override"))
            approval_rate = round(approvals / n, 4) if n else 0.0
            override_rate = round(override_n / n, 4) if n else 0.0
            mean_mr = round(
                statistics.mean(_default(q.get("mortality_ratio"), 0.0) for q in items), 4
            ) if n else 0.0

            current = float(current_multipliers.get(cohort)) if cohort in current_multipliers else None
            proposed = None
            change_pct = None
            notes = ""

            if (
                propose_changes
                and current is not None
                and baseline_mean_mr
                and baseline_mean_mr > 0
                and n >= MIN_COHORT_N
            ):
                empirical = mean_mr / baseline_mean_mr
                blended = STABILITY_WEIGHT * current + (1 - STABILITY_WEIGHT) * empirical

                max_pct = self._config.recalibration_max_change_pct / 100.0
                upper = current * (1 + max_pct)
                lower = current * (1 - max_pct)
                blended = max(lower, min(upper, blended))
                blended = max(ABSOLUTE_MULTIPLIER_BOUNDS[0], min(ABSOLUTE_MULTIPLIER_BOUNDS[1], blended))

                proposed_val = round(blended, 4)
                change_pct_val = round((proposed_val - current) / current * 100, 2) if current else 0.0

                if abs(change_pct_val) >= 0.5:
                    proposed = proposed_val
                    change_pct = change_pct_val
                    notes = (
                        f"empirical {empirical:.3f}× baseline; stability-weighted → {proposed_val}"
                    )
                else:
                    notes = "within 0.5% of current — no change proposed"
            elif propose_changes and n < MIN_COHORT_N:
                notes = f"insufficient samples (n={n} < {MIN_COHORT_N}) — monitoring only"

            results.append(
                CohortStats(
                    cohort=cohort,
                    cohort_type=cohort_type,
                    n=n,
                    approvals=approvals,
                    declines=declines,
                    manual_reviews=manual_reviews,
                    approval_rate=approval_rate,
                    manual_override_rate=override_rate,
                    mean_mortality_ratio=mean_mr,
                    current_multiplier=current,
                    proposed_multiplier=proposed,
                    change_pct=change_pct,
                    notes=notes,
                )
            )
        return results

    def _collect_proposed(self, *cohort_lists: list[CohortStats]) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for cohorts in cohort_lists:
            for c in cohorts:
                if c.proposed_multiplier is None:
                    continue
                group_key = {
                    "occupation": "cambodia_occupational",
                    "healthcare_tier": "cambodia_healthcare_tier",
                }.get(c.cohort_type)
                if group_key is None:
                    continue
                out.setdefault(group_key, {})[c.cohort] = c.proposed_multiplier
        return out

    def _reasoning_lines(
        self,
        proposed: dict[str, dict[str, float]],
        *cohort_lists: list[CohortStats],
    ) -> list[str]:
        lines: list[str] = []
        if not proposed:
            lines.append("No multiplier changes warranted — all cohorts within tolerance.")
            return lines
        for group, changes in proposed.items():
            for cohort, new_val in changes.items():
                src = next(
                    (c for cs in cohort_lists for c in cs if c.cohort == cohort and c.cohort_type + "_" in (
                        "occupation_" if group == "cambodia_occupational" else "healthcare_tier_"
                    )),
                    None,
                )
                if src and src.current_multiplier is not None:
                    lines.append(
                        f"{group}.{cohort}: {src.current_multiplier:.2f} → {new_val:.2f} "
                        f"(n={src.n}, Δ={src.change_pct:+.2f}%)"
                    )
        return lines

    def _fairness_report(
        self,
        occupation_cohorts: list[CohortStats],
        province_cohorts: list[CohortStats],
        gender_cohorts: list[CohortStats],
    ) -> FairnessReport:
        by_gender = {c.cohort: c.approval_rate for c in gender_cohorts if c.n >= MIN_COHORT_N}
        by_occupation = {c.cohort: c.approval_rate for c in occupation_cohorts if c.n >= MIN_COHORT_N}
        by_province = {c.cohort: c.approval_rate for c in province_cohorts if c.n >= MIN_COHORT_N}

        def _di(rates: dict[str, float]) -> float:
            vals = [v for v in rates.values() if v > 0]
            if not vals:
                return 1.0
            return round(min(vals) / max(vals), 4)

        ratios = [
            _di(by_gender) if by_gender else 1.0,
            _di(by_occupation) if by_occupation else 1.0,
            _di(by_province) if by_province else 1.0,
        ]
        di = min(ratios)

        flags: list[str] = []
        status = "pass"
        if di < FAIRNESS_DI_PASS:
            status = "fail"
            flags.append(
                f"Disparate impact {di:.2f} below Prakas 093 threshold {FAIRNESS_DI_PASS}"
            )
        elif di < FAIRNESS_DI_WARN:
            status = "warn"
            flags.append(f"Disparate impact {di:.2f} in monitoring band")

        return FairnessReport(
            disparate_impact_ratio=di,
            by_gender=by_gender,
            by_occupation=by_occupation,
            by_province=by_province,
            status=status,
            flags=flags,
        )

    def _build_candidate_payload(
        self,
        *,
        parent_payload: dict[str, Any],
        proposed_changes: dict[str, dict[str, float]],
        new_version_id: str,
        report: CalibrationReport,
    ) -> dict[str, Any]:
        from copy import deepcopy

        params = deepcopy(parent_payload["parameters"])
        for group_key, changes in proposed_changes.items():
            if group_key not in params:
                continue
            for cohort, new_val in changes.items():
                if cohort in params[group_key]:
                    params[group_key][cohort] = new_val

        fairness_dict: dict[str, Any] = {}
        if report.fairness is not None:
            fairness_dict = {
                "disparate_impact_ratio": report.fairness.disparate_impact_ratio,
                "status": report.fairness.status,
                "flags": report.fairness.flags,
            }

        return {
            "version": new_version_id,
            "created_at": _now_iso(),
            "parent_version": report.parent_version,
            "data_provenance": {
                "source": "local ETL dataset (data/synced/quotes.db)",
                "rows_used": report.total_valid_quotes,
                "days_window": report.days_back,
                "sync_id": None,
                "psi_score": report.psi["score"],
                "psi_status": report.psi["status"],
                "notes": (
                    "Distribution-derived proposal, stability-weighted (0.9 current + "
                    "0.1 empirical). No claims outcomes were used. See "
                    "wiki/topics/cambodia-smart-underwriting.md for model details."
                ),
            },
            "parameters": params,
            "validation": {
                "fairness_score": report.fairness.disparate_impact_ratio if report.fairness else None,
                "disparate_impact_ratio": report.fairness.disparate_impact_ratio if report.fairness else None,
                "status": report.fairness.status if report.fairness else "unknown",
                "notes": "; ".join(report.reasoning) if report.reasoning else "",
            },
        }
