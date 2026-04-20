"""API routes for /dashboard endpoints — monitoring and analytics."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api import crud
from api.database import get_db
from analytics.monitor import (
    PHNOM_PENH_ALIASES,
    REFERENCE_DISTRIBUTION,
    calculate_human_override_rate,
    calculate_psi,
    get_psi_time_series,
)

router = APIRouter()


@router.get("/stats")
async def dashboard_stats(db: Session = Depends(get_db)):
    """
    Return dashboard KPIs for the Underwriter Dashboard.

    PSI is computed from a dedicated DB query (last 100 cases) rather than
    slicing a full list load — keeps this endpoint fast at scale.
    """
    # PSI: query the 100 most-recent mortality_ratio values directly
    recent_mortality_ratios = crud.get_recent_mortality_ratios(db, limit=100)
    psi_score = 0.0
    if len(recent_mortality_ratios) >= 5:
        psi_score = calculate_psi(
            REFERENCE_DISTRIBUTION["mortality_ratio"], recent_mortality_ratios
        )
    psi_status = "stable" if psi_score < 0.10 else ("warning" if psi_score < 0.25 else "drift")

    # Province distribution
    records = crud.list_case_records(db)
    phnom_penh_count = sum(
        1 for r in records if (r.province or "").lower() in PHNOM_PENH_ALIASES
    )

    # HITL queue (status == "review")
    pending_summaries = crud.get_pending_cases(db, limit=10)
    pending_count = len(pending_summaries)

    # Human override rate and PSI time series (need full summaries for these)
    case_summaries = crud.list_case_summaries(db)
    override_stats = calculate_human_override_rate(case_summaries)
    psi_series = get_psi_time_series(case_summaries, window_days=30)

    return {
        "psi": {"current": round(psi_score, 4), "status": psi_status},
        "province_distribution": {
            "phnom_penh": phnom_penh_count,
            "provinces": len(records) - phnom_penh_count,
            "total": len(records),
        },
        "hitl_queue": {
            "pending_count": pending_count,
            "pending_cases": pending_summaries,
        },
        "human_override_rate": override_stats,
        "psi_time_series": psi_series,
    }
