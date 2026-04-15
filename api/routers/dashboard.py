"""API routes for /dashboard endpoints — monitoring and analytics."""

from fastapi import APIRouter

from api.deps import get_case_store
from analytics.monitor import (
    PHNOM_PENH_ALIASES,
    REFERENCE_DISTRIBUTION,
    calculate_human_override_rate,
    calculate_psi,
    get_psi_time_series,
)

router = APIRouter()


@router.get("/stats")
async def dashboard_stats():
    """
    Return dashboard KPIs for the Underwriter Dashboard.

    Reads from the in-memory case_store singleton. For production,
    replace with a database query.

    Response shape:
        psi.current         float   — PSI from last 100 cases vs reference
        psi.status          str     — "stable" | "warning" | "drift"
        province_distribution       — case counts by province
        hitl_queue.pending_count    — cases with status == "review"
        hitl_queue.pending_cases    — top 10 most recent (summary dicts)
        human_override_rate         — override statistics
        psi_time_series             — 30-day [{date, psi, n_cases}] list
    """
    case_store = get_case_store()
    cases = list(case_store.values())
    case_summaries = [c.to_summary() for c in cases]

    # --- PSI on last 100 cases ---
    recent_mortality_ratios = [
        c.actuarial.mortality_ratio
        for c in cases[-100:]
        if c.actuarial.mortality_ratio > 0
    ]
    psi_score = 0.0
    if len(recent_mortality_ratios) >= 5:
        psi_score = calculate_psi(
            REFERENCE_DISTRIBUTION["mortality_ratio"], recent_mortality_ratios
        )
    psi_status = (
        "stable" if psi_score < 0.10 else ("warning" if psi_score < 0.25 else "drift")
    )

    # --- Province distribution ---
    phnom_penh_count = sum(
        1
        for c in cases
        if (c.extracted_data.province or "").lower() in PHNOM_PENH_ALIASES
    )
    province_count = len(cases) - phnom_penh_count

    # --- HITL queue (status == "review") ---
    pending = [c for c in cases if c.status == "review"]
    pending_summaries = [c.to_summary() for c in pending[-10:]]

    # --- Human override rate ---
    override_stats = calculate_human_override_rate(case_summaries)

    # --- PSI time series (30-day) ---
    psi_series = get_psi_time_series(case_summaries, window_days=30)

    return {
        "psi": {"current": round(psi_score, 4), "status": psi_status},
        "province_distribution": {
            "phnom_penh": phnom_penh_count,
            "provinces": province_count,
            "total": len(cases),
        },
        "hitl_queue": {
            "pending_count": len(pending),
            "pending_cases": pending_summaries,
        },
        "human_override_rate": override_stats,
        "psi_time_series": psi_series,
    }
