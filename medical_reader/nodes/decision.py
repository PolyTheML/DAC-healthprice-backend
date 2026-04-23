"""
Decision Node: Set final approval/rejection status.

Based on the review outcome (STP vs human review), sets the final
case status and updates the state accordingly.
"""

from ..state import UnderwritingState, RiskLevel


def decision_node(state: UnderwritingState) -> UnderwritingState:
    """
    Final decision node: Set case status to approved or declined.

    Routing logic:
    1. DECLINE risk level → always declined (regardless of review decision)
    2. STP path (no human review) → auto-approved
    3. HITL path → use reviewer's decision (review.approved)

    Args:
        state: UnderwritingState with review decision captured
               (either review.required=False for STP, or review.approved set by HITL)

    Returns:
        Updated UnderwritingState with final status set
    """

    # Check for automatic decline (uninsurable risk)
    if state.risk_level == RiskLevel.DECLINE:
        state.status = "declined"
        state.add_audit_entry(
            node="decision",
            action="auto_declined_high_risk",
            details={"risk_level": "DECLINE", "risk_score": state.risk_score},
            confidence=1.0,
        )
        return state

    # Check STP path (no human review needed)
    if not state.review.required:
        state.status = "approved"
        state.add_audit_entry(
            node="decision",
            action="auto_approved_stp",
            details={"risk_score": state.risk_score},
            confidence=state.overall_confidence,
        )
        return state

    # HITL path: use reviewer's decision
    if state.review.approved:
        state.status = "approved"
        state.add_audit_entry(
            node="decision",
            action="approved_by_reviewer",
            details={"reviewer_id": state.review.reviewer_id},
            confidence=1.0,
        )
    else:
        state.status = "declined"
        state.add_audit_entry(
            node="decision",
            action="declined_by_reviewer",
            details={"reviewer_id": state.review.reviewer_id},
            confidence=1.0,
        )

    return state
