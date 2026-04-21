# Meta-Harness: End-to-End Optimization of Model Harnesses

**Source**: Lee, Nair, Zhang, Lee (Stanford/KRAFION), Khattab (MIT), Finn (Stanford)  
**Arxiv ID**: 2603.25723v1 | **Date**: March 2026  
**Created**: 2026-04-17 | **Last updated**: 2026-04-17

## Overview

Proposes **Meta-Harness**, an automated system for optimizing harness code (the orchestration logic around an LLM) via agentic search. Key finding: **6× performance gains possible** through harness optimization alone; harness choice matters as much as model weight tuning.

## Core Problem Addressed

Despite the enormous impact of harness design on LLM system performance, harness engineering remains largely **manual and ad-hoc**:

- Practitioners inspect features and manually adjust prompts, tool mediation, artifact conventions, verification gates, and state semantics
- Existing text optimizers (ProLaGi, TextGrad, OPRO, GEPA, AlphaEvolve) are poorly matched to harness engineering because:
  - They operate with short-horizon or heavily compressed feedback
  - They optimize over narrow design spaces (prompt templates, score heuristics)
  - They cannot reason over full harness implementations, execution traces, and long-range dependencies

## Key Contribution: Meta-Harness System

**Architecture**:

1. **Codebase as source of truth**: Filesystem containing:
   - Prior harness candidate implementations (source code)
   - Execution traces (diagnostic info on prior runs)
   - Evaluation scores (success metrics on tasks)

2. **Agentic proposer**: Coding agent that:
   - Reads full history (code, traces, scores)
   - Proposes targeted edits to harness code
   - Accesses developer tools (grep, cat, standard operations vs. monolithic prompt)
   - **Key insight**: Full history enables selective diagnosis; proposer reasons over failed examples and execution traces to identify targeted fixes

3. **Evaluation loop**:
   - Evaluate proposed harness on benchmark tasks
   - Store all logs (proposed code, reasoning traces, eval scores) in filesystem
   - Loop repeats; agent learns from full prior experience

**Why it works**: By exposing **full history** through the filesystem (rather than compressed summaries), the agent can:
- Trace downstream failures to upstream harness decisions
- Reason over prior candidate harnesses and their trade-offs
- Propose incremental, evidence-backed edits

## Experimental Results

### Text Classification (Online Task)

- Meta-Harness improves over **Agentc Context Engineering (ACE)** by 7.7 points while using **4× fewer context tokens**
- Discovers harnesses surpass prior hand-engineered optimizers (TTT-Discover, OpenEvolve) after just 60 proposals

### Retrieval-Augmented Math Reasoning

- Single discovered harness improves **IMO-level math problems by 4.7 points** on average across 5 held-out models
- Surpasses prior hand-optimized baselines

### Agentic Coding (TerminalBench-2)

- Discovered harnesses **rank #1 among all Claude Haiku 4.5 agents** in benchmark leaderboard

### Token Efficiency

- Meta-Harness uses full history (82 files per iteration, ~10M tokens diagnostic info)
- Yet achieves 4× context reduction vs. prior art by selectively exposing relevant failure traces

## Design Patterns Discovered

Meta-Harness automatically discovers harness patterns aligned with the paper's taxonomy:

- **Prompt construction**: How to frame instructions for clarity and guardrailing
- **Retrieval strategy**: When/how to invoke external knowledge
- **State update logic**: How to persist intermediate artifacts and reopen them
- **Tool mediation**: Validation gates, format enforcement, retry logic
- **Verification strategy**: When to validate outputs and how to handle failures

## Connection to Context Engineering

Meta-Harness builds on recent **context engineering** insights (Anthropic 2024-2025):

- Practitioners decide **what to store, retrieve, and present at each model call**
- These decisions span prompts, tool mediation, artifact conventions, and state semantics
- Meta-Harness automates this decision-making via agentic search + full history

## Connection to Thesis Framework

**Relevance**: Your stress-testing framework (EXP-001/002/003) could be **optimized** via Meta-Harness principles:
- Express experimental harness as mutable code (test orchestration, failure detection, result aggregation)
- Use agentic search to optimize test harness design (e.g., when to scale up, how to stratify test cases)
- Preserve full diagnostic history to inform future experimental designs

**Actionable insight**: If you wanted to optimize your stress-test parameters or failure injection strategies, Meta-Harness formalism shows how to do it systematically.

## Connection to DAC Platform

**Relevance**: DAC's multi-stage underwriting pipeline (intake → pricing → decision → review) could be optimized end-to-end via Meta-Harness:
- Each stage is a harness (prompts, tools, state flow)
- Meta-Harness could discover optimal prompt phrasing, tool invocation strategy, and state passing conventions
- Improvements measured on hold-out underwriting cases

---

*Synthesized from abstract, introduction, methodology, and experimental sections.*
