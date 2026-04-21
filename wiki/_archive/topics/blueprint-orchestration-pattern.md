# Blueprint Pattern: Deterministic + Agentic Orchestration

**Last Updated**: 2026-04-09  
**Source**: [Stripe Minions: One-Shot Agentic Coding](../sources/stripe-minions-agentic-coding.md)  
**Type**: Architectural Pattern  

---

## Overview

The **blueprint pattern** is a workflow orchestration approach that combines deterministic code nodes with agentic (LLM-driven) nodes to achieve both reliability and flexibility at scale.

Core principle: **"Putting LLMs into contained boxes" compounds reliability.**

---

## Pattern Structure

### Deterministic Nodes
- Fixed behavior: always execute the same logic
- No LLM calls
- Examples: linting, type checking, git operations, data validation, pushing code, creating audit logs
- **Purpose**: Guarantee critical steps complete; save tokens; reduce failure modes

### Agentic Nodes
- LLM-driven with full tool access
- Creative problem-solving within a scoped task
- Examples: "Implement feature", "Debug test failure", "Extract medical data from document"
- **Purpose**: Handle complexity, context-dependency, novel situations

### The Mix
A blueprint alternates deterministic and agentic nodes in a state machine graph:

```
1. [Deterministic] Initialize: load task, prepare context
   ↓
2. [Agentic] Implement: LLM writes code/solves problem
   ↓
3. [Deterministic] Lint: run auto-formatter, style checks
   ↓
4. [Agentic] Fix lint failures: if LLM-solvable, iterate
   ↓
5. [Deterministic] Push: commit and run tests
   ↓
6. [Agentic] Debug failures: if test-solvable, iterate (max 2 rounds)
   ↓
7. [Deterministic] Create PR: finalize and request review
```

---

## Why This Pattern Works

### Reliability at Scale
- **Deterministic steps guarantee completion**: Linting always runs, tests always run, decisions always logged
- **Contained agentic loops**: Agents only decide within their box (e.g., "fix lint errors", not "redesign system")
- **Failure is bounded**: If agent loop fails, falls back to deterministic path (human review, escalation)

### Token Efficiency
- Pre-push linting catches issues before expensive LLM debugging
- Deterministic validation prevents wasted tokens on invalid solutions
- "Shift feedback left" means fast, cheap feedback before expensive CI

### Context Engineering
- Each node sees only relevant context (rule files for current task, MCP tools for current problem)
- Nodes don't need global context; they have task-specific context
- Reduces context window bloat

### Parallelization
- Multiple blueprints can run independently (isolated execution environments)
- Deterministic steps scale horizontally (linting, validation are parallelizable)
- Agentic subtasks scale with LLM API (concurrent agent calls)

---

## Application to DAC-UW-Agent: Four-Layer Blueprint

### Layer 1: Core Engine (Deterministic)
- **Node**: Frequency-Severity GLM Pricing
- **Behavior**: Always calculate premium same way; no LLM
- **Input**: Extracted medical data (age, BMI, conditions, medical history)
- **Output**: Risk score, premium, confidence bound
- **Why deterministic**: Actuaries must own pricing logic; regulators require reproducibility

### Layer 2: AI Layer (Mixed)
- **Node 2a (Agentic)**: Extract medical data from PDF
  - LLM with Claude Vision, document understanding tools
  - Goal: Parse PDF → valid medical JSON
  - Scoped context: Medical rule file, validation constraints
  
- **Node 2b (Deterministic)**: Validate extracted data
  - Schema validation (Pydantic types)
  - Domain validation (physiological ranges, lab value norms)
  - Consistency validation (if diabetes, must have glucose lab)
  - Output: Validation report (pass/fail/warnings)

- **Node 2c (Agentic, conditional)**: Re-extract if validation fails
  - If validation fails + confidence < 0.8, re-attempt extraction
  - Provide validation feedback to LLM ("Blood pressure out of range, re-read form")
  - Max 2 retries

### Layer 3: Control Layer (Mixed)
- **Node 3a (Deterministic)**: Route based on complexity
  - STP threshold: If confidence > 0.95 + all validations pass → straight-through
  - Human review threshold: If confidence 0.7-0.95 OR complex case → flag for human
  - Reject threshold: If confidence < 0.5 OR unmappable document → reject
  
- **Node 3b (Agentic, conditional)**: Human review recommendations
  - If routed to human review: Generate explainability (why this case is complex)
  - Suggest underwriter checklist
  - Provide precedent cases (from RAG)

### Layer 4: Trust Layer (Deterministic)
- **Node 4a (Deterministic)**: Create immutable audit log
  - Record: decision, confidence, validation flags, route (STP/human/reject)
  - Record: timestamp, user, approval/denial
  - Output: Audit record for Cambodia IRC compliance
  
- **Node 4b (Deterministic)**: Explainability record
  - GLM coefficient contributions (SHAP values)
  - Data lineage (which PDF, which extraction attempt)
  - Why this risk tier?

---

## Pattern in Pseudocode (LangGraph-Ready)

