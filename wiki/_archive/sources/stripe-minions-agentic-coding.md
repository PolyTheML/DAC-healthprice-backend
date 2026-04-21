# Stripe's Minions: One-Shot End-to-End Agentic Coding at Scale

**Source**: Stripe Engineering Blog, Part 1 (2026-02-09) & Part 2 (2026-02-19)  
**Authors**: Alistair Gray  
**Type**: Engineering Blog (Miniseries)  
**Date Ingested**: 2026-04-09  
**Related Topics**: [Blueprint Orchestration Pattern](../topics/blueprint-orchestration-pattern.md), [Agent Context Engineering at Scale](../topics/agent-context-engineering-at-scale.md)  

---

## Executive Summary

Minions are Stripe's homegrown unattended coding agents responsible for 1,300+ pull requests merged weekly at Stripe. Unlike supervised agents (Cursor, Claude Code), minions are fully autonomous, one-shot systems designed to complete coding tasks start-to-finish without human interaction—though all code is human-reviewed before merge.

Key insight for DAC-UW-Agent: Stripe demonstrates that **scaling autonomous agents requires blending infrastructure, context engineering, and deterministic guardrails** rather than pure LLM creativity.

---

## Part 1: User Experience & Capabilities (2026-02-09)

### How Engineers Use Minions

**Entry Points:**
- **Slack integration** (primary): Tag minion app with task description; minion reads thread context and links
- **Internal tools**: Docs platform, feature flag platform, ticketing system
- **CLI/Web**: Programmatic access for automation

**Example Workflow:**
```
Engineer in Slack: "@minion Fix the flaky test_auth_persistence test"
  ↓
Minion reads Slack thread + linked PR/ticket
  ↓
Creates isolated devbox
  ↓
Runs local linting, tests, CI (2 rounds max)
  ↓
Opens PR following Stripe template
  ↓
Engineer reviews code, merges if approved
```

### Minion Capabilities

- **Start**: Can be triggered from anywhere (Slack, web UI, internal tools)
- **Scope**: Can work on Stripe's massive codebase (100M+ LOC, multiple large repos)
- **Stack**: Ruby (with Sorbet typing), homegrown libraries unique to Stripe
- **Autonomy**: No human steering or confirmation prompts during run
- **Output**: Production-ready PR that passes CI (or ready for engineer to iterate on)

### Why Build Custom (vs. Using Off-the-Shelf Agents)

Stripe chose to fork Block's Goose and build custom minion harness because:

1. **Codebase complexity**: 100M+ LOC, Stripe-specific Ruby stack, unique homegrown libraries
2. **Production stakes**: $1 trillion/year payment volume; financial & regulatory obligations
3. **Existing infrastructure**: Stripe had already invested in developer productivity foundations (devboxes, CI, code generation, environments)
4. **Supervised vs. unattended use case**: Third-party tools (Cursor, Claude Code) optimize for human-in-loop; Stripe needed fully autonomous design

**Key insight**: "If it's good for humans, it's good for LLMs"—rather than building new infrastructure for agents, leverage what already powers human developers.

---

## Part 2: Architecture & Implementation (2026-02-19)

### Devboxes: Isolated, Parallelizable, Predictable

**Problem**: Agents need full autonomy without permission checks, but shouldn't interfere with each other or act destructively.

**Stripe's Solution**: Devboxes (AWS EC2 instances)
- **Pre-warmed**: Available in 10 seconds (caches: git repos, type checking, code generation)
- **Isolated**: One devbox per task (engineers often run 5-6 in parallel)
- **Standard**: Based on same devbox infrastructure human engineers use
- **Cattle, not pets**: Easily replaceable, standardized, not bespoke

**Key benefit for agents**: Full autonomy without confirmation prompts because blast radius is limited to one devbox. No access to production, real user data, or arbitrary network egress.

### Blueprints: Deterministic Workflows + Agentic Subtasks

**Problem**: Pure agent loops are creative but unreliable. How do you guarantee deterministic steps (linting, pushing, testing) while allowing LLM flexibility for discovery?

**Stripe's Solution**: Blueprints
- Mix of **deterministic nodes** (rectangles) and **agentic nodes** (clouds)
- Deterministic nodes: always execute (linting, type checking, git operations, pushing)
- Agentic nodes: LLM calls with full tool access (e.g., "Implement task", "Fix CI failures")
- Example flow:
  1. **Agentic node**: Implement feature based on task description
  2. **Deterministic node**: Run configured linters
  3. **Agentic node**: If lint failures, fix them
  4. **Deterministic node**: Push to CI, parse results
  5. **Agentic node**: If test failures with no autofix, debug and retry
  6. **Deterministic node**: Create PR

