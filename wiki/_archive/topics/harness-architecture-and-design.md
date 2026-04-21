# Harness Architecture and Design

**Created**: 2026-04-17 | **Last updated**: 2026-04-17

## Definition

A **harness** is the control stack that orchestrates an LLM across multiple reasoning steps, tool uses, and state transitions. It is distinct from:
- The base model (weights, training)
- Low-level execution hooks (test runners, verifiers)

Instead, a harness specifies:
- What work is decomposed and scheduled
- What contracts must be satisfied (inputs, outputs, gates)
- What roles and responsibilities exist
- What state persists across steps
- How failures are classified and recovered

## The Harness is First-Class Infrastructure

Per [Natural-Language Agent Harnesses](../sources/2026-04-17_natural-language-agent-harnesses.md), **harness design matters as much as model selection**. Evidence:

- Changing the harness around a **fixed model** can produce **6× performance gains** (Meta-Harness experiments)
- Harness choice interacts with model capability: a weaker model with optimized harness can outperform a stronger model with poor harness design

This reframes "prompt engineering" into the broader practice of **harness engineering**: designing the entire orchestration, not just the prompts.

## Core Components (NLAH Formalism)

Per [Natural-Language Agent Harnesses](../sources/2026-04-17_natural-language-agent-harnesses.md), a harness makes explicit:

### Contracts
- Required inputs and outputs
- Format constraints and validation gates
- Permission boundaries (what the agent can/cannot access)
- Retry and stop rules (when to give up)

### Roles
- **Solver**: Generates candidate solutions
- **Verifier**: Validates outputs against contracts
- **Researcher**: Gathers additional information
- **Orchestrator**: Coordinates multi-agent workflows
- Each role has a distinct prompt and responsibility boundary

### Stage Structure
- Explicit workflow topology: Plan → Execute → Verify → Repair
- Named stages enable inspectability and testing
- Stages can be iterative (verify fails → repair → re-verify)

### Adapters & Scripts
- **Deterministic hooks** for tests, linters, verifiers, parsers
- Replace ad-hoc tool mediation with named, reusable procedures
- Examples: `run_tests()`, `parse_json()`, `check_permissions()`

### State Semantics
- **What persists** across steps (artifacts, ledgers, child workspaces)
- **How it reopens** (path conventions, manifest loading)
- Prevents silent loss of state or incorrect reuse

### Failure Taxonomy
- Classify failure modes by type
- Map each failure to recovery strategy
- Enable systematic testing of failure handling

## Design Patterns

Per [Building Effective Agents](../sources/2026-04-17_anthropic-building-effective-agents.md), five compositional patterns:

| Pattern | Use Case | Example |
|---|---|---|
| **Prompt Chaining** | Sequential task decomposition | Thesis: outline → draft → review → final |
| **Routing** | Multi-domain classification | DAC: intake form routing by policy type |
| **Parallelization** | Independent subtasks or voting | Risk assessment: multiple models, aggregate |
| **Orchestrator-Workers** | Dynamic delegation | DAC: intake orchestrator → pricing → decision → review |
| **Evaluator-Optimizer** | Iterative refinement | Test harness: generate → run → evaluate → refine |

## Two Complementary Approaches

### Natural-Language Harnesses (NLAHs)
- Harness logic written in editable, inspectable natural language
- Executed by Intelligent Harness Runtime (IHR)
- Enables **declarative specification** of orchestration
- Facilitates comparison, migration, and collaboration

**Benefit**: Harness design becomes portable across runtimes.

### Automated Harness Optimization (Meta-Harness)
- Agentic search over harness code
- Proposes targeted edits based on execution traces and scores
- Discovers optimal prompt phrasing, tool sequences, state flow
- Learns from full diagnostic history

**Benefit**: Harness tuning becomes systematic and reproducible.

## Connection to Multi-Session Coherence

Per [Effective Harnesses for Long-Running Agents](../sources/2026-04-17_anthropic-effective-harnesses-long-running-agents.md):

- Harnesses must encode **explicit progress tracking** (feature list, completion status)
- Each session's startup ritual reads progress file and git log
- State persists in structured artifacts (JSON, manifests), not ephemeral memory
- Enables multi-context work without loss of coherence

**Practical implication**: Design harnesses to survive session boundaries through durable state and explicit recovery.

## Thesis Application

Your stress-testing framework (EXP-001/002/003) can be expressed as a harness:

**Stage structure**:
1. **Setup**: Initialize test environment, load synthetic data
2. **Inject failures**: Apply failure modes (parsing errors, timeout, conflicting data)
3. **Run experiment**: Execute pricing engine under stress
4. **Interpret results**: Classify failures, measure detection rate
5. **Report**: Summarize findings and methodology

**Contracts**: Each stage has explicit inputs, outputs, success criteria, and failure modes.

**Roles**: Test orchestrator (manages flow), test harness (injects failures), interpreter (classifies results).

**State semantics**: Prior experiment results persisted in manifests, enabling reuse and comparison.

## DAC Application

DAC's multi-stage underwriting pipeline is naturally a **orchestrator-workers harness**:

1. **Intake orchestrator**: Routes form → pricing/decision based on policy type
2. **Pricing worker**: Executes GLM model, validates outputs
3. **Decision worker**: Applies underwriting rules, detects edge cases
4. **Review worker**: Human-in-the-loop validation, exceptions handling

**Contracts**: Each worker has explicit input schema, output schema, and failure gates.

**State semantics**: Intake form, pricing result, underwriting decision, and review notes persist across workers.

---

**See also**:
- [Runtime Orchestration and Tool Mediation](./runtime-orchestration-and-tool-mediation.md) — How harnesses execute
- [Harness Optimization](./harness-optimization.md) — Improving harness design
- [Context Engineering](./context-engineering.md) — Strategic state and information flow
