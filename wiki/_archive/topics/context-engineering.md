# Context Engineering: Strategic Information Flow

**Created**: 2026-04-17 | **Last updated**: 2026-04-17

## Definition

**Context engineering** is the practice of deciding:

1. **What information to store** (persistent artifacts, ledgers, state)
2. **What to retrieve** (on each agent invocation)
3. **What to present** (in the prompt context window)

These decisions span prompt phrasing, tool invocation sequences, artifact formats, state persistence conventions, and verification logic. Together they determine harness performance.

## The Context Engineering Perspective

Per [Building Effective Agents](../sources/2026-04-17_anthropic-building-effective-agents.md) and [Meta-Harness](../sources/2026-04-17_meta-harness-optimization.md):

Modern agent systems are not primarily constrained by model capability; they are constrained by **how effectively we engineer the context** around the model.

- Prompt phrasing is context engineering
- Tool design is context engineering
- State persistence conventions are context engineering
- Artifact formatting is context engineering
- Verification strategies are context engineering

Treating these as a **unified optimization problem** (not separate concerns) unlocks **6× performance gains**.

## Three Layers of Context Engineering

### Layer 1: Information Architecture

**Decision**: What does the agent need to know to take the next action?

Examples:
- **For intake form routing**: Policy type, applicant demographics, risk factors
- **For pricing decisions**: Policy type, health data, prior claims, competitor benchmarks
- **For underwriting review**: Pricing result, underwriting rules, exception thresholds

**Trade-off**: Including more information reduces hallucination but increases token cost.

### Layer 2: Artifact Design

**Decision**: How to format and store persistent information?

Examples:
- **JSON vs. YAML**: JSON is more common in training data; YAML is more human-readable
- **Flat vs. nested**: Nested structures reduce duplication; flat structures are easier to parse
- **Versioning**: Store artifact versions to enable rollback and comparison

**Trade-off**: Complex artifact formats reduce hallucination but increase engineering overhead.

### Layer 3: Retrieval Strategy

**Decision**: When and how to fetch information from persistent storage?

Examples:
- **Eager loading**: Fetch all state on session startup (simpler, more tokens)
- **Lazy loading**: Fetch state only when needed (complex, fewer tokens)
- **Adaptive loading**: Fetch based on task type (e.g., include pricing results only for decision stage)

**Trade-off**: Lazy loading saves tokens but requires metadata and routing logic.

## Context Optimization in Meta-Harness

Per [Meta-Harness](../sources/2026-04-17_meta-harness-optimization.md), the system automates context engineering by:

1. **Proposing changes** to information architecture (what to store/retrieve)
2. **Suggesting artifact format improvements** (JSON schema, field names, nesting)
3. **Discovering optimal retrieval strategies** (what to fetch on each call)

**Key finding**: Selective exposure of execution traces (only showing failed examples, not all traces) achieves **4× token reduction** while improving performance.

### Why Full Diagnostic History Matters

Practitioners often compress feedback into aggregate scores:
- ❌ "Your harness achieved 75% accuracy"
- ✅ "Your harness failed on 5 test cases due to JSON parsing errors; failed on 3 due to timeout; succeeded on 92"

Full diagnostic history enables:
- **Selective context**: Show only relevant failures (parsing errors) when proposing fixes
- **Evidence-backed edits**: "I'm changing the JSON parser because these 5 cases failed due to parsing"
- **Iterative refinement**: Learn from each failure to propose targeted improvements

## State Semantics: Persistence & Reopening

Critical context engineering decision: **How does state persist across sessions?**

Per [Effective Harnesses for Long-Running Agents](../sources/2026-04-17_anthropic-effective-harnesses-long-running-agents.md) and [Natural-Language Agent Harnesses](../sources/2026-04-17_natural-language-agent-harnesses.md):

### Structured Persistence

Use explicit formats (JSON, manifests) not ephemeral memory:

```json
{
  "session_id": "sess-2026-04-17-001",
  "artifacts": [
    {
      "name": "intake_form",
      "path": "data/intake_form.json",
      "created": "2026-04-17T10:00:00Z",
      "version": 1
    },
    {
      "name": "pricing_result",
      "path": "data/pricing_result.json",
      "created": "2026-04-17T10:05:00Z",
      "version": 1
    }
  ],
  "ledger": [
    {"timestamp": "2026-04-17T10:00:00Z", "action": "intake_form_submitted", "result": "success"},
    {"timestamp": "2026-04-17T10:05:00Z", "action": "pricing_executed", "result": "success"}
  ]
}
```

### Manifest-Based Reopening

On new session, agent reads manifest to reconstruct state:
1. List all artifacts (what exists?)
2. Load in order (intake → pricing → decision)
3. Validate consistency (pricing assumptions match intake data?)
4. Resume from last incomplete step

## Thesis Application

Your stress-testing framework uses context engineering:

1. **Information architecture**: What the test harness needs to know
   - Synthetic portfolio (structure, risk factors)
   - Failure modes to inject (parsing errors, timeouts, conflicting data)
   - Success criteria (failures detected, performance under stress)

2. **Artifact design**: How to store experimental state
   ```json
   {
     "experiment": "EXP-001",
     "synthetic_portfolio": "data/portfolio_seed_42.parquet",
     "failure_modes": ["parsing_error", "timeout", "conflicting_data"],
     "results": {
       "failures_detected": 27,
       "detection_rate": 0.97,
       "execution_time_sec": 42.3
     }
   }
   ```

3. **Retrieval strategy**: What each stage needs
   - Setup stage: Fetch portfolio definition
   - Inject failures stage: Fetch failure modes
   - Interpret results stage: Fetch results, classify by type

## DAC Application

DAC's multi-stage underwriting applies context engineering across workers:

1. **Information architecture per stage**:
   - **Intake**: Applicant demographics, health history, coverage needs
   - **Pricing**: Policy type, health data, risk factors, benchmarks
   - **Decision**: Pricing result, underwriting rules, exception thresholds
   - **Review**: Full application, pricing, decision, any exceptions

2. **Artifact design**:
   ```json
   {
     "intake_form": {...},
     "pricing_result": {
       "monthly_premium": 125.00,
       "risk_score": 8.5,
       "assumptions": {...}
     },
     "underwriting_decision": {
       "status": "approved",
       "exceptions": [],
       "reviewed_at": "2026-04-17T11:00:00Z"
     }
   }
   ```

3. **Retrieval strategy**:
   - Intake stage loads form
   - Pricing stage retrieves form + pricing benchmarks
   - Decision stage retrieves pricing result + rules
   - Review stage retrieves all prior artifacts

## Connection to Harness Architecture

Context engineering is the **tactical implementation** of [Harness Architecture and Design](./harness-architecture-and-design.md):

- **Contracts** (NLAH) specify what information must be validated
- **State semantics** (NLAH) declare what persists
- **Context engineering** (this topic) decides how to implement state persistence and retrieval

---

**See also**:
- [Harness Architecture and Design](./harness-architecture-and-design.md) — Conceptual framework
- [Runtime Orchestration and Tool Mediation](./runtime-orchestration-and-tool-mediation.md) — How context flows
- [Harness Optimization](./harness-optimization.md) — Tuning context engineering decisions