**Benefits**:
- Guarantees critical steps always run (linters, type checking) → saves tokens + reduces errors
- "Putting LLMs into contained boxes" compounds reliability at scale
- Teams can customize blueprints for specialized needs (e.g., codemod migrations)

**Analogy to DAC-UW-Agent**: This is exactly the four-layer architecture pattern (deterministic control points + agentic subtasks):
- Layer 1 (Core Engine): Deterministic GLM pricing
- Layer 2 (AI Layer): Agentic extraction + deterministic validation
- Layer 3 (Control Layer): Deterministic guardrails + agentic decision logic
- Layer 4 (Trust Layer): Deterministic audit logging

### Context Gathering: Rule Files

**Problem**: Large codebase means agents encounter unfamiliar libraries, conventions, best practices. Unconditional rules would bloat context window.

**Stripe's Solution**: Scoped rule files
- Rule files attached automatically as agent traverses filesystem
- **Scope by directory or file pattern**: Only load rules relevant to current file
- **Format standardization**: Uses Cursor's rules format (now synced to Claude Code format too)
- **Benefit**: Agents have just-in-time context, not full global rules

**For DAC-UW-Agent**: This suggests maintaining scoped rule files for different domains:
- Rules for medical data extraction (medical field ranges, validation logic)
- Rules for GLM pricing (actuarial conventions, regulatory constraints)
- Rules for compliance/audit (Cambodia IRC requirements, data privacy rules)

### Context Gathering: MCP (Model Context Protocol)

**Problem**: Static context (rule files) isn't enough. Agents need to dynamically fetch information (docs, tickets, build status, code intelligence).

**Stripe's Solution**: Centralized MCP server called "Toolshed"
- ~500 MCP tools for internal systems + SaaS platforms
- **Per-agent tool curation**: Each agent type gets relevant subset of tools
- **Security controls**: Agents can't use tools for destructive actions
- **Discovery**: Tools are automatically discoverable to all agentic systems

**Tools categories** (examples):
- Internal documentation lookup
- Ticket details (context about what to fix)
- Build status (check if CI passed)
- Code intelligence (Sourcegraph search)
- SaaS integrations (GitHub, Jira, etc.)

**For DAC-UW-Agent**: Could implement MCP tools for:
- Medical reference lookup (condition ranges, standard tests)
- Regulatory reference (Cambodia IRC articles, compliance guidelines)
- Actuarial reference (mortality tables, GLM parameters)
- Document metadata (applicant info, case history)

### Feedback & Iteration: Shifting Left

**Problem**: Running against CI many times is expensive (tokens, compute, time). Need fast local feedback.

**Stripe's Solution**: Multi-layer feedback architecture
1. **Pre-push hooks** (~<1 sec):
   - Background daemon precomputes lint rule heuristics
   - Auto-fixes common lint issues before push
   - Agent sees results before pushing branch

2. **Local testing** (deterministic node in blueprint):
   - Subset of linters run locally
   - Loop on lint failures locally before pushing
   - "Shift feedback left" principle: catch problems ASAP

3. **CI (one round)** (~minutes):
   - Full test suite runs after push
   - Auto-apply autofixes for test failures
   - If failures have no autofix, send back to agent for one more local attempt

4. **Second CI (final)** (~minutes):
   - If still failing after agent's second attempt, branch goes to human
   - Max 2 CI rounds to balance speed vs. completeness

**Key insight**: Deterministic checks early (linting) before expensive LLM iteration.

**For DAC-UW-Agent**: This maps to validation layers:
- **Layer 2 (AI)**: Local schema validation (Pydantic)
- **Layer 3 (Control)**: Domain validation (medical ranges)
- **Layer 4 (Trust)**: Consistency validation (audit trail)

---

## Key Takeaways for DAC-UW-Agent

### 1. **Infrastructure-First Approach**
Stripe didn't build agents from scratch—they leveraged existing human-developer infrastructure (devboxes, CI, code generation). 

**For underwriting**: Leverage existing insurance infrastructure (data pipelines, validation frameworks, compliance systems) rather than building agent-specific infrastructure.

### 2. **Deterministic Guardrails + Agentic Creativity**
Blueprints demonstrate that mixing determinism with LLM creativity compounds reliability:
- Deterministic: Always run linters, always push to CI, always log decisions
- Agentic: Adapt extraction logic, debug test failures, make context-dependent decisions

