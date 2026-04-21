# Natural-Language Agent Harnesses (NLAHs)

**Source**: Pan, Zou, Guo, Ni, Zheng (Tsinghua International Graduate School & Harbin Institute of Technology)  
**Arxiv ID**: 2603.28052v1 | **Date**: March 2026  
**Created**: 2026-04-17 | **Last updated**: 2026-04-17

## Overview

Proposes treating harness design as a first-class systems artifact, not a thin wrapper around model calls. Introduces two complementary contributions:

1. **Natural-Language Agent Harnesses (NLAHs)**: Structured natural-language representation of harness control logic, written in editable markdown/YAML-like format
2. **Intelligent Harness Runtime (IHR)**: Shared LLM runtime that interprets NLAH specifications directly, cleanly separating runtime charter from harness logic

## Core Problem Addressed

Harness logic is currently scattered across:
- Controller code (Python/JS procedural)
- Framework defaults (hidden assumptions)
- Tool adapters (verification gates, mediation rules)
- Runtime-specific conventions (artifact naming, state semantics)

This fragmentation makes harnesses:
- Hard to compare across runtimes
- Difficult to transfer between systems
- Impossible to inspect as a coherent artifact
- Prone to redundant implementation

## Key Contributions

### 1. NLAH Formalism

**Core components made explicit:**

- **Contracts**: Required inputs/outputs, format constraints, validation gates, permission boundaries, retry/stop rules
- **Roles**: Role prompts (solver, verifier, researcher, orchestrator) with non-overlapping responsibilities
- **Stage structure**: Explicit workflow topology (plan → execute → verify → repair)
- **Adapters & scripts**: Named hooks for deterministic actions (tests, linters, verifiers, parsers)
- **State semantics**: What persists across steps (artifacts, ledgers, child workspaces) and how it reopens (paths, manifests)
- **Failure taxonomy**: Classification of failure modes and recovery strategies

**Format principle**: Editable, inspectable natural-language contracts bound to explicit carriers (not buried in code).

### 2. Intelligent Harness Runtime (IHR)

**Architecture**:

- **In-loop LLM**: Interprets harness logic (NLAH contracts, roles, stage structure)
- **Backend tool access**: Terminal tools, multi-agent interface (e.g., OpenAI spawning/supervising)
- **Runtime charter**: Semantic/orchestration/child lifecycle; separates runtime policy from harness logic

**Interpretation flow**:
1. IHR reads (i) the NLAH, (ii) current state & environment, (iii) runtime charter
2. Selects next action consistent with contracts & control flow
3. Executes deterministically (tests, linters, scripts via adapters)
4. Updates persistent state (artifacts, ledgers)

**Key innovation**: Natural language does not replace deterministic code; instead **carries editable, inspectable orchestration logic** while adapters/scripts provide deterministic hooks.

## Experimental Results

**Controlled evidence** on shared runtime behavioral effect (RQ1), module composition/ablation (RQ2), and pairing-fidelity code-to-text migration (RQ3):

- Demonstrates that harness design patterns can be expressed, compared, and migrated across runtimes under shared IHR assumptions
- Shows code-to-text migration is feasible without loss of fidelity

## Design Patterns Identified

The paper catalogs harness design patterns used by modern agents (from Figure 1):

- **Reflection**: Introspection on intermediate state
- **Planning**: Decompose task into stages
- **Memory**: Retain context across steps
- **Flow**: Control branching and loops
- **ReAct**: Reason-act cycle
- **Orchestration**: Multi-agent coordination
- **RAG**: Retrieval-augmented generation
- **Test-Time Scaling**: Iterative refinement
- **Subagenst**: Delegation to specialized workers
- **Self-Evolving**: Adaptive behavior

## Connection to Thesis Framework

**Relevance**: NLAHs provide a **declarative substrate** for expressing the stress-testing orchestration logic. Instead of hardcoding EXP-001/002/003 execution, you could express them as NLAH stage structures with explicit role boundaries (test harness, result interpreter, failure classifier).

**Actionable insight**: Your thesis methodology chapter could adopt NLAH formalism to document the experimental control flow—making it both human-readable and machine-executable.

## Connection to DAC Platform

**Relevance**: As DAC evolves toward multi-agent underwriting (intake → pricing → decision → review), NLAHs offer a way to declaratively specify role boundaries, contract enforcement, and state semantics without fragmenting the orchestration across Python/API glue code.

---

*Synthesized from abstract, introduction, methodology, and experimental sections.*
