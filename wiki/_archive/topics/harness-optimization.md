# Harness Optimization: Automated Search and Tuning

**Created**: 2026-04-17 | **Last updated**: 2026-04-17

## The Case for Systematic Harness Tuning

Per [Meta-Harness](../sources/2026-04-17_meta-harness-optimization.md):

- **6× performance gains** are possible through harness optimization alone
- Harness choice often matters **as much as model selection**
- Yet harness tuning remains largely **manual and ad-hoc**

Current practice:
- Practitioners manually inspect features (prompts, tool sequences, state handling)
- Adjust based on intuition or trial-and-error
- Results are hard to reproduce or transfer across domains

**Problem**: Existing text optimizers (ProLaGi, TextGrad, OPRO, GEPA, AlphaEvolve) are poorly matched because they:
- Operate with short-horizon or heavily compressed feedback
- Optimize narrow design spaces (prompt templates, score heuristics)
- Cannot reason over full harness implementations and long-range dependencies

## Meta-Harness: Automated Harness Search

### Architecture

**Codebase as source of truth**:
- Prior harness candidate implementations (source code)
- Execution traces (diagnostic information from prior runs)
- Evaluation scores (success metrics on benchmark tasks)

**Agentic proposer** (coding agent):
- Reads **full history**: code, traces, scores (not compressed summaries)
- Identifies patterns in prior failures
- Proposes targeted edits to harness code
- Accesses developer tools: grep, cat, file operations (vs. monolithic prompt)

**Key insight**: By exposing full history through the filesystem, agent can:
- Trace downstream failures to upstream harness decisions
- Reason over prior candidates and their trade-offs
- Propose evidence-backed, incremental edits

**Evaluation loop**:
- Evaluate proposed harness on benchmark tasks
- Store all logs (proposed code, reasoning traces, scores) in filesystem
- Repeat; agent learns from full prior experience

### Why Full History Matters

Compressed feedback (e.g., "score improved from 70 to 75") loses critical information:
- Which edit caused the improvement?
- Did the improvement come from changed prompt or changed tool sequence?
- Is the improvement stable across different inputs?

**Full diagnostic history** (execution traces, failure classifications) enables:
- Selective diagnosis: agent sees which prior attempts failed and why
- Targeted proposals: agent identifies specific harness components to edit
- Evidence-backed changes: agent cites execution traces as justification

## Experimental Results

### Text Classification (Online Task)

- Meta-Harness improves over **Agentc Context Engineering (ACE)** by **7.7 points**
- Uses **4× fewer context tokens** (by selectively exposing relevant diagnostics)
- Discovers harnesses surpass hand-optimized baselines after just 60 proposals

### Retrieval-Augmented Math Reasoning

- Single discovered harness improves **IMO-level math problems by 4.7 points** on average
- Improves across 5 held-out models (generalization)

### Agentic Coding (TerminalBench-2)

- Discovered harnesses **rank #1 among all Claude Haiku 4.5 agents** in benchmark leaderboard

### Token Efficiency

Counterintuitive result: Despite using full history (82 files per iteration, ~10M tokens diagnostic info), Meta-Harness achieves **4× context reduction** vs. prior art by **selectively filtering** execution traces to show only relevant failures.

## Harness Patterns Automatically Discovered

Meta-Harness discoveries align with NLAH taxonomy:

- **Prompt construction**: Optimal framing for clarity and guardrailing
- **Retrieval strategy**: When/how to invoke external knowledge
- **State update logic**: How to persist and reopen artifacts
- **Tool mediation**: Validation gates, format enforcement, retry logic
- **Verification strategy**: When to validate and how to handle failures

## Design Space for Harness Optimization

Dimensions that Meta-Harness can tune:

| Dimension | Examples |
|---|---|
| **Prompt phrasing** | Instructional tone, level of detail, examples |
| **Tool invocation** | When to call tool, tool order, tool parameters |
| **State persistence** | What to store, how to format (JSON/YAML), where to store |
| **Verification gates** | When to validate, which validators, retry thresholds |
| **Failure recovery** | Fallback strategies, backtracking policies |

## Contrast with Manual Tuning

| Aspect | Manual | Meta-Harness |
|---|---|---|
| **Feedback signal** | Aggregate score | Full execution traces |
| **Proposal strategy** | Intuition, trial-and-error | Evidence-backed, targeted edits |
| **Context available** | Current problem | Full prior history |
| **Iteration speed** | Slow (human in the loop) | Fast (agentic loop) |
| **Reproducibility** | Hard (decisions not recorded) | Full; all edits recorded in git |

## Thesis Application

Your stress-testing framework could be optimized via Meta-Harness:

1. **Baseline harness**: Express EXP-001/002/003 as mutable code (failure injection, test orchestration, result interpretation)
2. **Evaluation**: Run experiments, capture execution traces (which tests ran, which failures detected, timing)
3. **Propose improvements**: Meta-Harness suggests:
   - Better failure injection strategy (e.g., inject failures earlier or later in flow)
   - Improved result interpretation (e.g., classify failures more precisely)
   - Optimized test parameters (e.g., portfolio size, time horizons)
4. **Iterate**: Each improvement validated on new synthetic portfolios

**Benefit**: Discover optimal experimental design systematically, not by intuition.

## DAC Application

DAC's multi-stage underwriting pipeline could be optimized end-to-end:

1. **Baseline harness**: Current intake → pricing → decision → review pipeline
2. **Evaluation**: Run on hold-out underwriting cases; capture traces
3. **Propose improvements**: Meta-Harness suggests:
   - Better intake form routing (which questions to ask first?)
   - Optimal pricing prompt phrasing (which factors to emphasize?)
   - Improved decision logic (when to escalate vs. auto-approve?)
4. **Validate**: Measure impact on underwriting accuracy, speed, cost

**Benefit**: DAC harness improves continuously without manual tuning; discoveries transfer to new markets or policy types.

## Connection to Context Engineering

Meta-Harness builds on insights from **context engineering** (Anthropic 2024-2025):

- What to **store** (artifacts, state)
- What to **retrieve** (on agent invocation)
- What to **present** (in prompt context)

These decisions span prompt phrasing, tool sequences, state flow, and verification logic. Meta-Harness automates them via agentic search.

---

**See also**:
- [Harness Architecture and Design](./harness-architecture-and-design.md) — What to optimize
- [Context Engineering](./context-engineering.md) — Information flow within harnesses
- [Meta-Harness: End-to-End Optimization](../sources/2026-04-17_meta-harness-optimization.md) — Full paper
