# Agent Harness: Deterministic Phase-Based Workflows

**Last Updated**: 2026-04-09  
**Source**: [AI Automators: Agentic RAG Series — Episode 6](../sources/agentic-rag-series-6-episodes.md)  
**Type**: Architectural Pattern  
**Key Insight**: "The model is commoditized. Structured enforcement of process is the moat."

---

## Overview

An **agent harness** is a state machine that enforces a deterministic workflow while embedding LLM calls at specific phases. Unlike pure agent loops (where the LLM decides what to do next), a harness dictates the sequence of operations and what LLM capabilities are available at each phase.

**Core Principle**: Constrain LLM creativity within "boxes" (phases) with clear entry/exit conditions, deterministic validation gates, and explicit state transitions.

---

## Problem It Solves

**Pure Agent Loop Issues**:
- Unpredictable execution (LLM decides flow, may retry indefinitely)
- Context bloat (full system prompt every round)
- Hard to resume (no clear phase boundaries)
- Hard to debug (non-deterministic flow)
- Hard to explain to users (opaque decision-making)
- Hard to enforce constraints (LLM might ignore guardrails)

**Harness Solution**:
- Predictable execution (system dictates flow)
- Scoped context (only relevant info per phase)
- Resumable (clear phase boundaries with state snapshots)
- Debuggable (transparent phase progression)
- Explainable (users see each phase completing)
- Enforced constraints (system can block invalid transitions)

---

## Phase Types: Five Core Patterns

### 1. Programmatic Phase
**What**: Pure Python, no LLM. Deterministic logic.  
**Use Cases**: File I/O, data transformation, calling APIs, validation  
**Example**: "Load PDF, extract text, validate file size"

```python
@harness.phase("intake_document")
def intake(input_file: str) -> dict:
    # No LLM, pure computation
    pdf_content = load_pdf(input_file)
    if len(pdf_content) == 0:
        raise ValueError("PDF is empty")
    return {"pdf_text": pdf_content, "status": "ready"}
```

**Benefits**:
- No hallucinations (pure logic)
- Reproducible (same input = same output)
- Fast (no API calls)
- Auditable (clear data transformations)

---

### 2. LLM Single Phase
**What**: One LLM call with structured output (JSON schema).  
**Use Cases**: Classification, extraction, decision-making  
**Example**: "Classify contract type" → returns `{"type": "NDA", "confidence": 0.95}`

```python
@harness.phase("classify_document")
def classify(pdf_text: str) -> dict:
    schema = {
        "type": ["NDA", "Service", "Licensing", "Employment"],
        "confidence": float,
        "reasoning": str
    }
    
    result = claude.call_structured(
        prompt=f"Classify this document: {pdf_text[:5000]}",
        output_schema=schema
    )
    return result
```

**Benefits**:
- Deterministic output (JSON schema enforced)
- Single round (fast, no iteration)
- Clear success/failure criteria
- Low token usage

**Important**: Output **must** conform to schema, or phase fails and escalates.

---

### 3. LLM Agent Phase
**What**: Multi-round agentic loop with tools (like a mini-agent inside the phase).  
**Use Cases**: Complex extraction, problem-solving with iteration  
**Example**: "Extract medical fields" with retry logic, validation feedback

```python
@harness.phase("extract_medical_fields")
def extract(pdf_text: str, max_retries: int = 2) -> dict:
    # Mini-agent loop within this phase
    for attempt in range(max_retries):
        result = agent_loop(
            goal="Extract medical fields: age, BMI, blood pressure, conditions",
            context=pdf_text,
            tools=[lookup_lab_range, lookup_condition_criteria],
            max_turns=5  # Scoped: max 5 turns, not unlimited
        )
        
        validation = validate_extraction(result)
        if validation.passed:
            return result
        
        # Retry with validation feedback
        pdf_text += f"\n\nValidation feedback: {validation.errors}"
    
    # If still failing after retries, escalate
    raise PhaseFailure("Could not extract medical fields after retries")
```

**Key Differences from Pure Agent**:
- Scoped subtask (extract medical, not "solve the problem")
- Limited iterations (max 2-5 rounds, not infinite)
- Clear success criteria (validation must pass)
- Deterministic fallback (escalate on failure)

