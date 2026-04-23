"""
Human-In-The-Loop (HITL) Node: Pause for human review and decision.

Uses LangGraph's interrupt() mechanism to pause execution and wait for
a human underwriter to make an approval/rejection decision.

The reviewer's decision is captured and returned to resume the workflow.
"""

from datetime import datetime
from langgraph.types import interrupt

from ..state import UnderwritingState


def hitl_node(state: UnderwritingState) -> UnderwritingState:
    """
    HITL checkpoint: Pause execution and wait for human review.

    This node triggers an interrupt that pauses the workflow execution.
    The Streamlit UI captures the case and presents it to a human reviewer.
    When the reviewer submits an approval/rejection decision, the graph
    is resumed with submit_review() and executes from this point.

    Args:
        state: UnderwritingState with extraction and pricing complete,
               review.required = True, awaiting human decision

    Returns:
        Updated UnderwritingState with reviewer decision captured

    The interrupt is resumed with a dict containing:
        {
            "approved": bool,
            "notes": str (reviewer's notes),
            "reviewer_id": str (underwriter's ID),
        }
    """

    # Prepare summary for reviewer
    reviewer_context = {
        "case_id": state.case_id,
        "risk_level": state.risk_level.value,
        "risk_score": state.risk_score,
        "review_reason": state.review.reason,
        "missing_fields": state.extracted_data.missing_fields(),
        "errors": state.errors,
        "summary": state.to_summary(),
    }

    # Trigger interrupt: execution pauses here
    # The graph returns the state at this point
    # Streamlit UI shows the case to a reviewer
    # When reviewer submits decision, graph.invoke() is called with Command(resume=decision)
    reviewer_input = interrupt(reviewer_context)

    # Resume point: reviewer_input contains approval decision
    state.review.approved = reviewer_input["approved"]
    state.review.reviewer_notes = reviewer_input.get("notes", "")
    state.review.reviewer_id = reviewer_input.get("reviewer_id", "unknown")
    state.review.timestamp = datetime.utcnow()

    # Log the review decision in audit trail
    state.add_audit_entry(
        node="hitl",
        action="human_review_completed",
        details={
            "approved": reviewer_input["approved"],
            "notes": reviewer_input.get("notes", ""),
            "reviewer_id": reviewer_input.get("reviewer_id", "unknown"),
        },
        confidence=1.0,  # Human review has perfect confidence
    )

    return state