```python
# Pseudocode: Medical underwriting blueprint

class UnderwritingBlueprint:
    
    def initialize(self, applicant_pdf):
        """Deterministic: Load PDF, extract metadata"""
        return {"pdf": applicant_pdf, "attempt": 1}
    
    def extract(self, state):
        """Agentic: Call Claude Vision to extract medical data"""
        extracted = agent.extract_medical_data(
            pdf=state["pdf"],
            context=rule_files["medical_extraction"],
            tools=mcp_tools["medical_reference"]
        )
        state["extracted"] = extracted
        state["confidence"] = extracted.get("confidence", 0.0)
        return state
    
    def validate(self, state):
        """Deterministic: Run 3-layer validation"""
        result = validator.validate(state["extracted"])
        state["validation"] = result
        state["is_valid"] = result.pass_all_checks
        return state
    
    def price(self, state):
        """Deterministic: Run GLM pricing"""
        if not state["is_valid"]:
            state["price"] = None
            return state
        
        pricing = glm_model.predict(state["extracted"])
        state["risk_score"] = pricing["risk_score"]
        state["premium"] = pricing["premium"]
        return state
    
    def route(self, state):
        """Deterministic: Decide STP vs. human review vs. reject"""
        conf = state["confidence"]
        valid = state["is_valid"]
        
        if conf > 0.95 and valid:
            state["route"] = "STP"
        elif conf > 0.5 and valid:
            state["route"] = "HUMAN_REVIEW"
        else:
            state["route"] = "REJECT"
        return state
    
    def explain(self, state):
        """Agentic (conditional): If routed to human review, generate explanation"""
        if state["route"] != "HUMAN_REVIEW":
            return state
        
        explanation = agent.explain_case(
            state=state,
            context=rule_files["compliance"],
            tools=mcp_tools["actuarial_reference"]
        )
        state["explanation"] = explanation
        return state
    
    def audit_log(self, state):
        """Deterministic: Create immutable audit record"""
        audit = {
            "decision": state["route"],
            "confidence": state["confidence"],
            "premium": state.get("premium"),
            "validation_flags": state["validation"].flags,
            "timestamp": now(),
            "reason": state.get("explanation"),
            "data_lineage": {
                "pdf": state["pdf"],
                "extraction_attempt": state.get("attempt", 1)
            }
        }
        state["audit"] = audit
        return state

# Blueprint orchestration
blueprint = UnderwritingBlueprint()
state = {}
state = blueprint.initialize(applicant_pdf)
state = blueprint.extract(state)
state = blueprint.validate(state)

if not state["is_valid"] and state["attempt"] < 2:
    # Agentic retry
    state["attempt"] += 1
    state = blueprint.extract(state)  # Try again with feedback
    state = blueprint.validate(state)

state = blueprint.price(state)
state = blueprint.route(state)
state = blueprint.explain(state)
state = blueprint.audit_log(state)

return state
```

---

## Key Principles

### 1. **Determinism at Boundaries**
- Start: Load task, prepare context (deterministic)
- End: Log decision, create audit trail (deterministic)
- Prevents ambiguity at critical points

### 2. **Agentic Loops Are Scoped**
- Agents never have unlimited retries
- Max 2 iterations per loop (matches Stripe pattern)
- Clear success/failure criteria
- Fallback to human review if agent fails

### 3. **Context Flows Through State**
- State object carries all information
- Each node reads what it needs, adds what it produces
- Immutable updates (return new state, don't mutate)
- Enables reproducibility and debugging

### 4. **Validation Between Layers**
- Every agentic output validated before next layer
- Failures halt progress and route to human/reject
- No silent failures

### 5. **Fast Feedback Comes Early**
- Linting (fast, deterministic) before testing (slow)
- Validation (deterministic) before pricing (deterministic but downstream)
- Schema validation before domain validation (cheaper first)

---

## Comparison to Other Patterns

### Workflows vs. Blueprints
- **Workflows**: Fixed DAG (Directed Acyclic Graph), all paths predetermined
- **Blueprints**: Fixed graph structure with conditional branching + agentic subtasks
- **Blueprint advantage**: More flexible than workflow (agentic nodes adapt), more structured than pure agent loop

### Pure Agent Loops vs. Blueprints
- **Pure agents**: Decide what to do next at each step (full autonomy, unpredictable)
- **Blueprints**: Agent decides within its box, blueprint decides next box (structure + flexibility)
- **Blueprint advantage**: Deterministic guarantee steps happen, more token-efficient

### Blueprints vs. Multi-Agent Collaboration
- **Multi-agent**: Multiple agents negotiate and decide
- **Blueprints**: One agent per scoped task, orchestrator decides flow
- **Blueprint advantage**: Simpler debugging, clearer responsibility, easier to test

---

## Building a Blueprint: Checklist

1. **Identify deterministic steps**: What must always happen? (logging, validation, pushing)
2. **Identify agentic tasks**: What requires creativity/adaptation? (extraction, explanation, debugging)
3. **Order the nodes**: Determinism at start/end; agentic in middle with deterministic validation after
4. **Define state**: What data flows between nodes?
5. **Define success criteria**: When does a node succeed? When does it fail and escalate?
6. **Set iteration limits**: Max retries for agentic loops (usually 2)
7. **Add fallback**: What happens if agentic node fails? (human review, escalation, rejection)
8. **Log everything**: Every node adds to audit trail

---

## References

- [Stripe Minions: One-Shot Agentic Coding](../sources/stripe-minions-agentic-coding.md) — Original blueprint pattern
- [Medical Underwriting Orchestration](./medical-underwriting-orchestration.md) — DAC-UW-Agent implementation
- [Agent Orchestration & Frameworks](./agent-orchestration.md) — LangGraph state machine primitives
