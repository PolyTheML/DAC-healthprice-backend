"""API routes for /cases endpoints."""

import tempfile
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from api.deps import get_graph, get_case_store
from api.models import (
    CaseSubmitResponse,
    CaseListItem,
    ReviewRequest,
    ReviewResponse,
    CaseDetailResponse,
    AuditReportResponse,
)
from medical_reader.state import UnderwritingState


class HealthQuoteRequest(BaseModel):
    """Optional overrides when bridging a case to health insurance pricing."""
    country: str = Field(default="cambodia", description="cambodia | vietnam")
    region: str = Field(default="Phnom Penh")
    ipd_tier: str = Field(default="Silver", description="Bronze | Silver | Gold | Platinum")
    coverage_types: List[str] = Field(default_factory=lambda: ["ipd"])
    face_amount: float = Field(default=50_000.0, ge=10_000.0, le=500_000.0)
    policy_term_years: int = Field(default=1, ge=1, le=40)

router = APIRouter()


def generate_case_id() -> str:
    """Generate a unique case ID."""
    return f"CASE-{datetime.now():%Y%m%d-%H%M%S}"


@router.post("", response_model=CaseSubmitResponse)
async def submit_case(file: UploadFile = File(...)):
    """
    Submit a new case: upload PDF and run through underwriting workflow.

    Returns immediately with current state (may be approved, declined, or pending review).
    """
    graph = get_graph()
    case_store = get_case_store()

    case_id = generate_case_id()

    # Write uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        pdf_path = tmp.name

    # Run the case through the workflow
    try:
        state = graph.invoke(
            {"case_id": case_id, "source_document_path": pdf_path},
            config={"configurable": {"thread_id": case_id}}
        )
        state = UnderwritingState(**state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")

    # Store in case registry
    case_store[case_id] = state

    # Return summary
    return CaseSubmitResponse(
        case_id=state.case_id,
        status=state.status,
        risk_level=state.risk_level.value,
        risk_score=state.risk_score,
        overall_confidence=state.overall_confidence,
        final_premium=state.actuarial.final_premium,
        requires_review=state.requires_human_review,
        audit_entries=len(state.audit_trail),
        created_at=state.created_at,
    )


@router.get("", response_model=list[CaseListItem])
async def list_cases():
    """List all cases."""
    case_store = get_case_store()

    items = []
    for case_id, state in case_store.items():
        items.append(CaseListItem(
            case_id=state.case_id,
            status=state.status,
            risk_level=state.risk_level.value,
            risk_score=state.risk_score,
            final_premium=state.actuarial.final_premium,
            reviewer_id=state.review.reviewer_id,
            created_at=state.created_at,
        ))

    return items


@router.get("/{case_id}", response_model=CaseDetailResponse)
async def get_case(case_id: str):
    """Get full case details."""
    case_store = get_case_store()

    if case_id not in case_store:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    state = case_store[case_id]

    return CaseDetailResponse(
        case_id=state.case_id,
        status=state.status,
        risk_level=state.risk_level.value,
        risk_score=state.risk_score,
        overall_confidence=state.overall_confidence,
        final_premium=state.actuarial.final_premium,
        requires_review=state.requires_human_review,
        audit_entries=len(state.audit_trail),
        created_at=state.created_at,
        updated_at=state.updated_at,
        extracted_data=state.extracted_data.model_dump(),
        actuarial=state.actuarial.model_dump(),
        review_notes=state.review.model_dump() if state.review else None,
    )


@router.post("/{case_id}/review", response_model=ReviewResponse)
async def submit_review(case_id: str, review: ReviewRequest):
    """
    Submit a human review decision for a case awaiting review.

    Only valid when case.status == "review".
    Resumes the workflow from the HITL checkpoint.
    """
    graph = get_graph()
    case_store = get_case_store()

    if case_id not in case_store:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    state = case_store[case_id]

    if state.status != "review":
        raise HTTPException(
            status_code=409,
            detail=f"Case {case_id} is not awaiting review (current status: {state.status})"
        )

    # Resume the workflow with the reviewer decision
    try:
        from langgraph.types import Command
        result = graph.invoke(
            Command(resume={
                "approved": review.approved,
                "notes": review.notes,
                "reviewer_id": review.reviewer_id,
            }),
            config={"configurable": {"thread_id": case_id}}
        )
        updated_state = UnderwritingState(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review submission failed: {str(e)}")

    # Update case store
    case_store[case_id] = updated_state

    return ReviewResponse(
        case_id=updated_state.case_id,
        status=updated_state.status,
        approved=review.approved,
        reviewer_id=review.reviewer_id,
        timestamp=datetime.utcnow(),
    )


@router.get("/{case_id}/audit-report", response_class=PlainTextResponse)
async def get_audit_report(case_id: str):
    """Get plaintext audit report for a case."""
    case_store = get_case_store()

    if case_id not in case_store:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    state = case_store[case_id]
    return state.to_audit_report()


@router.get("/{case_id}/summary", response_model=dict)
async def get_case_summary(case_id: str):
    """Get JSON summary for a case."""
    case_store = get_case_store()

    if case_id not in case_store:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    state = case_store[case_id]
    return state.to_summary()


@router.post("/{case_id}/health-quote")
async def get_health_quote(case_id: str, req: HealthQuoteRequest = None):
    """
    Bridge life insurance case → health insurance GLM quote.

    Takes the medical data already extracted from the PDF (via the intake node)
    and prices it through the health insurance engine.  Returns both the
    original life insurance actuarial result and a new health insurance quote
    side-by-side so an actuary can review both in a single response.

    Fields absent from the medical PDF (occupation, diet, exercise, etc.) are
    given conservative clinical defaults; all mapping decisions are reported in
    `mapping_notes` for the audit trail.
    """
    if req is None:
        req = HealthQuoteRequest()

    case_store = get_case_store()
    if case_id not in case_store:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    state = case_store[case_id]

    if not state.is_intake_complete:
        raise HTTPException(
            status_code=409,
            detail=f"Case {case_id} intake not complete (status: {state.status}). "
                   "Submit and process the case first."
        )

    try:
        from medical_reader.nodes.health_pricing_bridge import bridge_extracted_to_health_quote
        health_result = bridge_extracted_to_health_quote(
            extracted=state.extracted_data,
            country=req.country,
            region=req.region,
            ipd_tier=req.ipd_tier,
            coverage_types=req.coverage_types,
            face_amount=req.face_amount,
            policy_term_years=req.policy_term_years,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health pricing bridge failed: {str(e)}")

    return {
        "case_id": case_id,
        "life_insurance": {
            "gross_annual_premium": round(state.actuarial.gross_premium, 2),
            "monthly_premium": round(state.actuarial.monthly_premium, 2),
            "mortality_ratio": round(state.actuarial.mortality_ratio, 4),
            "risk_tier": state.risk_level.value,
            "factor_breakdown": state.actuarial.factor_breakdown,
            "assumption_version": state.actuarial.assumption_version,
        },
        "health_insurance": health_result,
        "note": (
            "Life insurance uses Mortality Ratio method (medical_reader/pricing/calculator.py). "
            "Health insurance uses Poisson-Gamma GLM (app/pricing_engine/health_pricing.py). "
            f"Health pricing confidence: {health_result['pricing_confidence']:.0%} "
            f"({len(health_result['inferred_fields'])} fields defaulted)."
        ),
    }


@router.get("/{case_id}/pricing-breakdown")
async def get_pricing_breakdown(case_id: str):
    """
    Get full pricing breakdown for a case.

    Returns complete premium calculation with transparent component breakdown,
    risk factors applied, mortality ratio, and assumption version for compliance.
    """
    case_store = get_case_store()

    if case_id not in case_store:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    state = case_store[case_id]

    if not state.is_pricing_complete:
        raise HTTPException(
            status_code=409,
            detail=f"Case {case_id} pricing not yet complete (status: {state.status})"
        )

    return {
        "case_id": state.case_id,
        "face_amount": state.actuarial.face_amount,
        "policy_term_years": state.actuarial.policy_term_years,
        "base_mortality_rate": round(state.actuarial.base_mortality_rate, 4),
        "mortality_ratio": round(state.actuarial.mortality_ratio, 4),
        "risk_tier": state.risk_level.value,
        "pure_premium": round(state.actuarial.pure_premium, 2),
        "expense_loading": round(state.actuarial.expense_loading, 2),
        "commission_loading": round(state.actuarial.commission_loading, 2),
        "profit_loading": round(state.actuarial.profit_loading, 2),
        "contingency_loading": round(state.actuarial.contingency_loading, 2),
        "total_loading": round(state.actuarial.total_loading_amount, 2),
        "gross_annual_premium": round(state.actuarial.gross_premium, 2),
        "gross_monthly_premium": round(state.actuarial.monthly_premium, 2),
        "factor_breakdown": state.actuarial.factor_breakdown,
        "assumption_version": state.actuarial.assumption_version,
        "calculation_notes": state.actuarial.calculation_notes,
    }