**For underwriting**: 
- Deterministic: Always run Frequency-Severity GLM, always validate medical data, always create audit trail
- Agentic: Adapt extraction for document variations, route complexity dynamically, explain decisions

### 3. **Scoped Context Engineering**
Don't bloat the context window with global rules. Attach context just-in-time based on what the agent is working on.

**For underwriting**:
- Medical rule files (for document extraction nodes)
- Actuarial rule files (for pricing nodes)
- Compliance rule files (for audit nodes)

### 4. **Isolated Execution Environments**
Devboxes provide parallelization, predictability, and isolation without human permission checks.

**For underwriting**: Consider containerized execution for agent processing (Docker containers, per-case isolation) so multiple underwriting decisions can run in parallel.

### 5. **One-Shot Design Requires Careful Planning**
Minions succeed because Stripe invested heavily in:
- Clear problem scope (specific PR, specific test, specific feature)
- Rich context (Slack thread, linked artifacts, rule files, MCP tools)
- Deterministic validation (linters, type checking, tests)
- Rapid feedback loops (local lint checks, auto-fixes, 2-round CI max)

**For underwriting**: Design agents to one-shot medical extraction + pricing + routing. Avoid multi-round iteration.

### 6. **Why Custom vs. Off-the-Shelf**
Stripe forked Goose rather than use Cursor/Claude Code because:
- Magnitude of difference: Supervised agents optimize for human-in-loop; Minions optimize for fully autonomous
- Context complexity: Stripe-specific libraries, conventions, infrastructure
- Integration depth: Need tight coupling with devboxes, CI, Toolshed, rule files

**For underwriting**: Consider whether generic agentic frameworks (LangGraph, CrewAI) are sufficient or if custom orchestration is needed for insurance-specific workflows.

---

## Connections to Existing DAC-UW-Agent Concepts

### Aligns With:
- **Four-layer architecture**: Blueprints = deterministic control (Layers 1, 3, 4) + agentic subtasks (Layer 2)
- **Medical underwriting orchestration**: Node pattern + immutable state mirrors blueprint design
- **Scoped rule files**: Validates CLAUDE.md approach; suggests directory-scoped rules
- **MCP integration**: Toolshed concept applies to medical reference + regulatory lookup tools
- **Validation layers**: Pre-push linting mirrors Layer 3 validation (schema → domain → consistency)

### Extends Understanding:
- **Parallelization**: Devbox isolation suggests container-based case processing
- **One-shot design**: Minions' approach to scoping and context gathering
- **Feedback loops**: Multi-layer validation (local → CI → human) mirrors medical workflow
- **Infrastructure leverage**: Use existing validation frameworks, not custom ones

---

## Areas for Further Exploration

1. **Container isolation for medical processing**: Can we apply devbox pattern to individual case processing?
2. **Medical Toolshed**: What MCP tools would be essential for underwriting? (condition lookup, lab ranges, mortality tables, compliance rules)
3. **Underwriting blueprints**: Explicit blueprint for medical extraction → pricing → routing (similar to Minions' state machine)
4. **Auto-fix capability**: Can we auto-fix common validation failures (e.g., "Weight not in valid range" → "Did you mean X?")

---

## Questions for Product Team

1. **Scope clarity**: Are cases well-scoped (single applicant, single document, clear decision point) like Minions' PRs?
2. **Context richness**: What metadata/context is available for each case? (applicant history, previous decisions, medical guidelines)
3. **Feedback loops**: What are acceptable failure modes? (human review, escalation, rejection)
4. **One-shot vs. iteration**: Should agents iterate on failures, or route to humans after first attempt?

---

## Metrics (Stripe Minions)

- **Scale**: 1,300+ PRs/week completely minion-produced (up from 1,000 in Part 1)
- **Autonomy**: No human-written code in minion PRs, only human code review
- **Parallelization**: Engineers run 5-6 minions in parallel without overhead
- **Reliability**: Deterministic steps (linting, testing, pushing) guarantee completeness
- **Efficiency**: Multi-layer feedback (pre-push, local, CI) keeps iteration cost low

---

## Implementation Patterns to Copy

1. **Blueprint pattern**: Alternating deterministic + agentic nodes
2. **Devbox warming**: Pre-computed state ready in seconds
3. **Scoped rules**: Just-in-time context by directory/pattern
4. **MCP tool curation**: Per-task subset of available tools
5. **Pre-push validation**: Fast feedback before expensive CI runs
6. **Max CI rounds**: Limit iteration (e.g., 2 rounds) to balance speed vs. completeness
7. **Slack-first UX**: Trigger from where work is discussed, not special tool UI
