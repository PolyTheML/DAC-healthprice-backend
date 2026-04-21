# Source: AutoResearch Tutorial — The Only Tutorial You'll Ever Need

**Source File**: 2026-04-10_autoresearch-tutorial-youtube.md  
**Original**: YouTube transcript by David Andre  
**URL**: https://www.youtube.com/watch?v=uBWuKh1nZ2Y  
**Ingested**: 2026-04-10  
**Format**: Video transcript (~19 minutes)

**Created**: 2026-04-10  
**Last Updated**: 2026-04-10

---

## Summary

David Andre explains Andrej Karpathy's AutoResearch framework—a method for autonomous AI self-improvement through systematic experimentation. The core insight: **Give an AI agent one editable file, one metric, and fixed time budgets per experiment; the agent runs 100+ experiments overnight, keeping improvements and reverting failures.** AutoResearch is generalizable beyond ML training to any domain with measurable outcomes (trading, marketing, prompt engineering, code optimization).

---

## Core Architecture

### Three-Layer System

1. **program.md** — Human instructions: goals, constraints, iteration rules (agent cannot modify)
2. **train.py** — One file the agent edits (could be code, config, prompt, math, anything optimizable)
3. **prepare.py** — Metric & evaluation script (agent cannot modify; defines "better")

The agent's constraint ensures it cannot cheat by rewriting the scoring function.

### The Experiment Loop

1. Agent proposes hypothesis (what will improve outcome)
2. Modifies `train.py`
3. Evaluates on fixed time budget (~5 min for ML, varies by domain)
4. Runs `prepare.py` metric
5. If improved: `git commit`
6. If not: `git reset` and repeat

**Result**: 100+ experiments overnight with perfectly comparable results (same time budget per experiment).

---

## Three Success Conditions (All Required)

| Condition | Why It Matters | Failure Mode |
|-----------|----------------|--------------|
| **Clear metric** | One number, objective direction | Agent optimizes random direction if metric is ambiguous |
| **Automated evaluation** | No human in the loop; runs while you sleep | Loop too slow to iterate; not autonomous |
| **One editable file** | Single point of modification | Too many variables = uncontrolled experiments |

**Without all three, AutoResearch fails.**

---

## Where AutoResearch Fails

- Brand design, UX (subjective "better")
- Pricing decisions (slow feedback loop, subjective value)
- Any domain where success is a judgment call or feeling

---

## Generalizability: Beyond Machine Learning

AutoResearch applies wherever:
- Outcome is measurable (one scalar metric)
- Evaluation is automated (no human judgment needed)
- Iteration is fast enough to sustain overnight loops

### Use Cases

| Domain | Train File | Metric | Example |
|--------|-----------|--------|---------|
| **ML training** | Model hyperparams/architecture | Validation accuracy | Karpathy's GPT-2 optimization |
| **Trading** | Buy/sell rules | Sharpe ratio | Test 100s of strategies overnight |
| **Marketing** | Email copy, ad creative, headlines | Conversion rate | Run 100 variants/day vs. 30/year |
| **Code optimization** | Algorithm implementation | Speed (latency/throughput) | Fine-tune models for phone deployment |
| **Prompt engineering** | System instructions + examples | Task accuracy/BLEU/user satisfaction | Optimize phrasing, language, proficiency level |
| **Product development** | Feature flags, UI configs | User engagement/revenue | A/B test at scale with automated feedback |

---

## Critical Insight: What Becomes Valuable

> "The skill that will make millionaires in the future is knowing **what to measure**, picking the **right metric**, and setting the **right constraints**. Because execution of any work or task will soon be basically free."

**Implication**: As agents commoditize execution, **metric design** becomes the competitive moat. Picking the wrong metric = optimizing the wrong thing with perfect efficiency.

---

## Karpathy's End Vision

Inspired by SETI@Home:
- Millions of AI agents distributed across thousands of computers
- Each running autonomous research loops
- Users allocate computational budget to research areas they care about
- Prediction: All frontier labs (OpenAI, Anthropic, Google) will run AutoResearch loops as the primary research engine

---

## Practical Example: Website Speed Optimization

**Live demo**: David Andre optimized a portfolio website's load time

| Iteration | Load Time | Change | Method |
|-----------|-----------|--------|--------|
| Baseline | 50ms | — | Simple portfolio site (Express + static files) |
| Exp 1 | 51ms | +2% | Reverted (worse) |
| Exp 2 | 33ms | -34% | Kept (committed) |
| Exp 3 | 28ms | -15% | Kept (from 33ms baseline) |
| Exp 4 | 25ms | -50% | Kept (from original 50ms) |

**Time elapsed**: ~4 minutes  
**Agent**: Claude Code with fast mode

---

## Implementation Notes

- **Tools**: GitHub + IDE (VS Code or Cursor) + coding agent (Claude Code, Codeium, etc.)
- **Parallelization**: Deploy multiple agents; they may find different optima
- **Key file**: program.md is heavily engineered; steal templates from Karpathy's original repo
- **Metrics**: Measure before starting to establish baseline
