"""CRUD helpers for ApplicationRecord and CaseRecord."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from api.db_models import ApplicationRecord, CaseRecord
from medical_reader.state import UnderwritingState


# ── Applications ──────────────────────────────────────────────────────────────

def list_applications(db: Session, statuses: Optional[set] = None) -> List[Dict]:
    q = db.query(ApplicationRecord)
    if statuses:
        q = q.filter(ApplicationRecord.status.in_(statuses))
    return [app_record_to_dict(r) for r in q.order_by(ApplicationRecord.submitted_at.desc()).all()]


def get_application(db: Session, app_id: str) -> Optional[Dict]:
    record = db.get(ApplicationRecord, app_id)
    return app_record_to_dict(record) if record else None


def create_application(db: Session, app_id: str, fields: Dict) -> Dict:
    record = ApplicationRecord(id=app_id, **fields)
    db.add(record)
    db.commit()
    db.refresh(record)
    return app_record_to_dict(record)


def update_application(
    db: Session,
    app_id: str,
    status: str,
    decision: Optional[Dict] = None,
    timeline: Optional[List] = None,
) -> Optional[Dict]:
    record = db.get(ApplicationRecord, app_id)
    if not record:
        return None
    record.status = status
    if decision is not None:
        record.decision = decision
    if timeline is not None:
        record.timeline = timeline
    db.commit()
    db.refresh(record)
    return app_record_to_dict(record)


def count_applications(db: Session) -> int:
    return db.query(ApplicationRecord).count()


def app_record_to_dict(r: ApplicationRecord) -> Dict:
    return {
        "id": r.id,
        "full_name": r.full_name,
        "status": r.status,
        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        "region": r.region,
        "occupation": r.occupation,
        "date_of_birth": r.date_of_birth,
        "gender": r.gender,
        "phone": r.phone,
        "email": r.email,
        "medical_data": r.medical_data or {},
        "timeline": r.timeline or [],
        "decision": r.decision,
    }


# ── Cases ─────────────────────────────────────────────────────────────────────

def upsert_case(db: Session, state: UnderwritingState) -> CaseRecord:
    """Insert or update a CaseRecord from a UnderwritingState object."""
    record = db.get(CaseRecord, state.case_id)
    is_new = record is None
    if is_new:
        record = CaseRecord(case_id=state.case_id)
        # Capture AI's original assessment on first write (before any human override)
        record.ai_risk_score = state.risk_score
        record.ai_risk_level = state.risk_level.value
        db.add(record)

    record.status = state.status
    record.risk_level = state.risk_level.value
    record.risk_score = state.risk_score
    record.overall_confidence = state.overall_confidence
    record.final_premium = state.actuarial.final_premium
    record.mortality_ratio = state.actuarial.mortality_ratio
    record.province = state.extracted_data.province
    record.requires_review = state.requires_human_review
    record.updated_at = datetime.utcnow()
    # Exclude raw bytes — not JSON-serializable
    record.state_json = state.model_dump(mode="json", exclude={"source_document_raw"})

    db.commit()
    db.refresh(record)
    return record


def apply_human_review(
    db: Session,
    case_id: str,
    approved: bool,
    reviewer_id: str,
    notes: str,
    updated_state: UnderwritingState,
) -> Optional[CaseRecord]:
    """Persist human review decision alongside the AI's original assessment for A/E analysis."""
    record = db.get(CaseRecord, case_id)
    if not record:
        return None

    record.status = updated_state.status
    record.updated_at = datetime.utcnow()
    record.human_override = True
    record.human_decision = "approved" if approved else "declined"
    record.human_reviewer_id = reviewer_id
    record.human_notes = notes
    record.human_reviewed_at = datetime.utcnow()
    record.state_json = updated_state.model_dump(mode="json", exclude={"source_document_raw"})

    db.commit()
    db.refresh(record)
    return record


def get_case(db: Session, case_id: str) -> Optional[CaseRecord]:
    return db.get(CaseRecord, case_id)


def record_to_state(record: CaseRecord) -> UnderwritingState:
    """Reconstruct a UnderwritingState from a CaseRecord's state_json blob."""
    return UnderwritingState.model_validate(record.state_json)


def list_case_records(db: Session, limit: int = 1000) -> List[CaseRecord]:
    return (
        db.query(CaseRecord)
        .order_by(CaseRecord.created_at.asc())
        .limit(limit)
        .all()
    )


def get_recent_mortality_ratios(db: Session, limit: int = 100) -> List[float]:
    """Fetch mortality_ratio from the most recent N cases — avoids loading full state_json."""
    rows = (
        db.query(CaseRecord.mortality_ratio)
        .order_by(CaseRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return [r.mortality_ratio for r in rows if r.mortality_ratio > 0]


def get_pending_cases(db: Session, limit: int = 10) -> List[Dict]:
    """Return summary dicts for cases currently awaiting human review."""
    records = (
        db.query(CaseRecord)
        .filter(CaseRecord.status == "review")
        .order_by(CaseRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return [case_record_to_summary(r) for r in records]


def list_case_summaries(db: Session, limit: int = 1000) -> List[Dict]:
    """Return summary dicts shaped like UnderwritingState.to_summary() for analytics functions."""
    return [case_record_to_summary(r) for r in list_case_records(db, limit)]


def case_record_to_summary(r: CaseRecord) -> Dict:
    """Convert a CaseRecord to the summary dict shape used by analytics/monitor.py."""
    state_data = r.state_json or {}
    extracted = state_data.get("extracted_data", {})
    occ = state_data.get("occupation_risk", {})
    reg = state_data.get("region_risk", {})
    return {
        "case_id": r.case_id,
        "status": r.status,
        "risk_level": r.risk_level,
        "final_premium": round(r.final_premium, 2),
        "overall_confidence": round(r.overall_confidence, 2),
        "requires_review": r.requires_review,
        # Exposed at top level so get_psi_time_series can pick it up
        "mortality_ratio": round(r.mortality_ratio, 4),
        "extracted_data": {
            "age": extracted.get("age"),
            "bmi": extracted.get("bmi"),
            "blood_pressure": (
                f"{extracted.get('blood_pressure_systolic')}/"
                f"{extracted.get('blood_pressure_diastolic')}"
            ),
            "smoker": extracted.get("smoker"),
            "province": extracted.get("province"),
            "occupation_type": extracted.get("occupation_type"),
            "motorbike_usage": extracted.get("motorbike_usage"),
        },
        "cambodia_risk": {
            "occupation_multiplier": round(occ.get("risk_multiplier", 1.0), 4),
            "endemic_multiplier": round(reg.get("endemic_risk_multiplier", 1.0), 4),
            "healthcare_discount": round(reg.get("healthcare_reliability_discount", 1.0), 4),
        },
        "reasoning_trace": state_data.get("reasoning_trace", ""),
        "audit_entries": len(state_data.get("audit_trail", [])),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        # A/E analysis fields
        "ai_risk_score": r.ai_risk_score,
        "ai_risk_level": r.ai_risk_level,
        "human_override": r.human_override,
        "human_decision": r.human_decision,
    }
