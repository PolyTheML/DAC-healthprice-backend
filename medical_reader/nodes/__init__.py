"""
Workflow nodes for the medical underwriting agent.

Each node processes the UnderwritingState and returns an updated state.
Used in LangGraph workflow orchestration.

Available nodes:
- intake_node: Extract medical data from PDF using Claude Vision
- pricing_node: Generic life pricing (kept for backwards compatibility)
- life_pricing_node: Cambodia-specific life insurance pricing with risk adjustments
- review_node: Determine if case requires human review (with SHAP-style trace)
- hitl_node: Human-in-the-loop pause/resume
- decision_node: Final approve/decline decision
"""

from .intake import intake_node
from .pricing import pricing_node
from .life_pricing import life_pricing_node
from .review import review_node
from .hitl import hitl_node
from .decision import decision_node

__all__ = ["intake_node", "pricing_node", "life_pricing_node", "review_node", "hitl_node", "decision_node"]
