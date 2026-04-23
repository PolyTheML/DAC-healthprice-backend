"""
LangGraph orchestration for medical underwriting workflow.

Implements a StateGraph with:
- 5 nodes: intake, pricing, review, hitl (human-in-the-loop), decision
- Conditional routing based on review requirements
- MemorySaver checkpointing for persistence and resumption
- Public API for running and resuming workflows
"""

from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from medical_reader.state import UnderwritingState
from medical_reader.nodes import intake_node, pricing_node, review_node
from medical_reader.nodes.hitl import hitl_node
from medical_reader.nodes.decision import decision_node


def route_after_review(state: UnderwritingState) -> str:
    """Conditional routing after review node.

    If human review is required, route to HITL node.
    Otherwise, proceed directly to decision node.
    """
    if state.review.required:
        return "hitl"
    else:
        return "decision"


def create_underwriting_graph():
    """Create and compile the underwriting workflow graph.

    Returns:
        Compiled graph ready for invocation.
    """
    graph = StateGraph(UnderwritingState)

    # Add nodes
    graph.add_node("intake", intake_node)
    graph.add_node("pricing", pricing_node)
    graph.add_node("review", review_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("decision", decision_node)

    # Add edges
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "pricing")
    graph.add_edge("pricing", "review")
    graph.add_conditional_edges("review", route_after_review)
    graph.add_edge("hitl", "decision")
    graph.add_edge("decision", END)

    # Compile with MemorySaver checkpointer (in-memory, keyed by thread_id)
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


def thread_config(case_id: str) -> dict:
    """Create thread configuration for a case.

    Used for checkpointing and resumption.
    Each case_id maps to a unique thread_id.
    """
    return {"configurable": {"thread_id": case_id}}


# Global compiled graph instance
_graph = None


def get_graph():
    """Get or create the compiled graph.

    Returns:
        Compiled LangGraph StateGraph instance.
    """
    global _graph
    if _graph is None:
        _graph = create_underwriting_graph()
    return _graph


def run_case(case_id: str, pdf_path: str) -> UnderwritingState:
    """Run a case through the underwriting workflow.

    Executes the full workflow until completion or interrupt (HITL).

    Args:
        case_id: Unique case identifier (used for checkpointing)
        pdf_path: Path to the PDF document

    Returns:
        UnderwritingState at current point
        - If no review required: final approved/declined state
        - If review required: paused at HITL node (awaiting human input)

    Raises:
        ValueError: If PDF not found
        Exception: If extraction or processing fails
    """
    graph = get_graph()
    config = thread_config(case_id)

    initial_state = UnderwritingState(
        case_id=case_id,
        source_document_path=pdf_path,
    )

    # Run the workflow
    # graph.invoke returns a dict, but the state is already an UnderwritingState
    # that was modified by the nodes. We pass it through the graph and get it back.
    result = graph.invoke(initial_state.model_dump(), config=config)

    # Reconstruct UnderwritingState from the result dict
    return UnderwritingState(**result)


def submit_review(
    case_id: str,
    approved: bool,
    notes: str,
    reviewer_id: str
) -> UnderwritingState:
    """Submit a human review decision and resume the workflow.

    Used when a case is paused at the HITL node awaiting review.
    Resumes execution from the interrupt with the reviewer's decision.

    Args:
        case_id: Case ID (must match case_id from run_case call)
        approved: Whether the underwriter approved the case
        notes: Reviewer's notes or reason for decision
        reviewer_id: ID of the reviewer (for audit trail)

    Returns:
        Final UnderwritingState after completing decision and subsequent nodes

    Raises:
        Exception: If case not found or not in review state
    """
    graph = get_graph()
    config = thread_config(case_id)

    reviewer_input = {
        "approved": approved,
        "notes": notes,
        "reviewer_id": reviewer_id,
    }

    # Resume from interrupt with the decision
    result = graph.invoke(
        Command(resume=reviewer_input),
        config=config
    )

    # Reconstruct UnderwritingState from the result dict
    return UnderwritingState(**result)
