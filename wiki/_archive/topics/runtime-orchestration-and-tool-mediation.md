# Runtime Orchestration and Tool Mediation

**Created**: 2026-04-17 | **Last updated**: 2026-04-17

## Definition

**Runtime orchestration** is the execution layer that interprets harness logic and mediates between the LLM and external tools. It handles:

- Interpreting harness contracts and stage structure
- Selecting next action consistent with control flow
- Invoking tools deterministically (tests, verifiers, parsers)
- Managing state updates and artifact persistence
- Detecting and recovering from failures

## Intelligent Harness Runtime (IHR)

Per [Natural-Language Agent Harnesses](../sources/2026-04-17_natural-language-agent-harnesses.md), an **in-loop LLM runtime** that:

1. **Reads** current state (NLAH contract, environment, stage history)
2. **Interprets** harness logic (natural language orchestration)
3. **Selects** next action consistent with contracts
4. **Executes** deterministically via adapters (tests, linters, verifiers)
5. **Updates** persistent state (artifacts, ledgers, child workspaces)

**Key architectural choice**: IHR cleanly separates **runtime charter** (orchestration semantics, policy) from **harness logic** (application-specific control flow).

## Separation of Concerns

IHR makes the boundary explicit:

| Component | Responsibility | Example |
|---|---|---|
| **Harness (NLAH)** | What work to do, in what order, with what contracts | "Plan stage must output JSON; pricing stage must pass validation gate" |
| **Runtime Charter** | How to execute that harness, respecting constraints | "When harness says 'verify', invoke the verification script; if it fails, retry up to 3 times" |
| **Adapters** | Deterministic execution hooks | `test_pricing()`, `parse_json()`, `check_schema()` |

This separation enables:
- **Portability**: Same harness logic can execute under different runtime policies
- **Inspectability**: Harness logic is readable; runtime policy is declarative
- **Composability**: Adapters can be reused across harnesses

## Tool Design for Agent Systems

Per [Building Effective Agents](../sources/2026-04-17_anthropic-building-effective-agents.md), effective tools require:

### Clear Purpose & Constraints

Each tool should have:
- Single, well-defined responsibility
- Clear constraints (what it can/cannot do)
- Examples of intended use

### Input/Output Specifications

Define **Agent-Computer Interface (ACI)**:
- Input schema (required fields, format, constraints)
- Output schema (what the agent receives)
- Validation rules (format checking, bounds validation)

### Comprehensive Examples

Provide 3-5 worked examples covering:
- Happy path (standard use case)
- Edge cases (boundary conditions)
- Error cases (what happens on invalid input)

### Poka-Yoke Principles

Design to prevent misuse:
- Make valid usage obvious (field names, ordering)
- Validate inputs before execution
- Return clear error messages on failure
- Minimize ceremony (JSON over XML, concise field names)

### Testing & Validation

- Test tool behavior under adversarial use
- Simulate agent misuse patterns
- Verify error handling is graceful

## Workflow Patterns as Orchestration

Per [Building Effective Agents](../sources/2026-04-17_anthropic-building-effective-agents.md), five patterns represent different **orchestration topologies**:

### Prompt Chaining
Sequential LLM calls, each taking prior output. Runtime responsibility:
- Pass outputs between calls without losing context
- Validate intermediate outputs (format, sanity checks)
- Stop on errors or completion

### Routing
Classify input, dispatch to handler. Runtime responsibility:
- Execute classifier reliably
- Route to correct handler
- Aggregate results if handlers produce multiple outputs

### Parallelization
Run multiple independent branches. Runtime responsibility:
- Launch branches concurrently
- Collect results as they complete
- Implement timeout/failure handling
- Aggregate results (voting, averaging, or combination)

### Orchestrator-Workers
Central LLM coordinates workers. Runtime responsibility:
- Execute orchestrator → get delegation instruction
- Invoke appropriate worker with instruction
- Collect worker output
- Repeat until orchestrator signals completion

### Evaluator-Optimizer
Generate → evaluate → optimize loop. Runtime responsibility:
- Execute generator
- Execute evaluator on output
- If evaluation fails, execute optimizer with feedback
- Iterate until evaluation passes or retry limit reached

## Session Startup Ritual

Per [Effective Harnesses for Long-Running Agents](../sources/2026-04-17_anthropic-effective-harnesses-long-running-agents.md), runtime must establish consistent session **initialization**:

1. Check working directory and git status
2. Read progress tracking file (JSON feature list)
3. Review git log to understand prior context
4. Run basic end-to-end validation tests
5. Identify next work item from feature list

**Design principle**: Explicit state recovery enables multi-session coherence without memory.

## State Semantics and Persistence

Critical runtime responsibility: **durable state management**

- **Artifacts**: Intermediate outputs (test results, pricing outputs, parsed JSON)
- **Ledgers**: Running records (which tests passed, which failed, what was tried)
- **Child workspaces**: Isolated execution contexts for subtasks (e.g., child agent for specialized reasoning)

**State reopening**: On new session, runtime reconstructs state from:
- Manifest files (declaring what artifacts exist)
- Path conventions (where to find each artifact)
- Ledger entries (history of actions taken)

## Thesis Application

Your stress-testing harness runtime would:

1. **Parse NLAH**: Read experiment specification (EXP-001 stage structure, failure modes, success criteria)
2. **Initialize**: Load synthetic portfolio, set up test environment
3. **Execute stages**: Run each stage, updating result artifacts
4. **Detect failures**: Invoke failure classifier (adapter script), catch parsing errors, timeouts, etc.
5. **Record results**: Append to ledger (which failures detected, how many, in what order)
6. **Persist state**: Save results to manifest for later analysis

## DAC Application

DAC's multi-stage underwriting would execute under a **orchestrator-workers runtime**:

1. **Parse NLAH**: Intake orchestrator spec, pricing worker spec, decision worker spec
2. **Load state**: Prior results from intake form
3. **Execute orchestrator**: Classify policy type, route to pricing/decision
4. **Invoke workers**: Call pricing worker with intake data, decision worker with pricing result
5. **Update state**: Persist pricing result, underwriting decision, any exceptions
6. **Session recovery**: On restart, read prior form/pricing/decision; identify next worker

---

**See also**:
- [Harness Architecture and Design](./harness-architecture-and-design.md) — What the runtime executes
- [Tool Design for Agents](./tool-design-for-agents.md) — Designing tools the runtime invokes
- [Effective Harnesses for Long-Running Agents](../sources/2026-04-17_anthropic-effective-harnesses-long-running-agents.md) — Session coherence patterns
