# Agent Orchestration & Frameworks

**Tag**: The "Command Center" / Workflow Engine

---

## Definition

Agent orchestration is the architecture that manages how multiple AI agents interact, make decisions, and execute complex workflows. It defines the "flow" from document intake through risk scoring, review, and final underwriting decision.

## Why Orchestration Matters

Without a framework:
- Agents run independently without coordination
- Data flows are implicit and hard to track
- Humans can't easily inspect where decisions came from
- Scaling to many policies creates bottlenecks
- Regulatory audit becomes a nightmare

With orchestration:
- Clear workflow: Extract → Validate → Price → Review → Decide
- State persists across steps (agent remembers what happened)
- Branching logic routes complex cases to humans
- Full decision trail for compliance
- Reliable failure recovery

## Framework Options

### LangGraph (Recommended)
**Best for**: Structured workflows with clear branching logic, human-in-the-loop integration, observability

**Architecture**:
```
Node (Discrete Agent Task)
  ↓ Edge (Conditional Routing)
  ↓ State (Agent Memory)
  ↓ Branching (If X, then Y; else Z)
```

**Strengths**:
- Graph-based (easy to visualize)
- State management (tracks context across steps)
- Human-in-the-loop (inspection/approval gates)
- Durable execution (survives failures)
- Integrated with LangSmith (debugging)

**For Insurance**: Define underwriting workflow as a graph. See [LangGraph](../sources/langgraph.md).

### Microsoft AutoGen
**Best for**: Conversational multi-agent scenarios where agents negotiate

**Architecture**:
```
Underwriting Agent ←→ Compliance Agent
         ↓
    Group Chat
         ↓
    Consensus Decision
```

**Strengths**:
- Agents talk to each other
- Automatic conflict resolution
- Flexible task delegation

**Limitations**:
- Currently in maintenance mode
- Microsoft recommends Agent Framework for new projects
- Less structured than LangGraph for strict workflows

See [Microsoft AutoGen](../sources/microsoft-autogen.md).

## Your Underwriting Workflow (LangGraph)

```
[START]
  ↓
[EXTRACT: LlamaParse + Claude → JSON medical data]
  ↓
[VALIDATE: Guardrails → Check schema & ranges]
  ↓
[If validation fails] → [CORRECT: Re-extract or flag for manual review]
  ↓
[SCORE: Frequency-Severity GLM → Risk score + premium]
  ↓
[CLASSIFY: Complexity assessment → STP/Review/Underwriter?]
  ↓
[Route Decision]
  ├─ [STP Path: Auto-approve low-complexity] → [Decision: APPROVED]
  ├─ [Review Path: AI recommendation + brief human review] → [Decision: APPROVED/DENIED/REFER]
  └─ [Underwriter Path: Full manual with AI support] → [Decision: APPROVED/DENIED]
  ↓
[STORE: Log decision + audit trail]
  ↓
[END]
```

## State Management

What the "State" holds throughout workflow:

```json
{
  "policy_id": "POL-2026-0001",
  "applicant": {
    "name": "Jane Doe",
    "age": 35
  },
  "extracted_data": {
    "bmi": 24.5,
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "conditions": ["Diabetes Type 2"],
    "medications": ["Metformin"]
  },
  "validation_status": {
    "passed": true,
    "errors": []
  },
  "risk_score": {
    "frequency": 0.08,
    "severity": 5200,
    "total_risk": 416,
    "premium_quoted": 1560
  },
  "complexity_flags": [
    "diabetes_requires_recent_labs"
  ],
  "routing_decision": "human_review",
  "underwriter_decision": null,
  "audit_trail": [
    "2026-04-09 14:32:01 - Extraction completed by Claude",
    "2026-04-09 14:32:15 - Validation passed",
    "2026-04-09 14:32:45 - Risk score calculated",
    "2026-04-09 14:35:10 - Jane Smith (ID: 7421) reviewed and approved"
  ]
}
```

## Observability & Monitoring

**AgentOps** provides visibility into every step:
- Which node executed when?
- What was the state at each step?
- How long did each node take?
- How many tokens used?
- What decisions were made?

This becomes your regulatory audit trail. See [AgentOps](../sources/agentops.md).

## Human-in-the-Loop Integration

**Inspection Points**:
1. After extraction: "Does the extracted data look reasonable?"
2. After validation: "Any concerns about data quality?"
3. After scoring: "Is the risk assessment aligned with medical findings?"
4. At routing: "Should this go to STP or require human review?"

**Approval Gates**:
- Underwriter must approve before policy issued (for non-STP cases)
- Can override AI recommendation with rationale
- All overrides logged

## Workflow Patterns

### Pattern 1: Sequential (Linear)
Extract → Validate → Score → Review → Approve
- Simple, easy to understand
- No branching

### Pattern 2: Conditional (Your Model)
Extract → Validate → {If low-complexity: STP-Approve} | {Else: Review-Underwriter}
- Handles routine vs. complex cases
- Efficient routing

### Pattern 3: Iterative (Correction Loop)
Extract → Validate → {If errors: Re-extract} → {Else: Continue}
- Can ask Claude to re-read PDF
- Improves accuracy over retries

### Pattern 4: Collaborative (Multi-Agent)
Underwriting Agent ↔ Medical Agent ↔ Compliance Agent → Consensus
- Useful if agents specialize
- More complex to implement

**Recommended for your thesis**: Pattern 2 (conditional routing)

## Technology Stack

- **Framework**: LangGraph
- **LLMs**: Claude (extraction, explanation, reasoning)
- **Validation**: Guardrails AI
- **Observability**: AgentOps
- **Database**: DynamoDB (state persistence)
- **Deployment**: AWS Lambda + Step Functions

## Relevance to Thesis

Agent orchestration is the **"Command Center"** that:
1. Directs the entire underwriting workflow
2. Routes cases based on complexity
3. Maintains full decision trail for compliance
4. Integrates human judgment at critical points
5. Scales from dozens to thousands of policies
6. Provides regulators with auditable, reproducible decisions

## Implementation Roadmap

1. ✅ Understand orchestration concepts
2. 📌 Define your workflow graph (nodes and edges)
3. 📌 Build LangGraph prototype
4. 📌 Add validation gates
5. 📌 Integrate AgentOps monitoring
6. 📌 Add human-in-the-loop approval endpoints
7. 📌 Test end-to-end with sample policies

## Related Topics

- [LangGraph](../sources/langgraph.md)
- [Microsoft AutoGen](../sources/microsoft-autogen.md)
- [AgentOps](../sources/agentops.md)
- [Human-in-the-Loop Workflows](./human-in-the-loop.md)
- [Agentic AI & STP](./agentic-ai-stp.md)
- [Agent Safety & Reliability](./agent-safety.md)
