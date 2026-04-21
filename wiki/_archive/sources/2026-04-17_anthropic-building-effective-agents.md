# Anthropic: Building Effective Agents

**Source**: Anthropic Engineering Blog  
**URL**: https://www.anthropic.com/engineering/building-effective-agents  
**Date**: 2026 (recent)  
**Created**: 2026-04-17 | **Last updated**: 2026-04-17

## Overview

High-level guidance on agent architecture, distinguishing between workflows (predefined orchestration) and agents (dynamic tool use), and five key design patterns. Emphasizes **simplicity, transparency, and documented tool design** over complexity.

## Core Architectural Distinction

### Workflows vs. Agents

| Aspect | Workflow | Agent |
|---|---|---|
| **Definition** | LLMs + tools orchestrated via predefined code paths | LLM dynamically directs its own tool use and branching |
| **When to use** | Open problem with known decomposition | Genuinely open-ended; path cannot be predetermined |
| **Trade-offs** | Predictable, low latency, low cost | Higher latency/cost, but adaptive to novel scenarios |

**Key principle**: Start with workflows; graduate to agents only when necessary.

## When to Build Agents

Three conditions suggest agentic systems:

1. **Open-ended problem**: Task steps cannot be predetermined
2. **Tool uncertainty**: Agent needs to decide which tools to invoke, in which order
3. **Adaptive recovery**: Agent must learn from failures and adjust approach

Most practical systems remain **workflow-based** with strategic agentic components (e.g., a routing agent that classifies input, then hands off to specialized workflows).

## Five Core Workflow Patterns

These patterns represent **compositional building blocks** for orchestrating LLMs and tools:

### 1. Prompt Chaining

Sequential LLM calls, each taking output of prior call as input. Useful for:
- Decomposing complex tasks (write → edit → finalize)
- Clear checkpoints between steps
- Easy monitoring and debugging

**Example**: Thesis writing pipeline (outline → draft → review → final).

### 2. Routing

Classify input and direct to specialized handler. Useful for:
- Multi-domain problems (customer support: billing vs. technical vs. returns)
- Ensuring correct tool/agent specialization
- Reducing hallucination via focused prompts

**Example**: DAC intake form routing (individual → employee → group plan).

### 3. Parallelization

Run multiple independent subtasks simultaneously or use voting/averaging for diverse outputs. Useful for:
- Fault tolerance (if one branch fails, others continue)
- Consensus building (multiple agents reason, then aggregate)
- Throughput (embarrassingly parallel workloads)

**Example**: Risk assessment with multiple independent models, aggregated via voting.

### 4. Orchestrator-Workers

Central LLM dynamically delegates to specialized workers. Useful for:
- Complex multi-step workflows with conditional branching
- Workers are domain experts (each handles one task type)
- Orchestrator decides sequencing and combines results

**Example**: DAC underwriting (intake orchestrator → pricing worker → decision worker → review worker).

### 5. Evaluator-Optimizer

Iterative refinement loop: LLM generates, evaluator provides feedback, optimizer improves. Useful for:
- Quality-critical outputs (code generation, creative writing)
- Tight feedback loops (agent sees what failed and why)
- Convergence detection (iterate until quality threshold met)

**Example**: Stress-test harness refinement (generate test case → run → evaluate pass/fail → refine parameters).

## Three Core Implementation Principles

### 1. Simplicity

- Start simple (prompt chaining)
- Add complexity only when justified
- Avoid over-engineering multi-agent systems when workflows suffice

### 2. Transparency

- Make agent reasoning visible (explicit planning steps, not just tool invocations)
- Document decision points and branching logic
- Enable auditing and debugging

### 3. Documentation & Testing of Tool Interfaces (ACI)

Define **Agent-Computer Interface** (ACI) for each tool:

- Clear purpose and constraints
- Input/output specifications
- Examples of correct/incorrect usage
- Failure modes and recovery strategies

**Principle**: Well-designed tools prevent misuse through documentation, examples, and poka-yoke principles.

## Tool Design Recommendations

### Format Overhead

Minimize ceremony; align with natural training data patterns:
- JSON over XML (more common in training data)
- Concise field names (reduce token overhead)
- Examples before schema definitions

### Thinking Space

Allow room for reasoning:
- Don't compress feedback too aggressively
- Preserve diagnostic information (execution traces, failure reasons)
- Let agent see full context before deciding next step

### Comprehensive Documentation

Every tool needs:
- Purpose statement
- Input/output schema
- 3-5 worked examples (happy path + edge cases)
- Common failure modes

### Testing & Poka-Yoke

- Test tool behavior under adversarial use
- Design constraints to prevent misuse (e.g., required fields, format validators)
- Make correct usage the easiest path

## Practical Applications

Two domains show particular value:

### Customer Support Agents
- Clear success metrics (issue resolved, customer satisfaction)
- Actionable feedback loops (customer says "no, you misunderstood")
- Meaningful human oversight (human reviews complex cases)

### Coding Agents
- Well-defined interface (filesystem, shell, version control)
- Automatic validation (tests, type checking, linting)
- Incremental progress (each session advances one feature)

## Connection to Context Engineering

Recent work (Anthropic 2024-2025) frames agent design as **context engineering**:

- Decide what information to store, retrieve, and present
- Make these decisions explicit and measurable
- Optimize over the entire orchestration, not just prompts

## Connection to Thesis & DAC

**For thesis**: Your stress-testing framework is a multi-stage workflow:
- **Routing** component: Classify failure modes
- **Orchestrator-workers** pattern: Test harness orchestrates EXP-001/002/003 workers
- **Evaluator-optimizer** pattern: Interpret results, refine test strategy

**For DAC**: Multi-stage underwriting is classically orchestrator-workers:
- Orchestrator routes intake forms
- Pricing worker executes GLM model
- Decision worker applies underwriting rules
- Review worker validates edge cases

---

*Synthesized from article sections on architecture, patterns, principles, and practical guidance.*
