"""
Auto Insurance Pricing Routes — Continuous Underwriting

POST /api/v1/auto/quote              — static GLM quote + create policy
POST /api/v1/auto/telematics-event   — ingest telemetry, update premium
GET  /api/v1/auto/policies/{policy_id}      — get policy state
GET  /api/v1/auto/policies/{policy_id}/stream — SSE live premium ticker
"""
from __future__ import annotations
import sys
import json
import asyncio
import uuid
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.data.features import VehicleProfile
from app.data.validation import validate_profile
from app.pricing_engine.glm_pricing import compute_glm_price
from app.auto.models import (
    AutoQuoteRequest,
    AutoQuoteResponse,
    TelematicsEvent,
    MaskedTelemetry,
)
from app.auto.streaming_model import _global_streaming_model
from app.auto.fairness import compute_fairness_audit, FairnessAuditResponse

router = APIRouter(prefix="/api/v1/auto", tags=["auto-pricing"])
log = logging.getLogger(__name__)

# ── In-memory SSE pubsub (single-process; upgrade to Redis for multi-worker) ──
_policy_queues: dict[str, list[asyncio.Queue]] = {}


def _publish_policy(policy_id: str, data: dict) -> None:
    for q in _policy_queues.get(policy_id, []):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


async def _subscribe_policy(policy_id: str) -> asyncio.Queue:
    q = asyncio.Queue(maxsize=64)
    _policy_queues.setdefault(policy_id, []).append(q)
    return q


def _unsubscribe_policy(policy_id: str, q: asyncio.Queue) -> None:
    subs = _policy_queues.get(policy_id, [])
    if q in subs:
        subs.remove(q)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mask_pii(event: TelematicsEvent) -> MaskedTelemetry:
    """Strip raw GPS into a geohash-like token; bucket time to hour only."""
    lat_hash = hashlib.sha256(
        f"{event.gps_lat:.2f}:{event.gps_lon:.2f}".encode()
    ).hexdigest()[:6]
    hour = event.timestamp.hour if event.timestamp else datetime.utcnow().hour
    return MaskedTelemetry(
        policy_id=event.policy_id,
        gps_hash=lat_hash,
        speed_kmh=event.speed_kmh,
        harsh_braking=event.harsh_braking,
        lane_shifts=event.lane_shifts,
        hour_bucket=hour,
        weather_zone=None,  # placeholder for external weather API
    )


def _get_db_pool(request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return pool


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/quote", response_model=AutoQuoteResponse)
async def auto_quote(request: Request, req: AutoQuoteRequest):
    """Create a new auto policy and return the GLM anchor premium."""
    err = validate_profile(req.model_dump())
    if err:
        raise HTTPException(status_code=400, detail=err)

    profile = VehicleProfile(**req.model_dump())
    result = compute_glm_price(profile)

    policy_id = f"AUTO-{uuid.uuid4().hex[:8].upper()}"
    pool = _get_db_pool(request)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO auto_policies (
                policy_id, vehicle_type, year_of_manufacture, region,
                driver_age, accident_history, coverage, tier, family_size,
                glm_anchor, current_premium, deviation_multiplier
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            policy_id,
            req.vehicle_type,
            req.year_of_manufacture,
            req.region,
            req.driver_age,
            req.accident_history,
            req.coverage,
            req.tier,
            req.family_size,
            result.glm_price,
            result.glm_price,
            1.0,
        )

    return AutoQuoteResponse(
        policy_id=policy_id,
        glm_anchor=result.glm_price,
        current_premium=result.glm_price,
        deviation_multiplier=1.0,
        breakdown=result.to_dict(),
    )


@router.post("/telematics-event")
async def process_telematics_event(request: Request, event: TelematicsEvent):
    """Ingest a telemetry ping, compute deviation, update premium, and broadcast."""
    safe = _mask_pii(event)
    pool = _get_db_pool(request)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT glm_anchor FROM auto_policies WHERE policy_id = $1",
            event.policy_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Policy not found")
        anchor = float(row["glm_anchor"])

    # Predict deviation from masked telemetry
    features = safe.model_dump()

    # Synthetic residual for demo warm-up (river learns online from heuristic target)
    synthetic_residual = (
        safe.speed_kmh * 0.001
        + (0.15 if safe.harsh_braking else 0.0)
        + safe.lane_shifts * 0.05
        + (0.10 if safe.hour_bucket in (0, 1, 2, 3, 4, 5, 6, 22, 23) else 0.0)
    )
    _global_streaming_model.update_one(features, synthetic_residual)

    deviation = _global_streaming_model.predict_deviation(features)
    new_premium = anchor * deviation

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO auto_telemetry_log
                (policy_id, gps_hash, speed_kmh, harsh_braking,
                 lane_shifts, hour_bucket, weather_zone, deviation, new_premium)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            """,
            event.policy_id,
            safe.gps_hash,
            safe.speed_kmh,
            safe.harsh_braking,
            safe.lane_shifts,
            safe.hour_bucket,
            safe.weather_zone,
            deviation,
            new_premium,
        )
        await conn.execute(
            """
            UPDATE auto_policies
            SET current_premium = $1,
                deviation_multiplier = $2,
                updated_at = NOW()
            WHERE policy_id = $3
            """,
            new_premium,
            deviation,
            event.policy_id,
        )

    payload = {
        "new_premium": round(new_premium, 2),
        "deviation": round(deviation, 4),
        "trigger": "harsh_braking" if event.harsh_braking else "normal",
        "ts": datetime.utcnow().isoformat(),
    }
    _publish_policy(event.policy_id, payload)

    return {
        "status": "Premium Re-aligned",
        "policy_id": event.policy_id,
        "new_premium": round(new_premium, 2),
        "deviation": round(deviation, 4),
    }


@router.get("/policies/{policy_id}")
async def get_policy(request: Request, policy_id: str):
    """Fetch current policy state."""
    pool = _get_db_pool(request)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM auto_policies WHERE policy_id = $1", policy_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")
    return dict(row)


@router.get("/policies/{policy_id}/stream")
async def stream_premium(request: Request, policy_id: str):
    """Server-Sent Events stream of premium updates for a given policy."""

    async def event_generator() -> AsyncGenerator[str, None]:
        q = await _subscribe_policy(policy_id)
        try:
            # Emit current state immediately
            pool = _get_db_pool(request)
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT current_premium, deviation_multiplier
                    FROM auto_policies WHERE policy_id = $1
                    """,
                    policy_id,
                )
            if row:
                payload = {
                    "new_premium": float(row["current_premium"]),
                    "deviation": float(row["deviation_multiplier"]),
                    "trigger": "connected",
                    "ts": datetime.utcnow().isoformat(),
                }
                yield f"data: {json.dumps(payload)}\n\n"

            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=25.0)
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'keepalive': True, 'ts': datetime.utcnow().isoformat()})}\n\n"
                    continue
                yield f"data: {json.dumps(data)}\n\n"
        finally:
            _unsubscribe_policy(policy_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/fairness-audit", response_model=FairnessAuditResponse)
async def fairness_audit(request: Request):
    """Return real-time fairness scores for auto policies."""
    pool = _get_db_pool(request)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT driver_age, region, deviation_multiplier FROM auto_policies"
        )
    return compute_fairness_audit([dict(r) for r in rows])
