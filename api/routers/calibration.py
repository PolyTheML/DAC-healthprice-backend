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
