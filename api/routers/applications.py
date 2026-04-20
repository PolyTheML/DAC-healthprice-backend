"""API routes for /api/v1/applications endpoints."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api import crud
from api.database import get_db
from api.middleware.jwt import require_auth

router = APIRouter()


def _next_id() -> str:
    return f"DAC-{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:4].upper()}"


class ApplicationCreate(BaseModel):
    full_name: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    region: Optional[str] = None
    occupation: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    medical_data: Optional[Dict[str, Any]] = None


class DecisionRequest(BaseModel):
    outcome: str  # "approved" | "declined" | "referred"
    notes: Optional[str] = ""
    reviewer_id: Optional[str] = ""


@router.get("")
def list_applications(
    status: Optional[str] = Query(None, description="Comma-separated statuses to filter by"),
    auth: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    statuses = {s.strip() for s in status.split(",")} if status else None
    apps = crud.list_applications(db, statuses)
    return {"applications": apps}


@router.post("")
def create_application(body: ApplicationCreate, db: Session = Depends(get_db)):
    """Create a new application — public endpoint, no auth required."""
    app_id = _next_id()
    now = datetime.utcnow()
    fields = {
        "full_name": body.full_name,
        "status": "submitted",
        "submitted_at": now,
        "date_of_birth": body.date_of_birth,
        "gender": body.gender,
        "region": body.region,
        "occupation": body.occupation,
        "phone": body.phone,
        "email": body.email,
        "medical_data": body.medical_data or {},
        "timeline": [
            {"event": "Application received", "done": True,  "timestamp": now.isoformat()},
            {"event": "Initial review",        "done": False, "timestamp": None},
            {"event": "Underwriter decision",  "done": False, "timestamp": None},
            {"event": "Policy issued",         "done": False, "timestamp": None},
        ],
    }
    crud.create_application(db, app_id, fields)
    return {"id": app_id, "status": "submitted", "reference": app_id}


@router.get("/{app_id}/status")
def get_status(app_id: str, db: Session = Depends(get_db)):
    """Status timeline — public so applicants can track without auth."""
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    return {"id": app_id, "status": app["status"], "timeline": app["timeline"]}


@router.post("/{app_id}/decision")
def make_decision(
    app_id: str,
    body: DecisionRequest,
    auth: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")

    now = datetime.utcnow().isoformat()
    decision = {
        "outcome": body.outcome,
        "notes": body.notes,
        "reviewer_id": body.reviewer_id or auth.get("sub", "unknown"),
        "decided_at": now,
    }
    timeline = app["timeline"]
    for event in timeline:
        if event["event"] == "Underwriter decision":
            event["done"] = True
            event["timestamp"] = now
        if event["event"] == "Policy issued" and body.outcome == "approved":
            event["done"] = True
            event["timestamp"] = now

    crud.update_application(db, app_id, body.outcome, decision=decision, timeline=timeline)
    return {"id": app_id, "status": body.outcome}