**Benefits**:
- Flexible (agent adapts to document variation)
- Bounded (can't loop forever)
- Observable (clear failure modes)

---

### 4. LLM Batch Agents Phase
**What**: Parallel sub-agents, each handling a scoped subtask.  
**Use Cases**: Analyzing multiple items independently (risk clauses, medical conditions, etc.)  
**Example**: "Analyze 5 risk clauses in parallel"

```python
@harness.phase("risk_analysis_parallel")
def analyze_risks(clauses: list[str]) -> dict:
    # Spawn 5 concurrent agents, one per clause
    tasks = [
        agent.analyze_clause(
            clause=clause,
            tools=[risk_database, precedent_lookup],
            constraints="Return JSON: {risk_level, justification, examples}"
        )
        for clause in clauses
    ]
    
    # Wait for all to complete (with timeout)
    results = await asyncio.gather(*tasks, timeout=30)
    
    # Aggregate results
    return {"clause_risks": results, "status": "complete"}
```

**Benefits**:
- Parallelization (5 agents × 6 seconds = 6 seconds, not 30 seconds)
- Isolation (each agent works independently, no interference)
- Scalability (can spawn 10+ agents for 100+ items)
- Deterministic results (each agent has same constraints)

**Constraints**:
- Agents must be independent (no inter-agent communication)
- Timeout enforcement (kill hanging agents)
- Result aggregation (combine N results into one)

---

### 5. LLM Human Input Phase
**What**: Pause workflow to gather context from user.  
**Use Cases**: Collecting requirements, clarifications, preferences  
**Example**: "Ask user: What's your risk tolerance before proceeding?"

```python
@harness.phase("gather_context")
def gather_context(document_summary: str) -> dict:
    # Pause and ask user
    user_input = await harness.ask_user({
        "question1": "What's your risk tolerance? (low/medium/high)",
        "question2": "Any special considerations?",
        "question3": "Timeline for decision?"
    })
    
    # Validate and return
    return {
        "risk_tolerance": user_input["question1"],
        "special_considerations": user_input["question2"],
        "timeline": user_input["question3"]
    }
```

**Benefits**:
- Grounds AI in human context (not operating in vacuum)
- Captures preferences (user can steer outcome)
- Transparent (user knows when they're needed)

**Important**: Phase pauses until user responds (synchronous).

---

## Harness Workflow: Example (Medical Underwriting)

```
[Start]
    ↓
[Phase 1: Programmatic] Intake applicant PDF
    Input: file.pdf
    Output: {pdf_text: "...", file_hash: "xyz"}
    ↓
[Phase 2: LLM Single] Classify document type
    Input: pdf_text
    Output: {type: "medical_form", confidence: 0.98}
    ↓
[Phase 3: LLM Human Input] Gather context
    Input: document_summary
    Output: {returning_applicant: true, special_conditions: "diabetes"}
    ↓
[Phase 4: Programmatic] Fetch medical reference data
    Input: document_type, special_conditions
    Output: {lab_ranges: {...}, condition_criteria: {...}}
    ↓
[Phase 5: LLM Agent] Extract medical fields (max 2 retries)
    Input: pdf_text, lab_ranges, medical_conditions
    Output: {age: 45, BMI: 24.5, conditions: [...], confidence: 0.92}
    ↓
[Phase 6: Programmatic] Validate extracted data
    Input: extracted_data
    Output: {valid: true, flags: []}
    ↓
[Phase 7: Programmatic] Run GLM pricing
    Input: extracted_data
    Output: {risk_score: 0.15, premium: 450, tier: "STANDARD"}
    ↓
[Phase 8: LLM Single] Generate explanation + routing
    Input: extraction, pricing, flags
    Output: {decision: "APPROVE", explanation: "...", route: "STP"}
    ↓
[Phase 9: Programmatic] Create audit trail
    Input: all_phase_outputs
    Output: audit_log.json
    ↓
[Complete] → User sees progress + result

```

---

## Workspace Artifacts: Phase State Management

Each phase produces outputs that become inputs to subsequent phases. This enables **resumability** and **auditability**.

### Example: Contract Review Harness (8 phases)

```
Phase 1 → intake.json
Phase 2 → classification.json
Phase 3 → user_context.json
Phase 4 → standards.md
Phase 5 → clauses_extracted.json
Phase 6 → risk_analysis.json (5 sub-agent results)
Phase 7 → redlines.json
Phase 8 → report.docx
```

**Benefits**:
- **Resumability**: If Phase 8 fails, restart Phase 8 with Phase 7's output
- **Debugging**: See exact inputs/outputs of each phase
- **Auditability**: Full trace of transformation from input → output
- **Parallelization**: Later phases could read earlier phases' artifacts

**Storage Strategy**:
- Store artifacts in workspace (filesystem or database)
- Keyed by execution_id (same case can run multiple times)
- Retention: Keep for audit period (e.g., 7 years for insurance)

---

## Harness vs. Other Patterns

### Harness vs. Blueprint (Stripe)

| Aspect | Harness (AI Automators) | Blueprint (Stripe) |
|--------|---|---|
| **Flow** | Sequential phases | Mixed deterministic + agentic nodes |
| **LLM Control** | System dictates flow | Nodes iterate, can call tools |
| **Iteration** | Max retries per phase | LLM decides within node |
| **State** | Artifacts per phase | State object flows through |
| **Use Case** | Structured workflows | Creative problem-solving |
| **Resume** | Yes (clear phase boundaries) | Yes (state snapshots) |

**When to use Harness**:
- Well-defined workflow (intake → extract → validate → decide)
- Need clear progress reporting
- Want explicit human input points
- Require phase-level resumability

**When to use Blueprint**:
- Flexible problem-solving (extraction + retry with feedback)
- Complex iteration patterns
- Agent needs autonomy within constraints
- Less structured requirements

---

## Implementation Considerations

### 1. Phase Boundaries
- Each phase has **clear entry condition** (what must exist to start)
- Each phase has **clear exit condition** (what must exist to complete)
- Transitions are explicit, not inferred

```python
phase_intake: 
  entry_condition: file_exists(input_file)
  exit_condition: valid_json(intake_output)

phase_classify:
  entry_condition: phase_intake.completed and output exists
  exit_condition: classification matches allowed types
```

### 2. Error Handling
- **Recoverable errors**: Retry within phase (with feedback)
- **Non-recoverable errors**: Escalate (fail phase, notify user)
- **Timeout errors**: Kill phase, escalate

```python
try:
    result = phase_extract(...)
except ValidationError:
    # Recoverable: retry with feedback
    retry_count += 1
except TimeoutError:
    # Non-recoverable: escalate
    escalate_to_human()
except Exception:
    # Unknown: log and escalate
    log_error_and_escalate()
```

### 3. Scoped Tools & Context
- Each LLM phase has curated tools (not all 100 tools)
- System prompt focused on phase goal (not full architecture)
- Reduces context window, improves accuracy

```python
phase_extract:
  tools: [lookup_lab_range, lookup_condition_criteria, validate_field]
  system_prompt: "Extract medical fields. Use tools for validation."
  model: Claude 3.5 Sonnet (cheaper for single-turn)

phase_agent:
  tools: [lookup_lab_range, lookup_condition_criteria, search_medical_literature]
  system_prompt: "Extract medical fields with iterative validation..."
  model: Claude 3.5 Sonnet (with agent capabilities)
```

### 4. Parallelization
- Independent phases can run in parallel (with dependencies)
- Batch agent phase parallelizes sub-agents (5-100 concurrent)
- Use async/await for I/O-bound operations

```python
# Sequential: Phase 1 → Phase 2 → Phase 3
async def run_harness():
    phase1_result = await run_phase_1()
    phase2_result = await run_phase_2(phase1_result)
    phase3_result = await run_phase_3(phase2_result)

# Parallel batch within Phase 3
async def batch_analysis(items):
    tasks = [analyze_item(item) for item in items]
    return await asyncio.gather(*tasks)
```

---

## Questions to Answer During Implementation

1. **How many phases?** (5-10 typical)
2. **Where is human input needed?** (Phase 3 pattern)
3. **Which phases are LLM-driven vs. programmatic?**
4. **What are failure modes for each phase?** (validation error → retry vs. escalate)
5. **How long should each phase timeout?** (30 sec? 5 min?)
6. **Should artifacts be persisted?** (filesystem? database? S3?)
7. **How to handle concurrent harness runs?** (per-applicant isolation)

---

## References

- [AI Automators: Agentic RAG Series — Episode 6](../sources/agentic-rag-series-6-episodes.md) — Full harness pattern + contract review example
- [Blueprint Orchestration Pattern](./blueprint-orchestration-pattern.md) — Stripe's approach (deterministic + agentic mixing)
- [Agent Context Engineering at Scale](./agent-context-engineering-at-scale.md) — Scoped context per phase
