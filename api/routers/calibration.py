"""
API routes for /calibration endpoints — ETL sync control and
assumption version management.

Mutating endpoints (sync / promote / rollback) are gated behind an
``X-Admin-Token`` header that must match the ``ADMIN_TOKEN`` env var.
If ``ADMIN_TOKEN`` is unset, gating is disabled (dev default, matching
the rest of the API's unauthed posture).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from etl.config import get_config
from etl.pipeline import ETLPipeline
from medical_reader.calibration import CalibrationEngine
from medical_reader.pricing import versioning

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def admin_required(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        return
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="admin token required")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class SyncStatusResponse(BaseModel):
    last_sync: dict[str, Any] | None
    total_syncs: int
    source: str
    admin_token_required: bool


class SyncTriggerResponse(BaseModel):
    sync_id: str
    status: str
    rows_fetched: int
    rows_validated: int
    rows_quarantined: int
    rows_invalid: int
    rows_duplicate: int
    data_hash: str | None
    error: str | None


class VersionSummary(BaseModel):
    version: str
    created_at: str
    status: str
    parent_version: str | None = None
    reason: str | None = None


class VersionDetail(BaseModel):
    version: str
    created_at: str
    status: str
    parent_version: str | None
    data_provenance: dict[str, Any]
    parameters: dict[str, Any]
    validation: dict[str, Any]


class VersionListResponse(BaseModel):
    active_version: str
    versions: list[VersionSummary]
    recalibration_log: list[dict[str, Any]]


class PromoteResponse(BaseModel):
    active_version: str
    prior_active: str | None
    action: str


# ---------------------------------------------------------------------------
# ETL sync endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status() -> SyncStatusResponse:
    cfg = get_config()
    pipeline = ETLPipeline(cfg)
    audit = pipeline._writer.read_audit_log()
    last = audit[-1] if audit else None
    return SyncStatusResponse(
        last_sync=last,
        total_syncs=len(audit),
        source=f"{cfg.production_api_url}/admin/etl/quotes",
        admin_token_required=bool(os.getenv("ADMIN_TOKEN")),
    )


@router.get("/audit-log")
async def get_audit_log(limit: int = 50) -> dict[str, Any]:
    pipeline = ETLPipeline()
    log = pipeline._writer.read_audit_log()
    return {"total": len(log), "entries": log[-limit:]}


@router.post(
    "/sync",
    response_model=SyncTriggerResponse,
    dependencies=[Depends(admin_required)],
)
async def trigger_manual_sync() -> SyncTriggerResponse:
    pipeline = ETLPipeline()
    result = await pipeline.run_sync()
    return SyncTriggerResponse(
        sync_id=result.sync_id,
        status=result.status,
        rows_fetched=result.rows_fetched,
        rows_validated=result.rows_validated,
        rows_quarantined=result.rows_quarantined,
        rows_invalid=result.rows_invalid,
        rows_duplicate=result.rows_duplicate,
        data_hash=result.data_hash,
        error=result.error,
    )


# ---------------------------------------------------------------------------
# Recalibration endpoints
# ---------------------------------------------------------------------------

class RecalibrateRequest(BaseModel):
    trigger: str = "manual"
    days_back: int = 90
    dry_run: bool = False             # if True, run analysis only; do not write a version


@router.post("/recalibrate", dependencies=[Depends(admin_required)])
async def run_recalibration(payload: RecalibrateRequest | None = None) -> dict[str, Any]:
    """
    Run the recalibration engine against the local ETL dataset.

    - ``dry_run=True`` returns the full analysis report without writing.
    - Otherwise creates a candidate version and auto-promotes iff fairness passes
      (per the configured policy).
    """
    req = payload or RecalibrateRequest()
    engine = CalibrationEngine()
    if req.dry_run:
        report = engine.run_analysis(trigger=req.trigger, days_back=req.days_back)
    else:
        report = engine.propose_candidate_version(trigger=req.trigger, days_back=req.days_back)
    return report.to_dict()


# ---------------------------------------------------------------------------
# A/E ratio endpoint
# ---------------------------------------------------------------------------

@router.get("/ae-ratio")
async def ae_ratio(days_back: int = 90) -> dict[str, Any]:
    """
    Actual vs Expected mortality ratio by occupation and healthcare tier.
    Actual = mean mortality_ratio observed in quotes.
    Expected = current model multiplier for that cohort.
    A/E > 1.0 = under-pricing (model under-estimates risk).
    A/E < 1.0 = over-pricing (model over-estimates risk).
    """
    engine = CalibrationEngine()
    report = engine.run_analysis(trigger="ae_check", days_back=days_back)

    if report.status == "insufficient_data":
        return {
            "status": "insufficient_data",
            "quotes_available": report.total_valid_quotes,
            "message": report.reasoning[0] if report.reasoning else "Not enough quotes",
        }

    # Find baseline mean MR for each cohort type to normalize empirical multipliers
    baselines: dict[str, float] = {}
    for c in report.cohort_stats:
        if c.cohort == "office_desk" and c.cohort_type == "occupation":
            baselines["occupation"] = c.mean_mortality_ratio
        if c.cohort == "tier_b" and c.cohort_type == "healthcare_tier":
            baselines["healthcare_tier"] = c.mean_mortality_ratio

    rows = []
    for c in report.cohort_stats:
        if c.current_multiplier is None or c.n < 5:
            continue
        baseline_mr = baselines.get(c.cohort_type)
        if baseline_mr and baseline_mr > 0:
            empirical_multiplier = c.mean_mortality_ratio / baseline_mr
            ratio = round(empirical_multiplier / c.current_multiplier, 3)
        else:
            ratio = None

        rows.append({
            "cohort": c.cohort,
            "cohort_type": c.cohort_type,
            "n": c.n,
            "actual_mean_mr": c.mean_mortality_ratio,
            "current_multiplier": c.current_multiplier,
            "ae_ratio": ratio,
            "status": (
                "under-pricing" if ratio and ratio > 1.02
                else "over-pricing" if ratio and ratio < 0.98
                else "on-target"
            ) if ratio is not None else "insufficient_data",
        })

    rows.sort(key=lambda x: abs((x["ae_ratio"] or 1.0) - 1.0), reverse=True)
    return {
        "active_version": report.parent_version,
        "quotes_analyzed": report.total_valid_quotes,
        "days_back": days_back,
        "psi": report.psi,
        "cohorts": rows,
    }


# ---------------------------------------------------------------------------
# Version endpoints
# ---------------------------------------------------------------------------

@router.get("/versions", response_model=VersionListResponse)
async def list_versions() -> VersionListResponse:
    manifest = versioning.read_manifest()
    return VersionListResponse(
        active_version=manifest["active_version"],
        versions=[VersionSummary(**v) for v in manifest.get("versions", [])],
        recalibration_log=manifest.get("recalibration_log", []),
    )


@router.get("/versions/diff")
async def versions_diff(from_version: str, to_version: str) -> dict[str, Any]:
    """
    Compare multiplier parameters between two versions (butterfly chart data).
    Returns per-group parameter deltas sorted by absolute change.
    """
    try:
        from_payload = versioning.load_version_raw(from_version)
    except versioning.VersionNotFoundError:
        raise HTTPException(404, f"Version {from_version!r} not found")
    try:
        to_payload = versioning.load_version_raw(to_version)
    except versioning.VersionNotFoundError:
        raise HTTPException(404, f"Version {to_version!r} not found")

    from_params = from_payload.get("parameters", {})
    to_params   = to_payload.get("parameters", {})

    groups = sorted(set(list(from_params) + list(to_params)))
    diffs: dict[str, list] = {}
    for group in groups:
        fp = from_params.get(group, {})
        tp = to_params.get(group, {})
        if not isinstance(fp, dict) or not isinstance(tp, dict):
            continue
        keys = sorted(set(list(fp) + list(tp)))
        group_diffs = []
        for key in keys:
            old_val = fp.get(key)
            new_val = tp.get(key)
            if old_val is None or new_val is None:
                continue
            try:
                delta_pct = round((float(new_val) - float(old_val)) / float(old_val) * 100, 2)
            except (ZeroDivisionError, TypeError):
                delta_pct = None
            if delta_pct is not None and abs(delta_pct) >= 0.01:
                group_diffs.append({
                    "parameter": key,
                    "from_value": old_val,
                    "to_value": new_val,
                    "delta_pct": delta_pct,
                    "direction": "increased" if delta_pct > 0 else "decreased",
                })
        if group_diffs:
            group_diffs.sort(key=lambda x: abs(x["delta_pct"]), reverse=True)
            diffs[group] = group_diffs

    return {
        "from_version": from_version,
        "to_version": to_version,
        "from_created_at": from_payload.get("created_at"),
        "to_created_at": to_payload.get("created_at"),
        "changed_parameters": sum(len(v) for v in diffs.values()),
        "groups": diffs,
    }


@router.get("/versions/active", response_model=VersionDetail)
async def get_active_version() -> VersionDetail:
    payload = versioning.load_version_raw(versioning.get_active_version_id())
    return _version_detail(payload)


@router.get("/versions/{version_id}", response_model=VersionDetail)
async def get_version(version_id: str) -> VersionDetail:
    try:
        payload = versioning.load_version_raw(version_id)
    except versioning.VersionNotFoundError:
        raise HTTPException(status_code=404, detail=f"version {version_id} not found")
    return _version_detail(payload)


@router.post(
    "/versions/{version_id}/promote",
    response_model=PromoteResponse,
    dependencies=[Depends(admin_required)],
)
async def promote_version(version_id: str, reason: str | None = None) -> PromoteResponse:
    try:
        versioning.validate_version_id(version_id)
    except versioning.InvalidVersionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        prior = versioning.get_active_version_id()
        versioning.promote_version(version_id, reason=reason or "manual promote via API")
    except versioning.VersionNotFoundError:
        raise HTTPException(status_code=404, detail=f"version {version_id} not found")
    return PromoteResponse(active_version=version_id, prior_active=prior, action="promote")


@router.post(
    "/versions/{version_id}/rollback",
    response_model=PromoteResponse,
    dependencies=[Depends(admin_required)],
)
async def rollback_version(version_id: str, reason: str | None = None) -> PromoteResponse:
    try:
        versioning.validate_version_id(version_id)
    except versioning.InvalidVersionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        prior = versioning.get_active_version_id()
        versioning.rollback_to(version_id, reason=reason or "manual rollback via API")
    except versioning.VersionNotFoundError:
        raise HTTPException(status_code=404, detail=f"version {version_id} not found")
    return PromoteResponse(active_version=version_id, prior_active=prior, action="rollback")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _version_detail(payload: dict[str, Any]) -> VersionDetail:
    manifest = versioning.read_manifest()
    status = "unknown"
    for entry in manifest.get("versions", []):
        if entry["version"] == payload["version"]:
            status = entry.get("status", "unknown")
            break
    return VersionDetail(
        version=payload["version"],
        created_at=payload.get("created_at", ""),
        status=status,
        parent_version=payload.get("parent_version"),
        data_provenance=payload.get("data_provenance", {}),
        parameters=payload.get("parameters", {}),
        validation=payload.get("validation", {}),
    )
