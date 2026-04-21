# Agentic Workflows & Orchestration

**Last Updated**: 2026-04-09

## Overview

Agentic workflows enable autonomous systems to decompose complex tasks into multiple steps, with LLMs dynamically determining next actions. Core frameworks include LangGraph, CrewAI, and multi-agent patterns.

---

## Key Principles from Anthropic Research

**Source**: [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)

### Core Distinction: Workflows vs. Agents

- **Workflows**: Predefined code paths, best for predictable well-scoped tasks
- **Agents**: Dynamic decision-making, best for open-ended problems where steps are unpredictable

### Six Effective Patterns

1. **Prompt Chaining** — Fixed decomposition (task A → task B → task C)
2. **Routing** — Selecting specialized handler based on input category
3. **Parallelization** — Speed gains or confidence improvements through multiple attempts
4. **Orchestrator-Workers** — Central coordinator delegates to specialized agents
5. **Evaluator-Optimizer** — Iterative refinement with explicit evaluation criteria
6. **Agents** — Truly autonomous systems for open-ended problems

### Design Principles

- **Start simple**: Many applications only need optimized single LLM calls + retrieval
- **Transparency**: Agents must explicitly plan before acting (visible reasoning > hidden state)
- **Tool design excellence**: Format matters enormously for LLM accuracy
  - Provide context *before* output generation
  - Include example usage and edge cases
  - Apply "poka-yoke" (mistake-proofing) to prevent errors

---

## LangGraph: Multi-Agent Architecture

**Sources**: 
- [LangGraph Multi-Agent Workflows](https://blog.langchain.com/langgraph-multi-agent-workflows/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)

### Core Model

Multi-agent systems = **multiple independent actors (LLMs) connected in a directed graph**

Each agent has:
- Own prompt and system instructions
- Own LLM instance (can use different models)
- Own tools and custom logic
- Independent scratchpad or shared context

### Three Orchestration Patterns

| Pattern | Information Flow | Best For |
|---------|-----------------|----------|
| **Collaboration** | Shared scratchpad (all messages visible) | Full transparency; verbose but comprehensive |
| **Supervisor Model** | Independent scratchpads + central aggregator | Focused work per agent, centralized routing |
| **Hierarchical Teams** | Nested LangGraph agents under supervisor | Maximum specialization and team structure |

### Key Benefits

1. **Specialization**: Focused agents perform better than generalists with many tools
2. **Customization**: Per-agent prompts, models, fine-tuning
3. **Maintainability**: Evaluate/improve agents independently

---

## Insurance Application: Underwriting Workflow

For life insurance intake:

1. **Document Reader Agent** — Extracts medical data from PDFs (OCR + LLM)
2. **Risk Assessor Agent** — Computes GLM frequency-severity score
3. **Complexity Router Agent** — Determines if case is routine (STP) or requires human review
4. **Supervisor Agent** — Orchestrates workflow, manages state, ensures audit trail

**State Machine Checkpoint**: Each agent action is logged for compliance audit.

---

## Related Topics

- [Human-in-the-Loop Workflows](./human-in-the-loop.md) — How to integrate agent decisions with human oversight
- [Agentic AI & STP](./agentic-ai-stp.md) — Straight-through processing for routine cases
- [Agent Safety & Reliability](./agent-safety.md) — Guardrails and output validation
