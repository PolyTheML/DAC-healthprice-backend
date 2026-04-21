# Anthropic: Effective Harnesses for Long-Running Agents

**Source**: Anthropic Engineering Blog  
**URL**: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents  
**Date**: 2026 (recent)  
**Created**: 2026-04-17 | **Last updated**: 2026-04-17

## Overview

Practical guide to designing harnesses that survive **multiple context windows** and maintain progress across sessions. Addresses a core failure mode: agents that work well within a single context window but lose coherence when work spans multiple sessions.

## Core Problem: Multi-Session Coherence

Each new session begins with **no memory** of prior work. Systems must explicitly reconstruct context via:

- Progress tracking (what was completed, what remains)
- Git history (canonical record of changes)
- State artifacts (intermediate results, feature lists, test outputs)

Without these mechanisms, agents reset to square one on each invocation.

## Two-Part Solution Framework

### 1. Initializer Agent (First Run Only)

**Responsibilities**:
- Set up development environment (git repos, env files)
- Generate comprehensive feature list (structured JSON, 200+ items in examples)
- Create progress tracking file (marks completion state)
- Write `init.sh` script for repeatable environment setup
- Establish initial commits with descriptive messages

**Design principle**: Do foundational setup once, record everything for future sessions.

### 2. Coding Agent (Incremental Work)

**Responsibilities**:
- Read progress file and git log at session start to understand prior state
- Implement **single feature** per session
- Test thoroughly (browser automation, not just unit tests)
- Mark feature complete only after end-to-end validation
- Commit changes with descriptive messages
- Leave code in mergeable condition

**Design principle**: Small, testable increments; each session advances one feature.

## Critical Techniques

### Feature List Management

Use **structured JSON** format, not prose:

```json
{
  "features": [
    {
      "id": "feature-001",
      "name": "User authentication",
      "status": "completed",
      "tests": "auth.test.ts",
      "notes": "JWT + refresh tokens"
    },
    {
      "id": "feature-002",
      "name": "Dashboard",
      "status": "in_progress",
      "tests": "dashboard.test.ts",
      "notes": "Waiting on API integration"
    }
  ]
}
```

**Why structured**: Prevents premature completion declarations; agents can parse state precisely.

### Session Startup Ritual

Every session follows consistent steps:

1. Check working directory and git status
2. Read progress file to understand current state
3. Run basic end-to-end tests to validate prior work
4. Identify next incomplete feature
5. Implement and test before session end

### Testing Requirements

Critical finding: **Browser automation is non-negotiable**. Unit tests alone are insufficient; agents must:

- Spawn actual browser and interact with UI
- Verify visual rendering, user workflows
- Test cross-feature interactions
- Avoid false positives from mocked data

## Key Failure Modes Addressed

| Failure Mode | Cause | Solution |
|---|---|---|
| Project completion prematurely declared | No external tracking; agent loses context across sessions | Feature list + progress file in source control |
| Buggy or untested code left in repo | Insufficient verification gates | Require browser automation before marking complete |
| Lost context on multi-session work | No session startup ritual | Read progress file, git log, run E2E tests first |
| Undocumented or unmergeable state | Inadequate commit messages | Require descriptive messages + mergeable condition |

## Connection to Thesis Framework

**Relevance**: Your stress-testing experiments (EXP-001/002/003) span multiple stages and could benefit from:
- **Feature list**: Document each experiment phase (setup, run, verification, interpretation)
- **Progress tracking**: Mark which phases complete, which pending
- **Session startup**: Each session reads prior results, validates assumptions before continuing
- **Testing discipline**: Each phase has explicit success criteria (failure modes caught, edge cases validated)

## Connection to DAC Platform

**Relevance**: DAC's multi-stage pipeline naturally maps to this pattern:
- **Initializer**: Bootstrap data, schemas, API clients
- **Coding agent sessions**: Implement one underwriting capability per session (intake form, pricing engine, decision node)
- **Feature list**: Track capabilities (GLM pricing, risk assessment, underwriter dashboard)
- **Progress tracking**: Mark which features are in_progress, completed, pending

---

*Synthesized from article content on harness design, multi-session coherence, and practical techniques.*
