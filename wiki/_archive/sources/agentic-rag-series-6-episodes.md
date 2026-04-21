# AI Automators: Claude Code Agentic RAG Series (6 Episodes)

**Source**: https://github.com/theaiautomators/claude-code-agentic-rag-series  
**Type**: Educational Video Series + Reference Implementation  
**Author**: The AI Automators  
**Date Ingested**: 2026-04-09  
**Related Topics**: [RAG: Retrieval-Augmented Generation](../topics/rag-retrieval-augmented-generation.md), [Agent Orchestration & Frameworks](../topics/agent-orchestration.md), [Agent Harness: Deterministic Phases](../topics/agent-harness-deterministic-phases.md)  

---

## Overview

A progressive 6-episode learning series building RAG (Retrieval-Augmented Generation) systems from foundational chat + search to fully autonomous agents with deterministic workflow harnesses. Each episode adds capabilities and includes PRDs, prompts, planning documents, and working implementations.

**Thesis**: "The model is commoditized. Structured enforcement of process is the moat."

---

## The Six Episodes: Progressive Capabilities

### Episode 1: Agentic RAG Masterclass
**Focus**: Foundational RAG architecture  
**Outputs**: Chat UI, document ingestion, hybrid search, tool calling, sub-agents

**Components**:
- **Frontend**: React + TypeScript + Tailwind + shadcn/ui (Vite)
- **Backend**: Python FastAPI orchestrating RAG logic
- **Database**: Supabase (PostgreSQL + pgvector for vector search)
- **Document Processing**: Docling for multi-format ingestion
- **Models**: OpenAI, OpenRouter, LM Studio (local option)
- **Observability**: LangSmith for trace visibility

**Architecture Flow**:
```
Chat UI (React)
    ↓
FastAPI Backend
    ↓
Document Processor (Docling)
    ↓
Supabase (pgvector + semantic search)
    ↓
LLM + Tool Calling
    ↓
Response to User
```

**Key Patterns**:
- Managed RAG using OpenAI Responses API (starting point before custom pipelines)
- Chat persistence via Supabase
- Modular progression: 8 sequential modules increasing complexity
- Collaborative development: "Claude writes code, you guide and course-correct"

**For DAC-UW-Agent**:
- Document ingestion pipeline (medical PDFs) can follow Episode 1 patterns
- Hybrid search (medical field names + semantic meaning) applies to case lookup
- Sub-agents pattern hints at multiple underwriting sub-agents (extraction, pricing, compliance)

---

### Episode 2: Knowledge Base Explorer
**Focus**: Hierarchical knowledge navigation  
**Outputs**: Filesystem-like tools for knowledge discovery

**Key Capabilities**:
- **Filesystem-style navigation**: `ls()`, `cd()`, `find()` tools for knowledge traversal
- **Hierarchical organization**: Folders → subfolders → documents (tree structure)
- **Smart discovery**: Full-text search within hierarchical context
- **Context-aware retrieval**: Agent can explore knowledge structure to understand what exists before querying

**Architecture Pattern**:
```
Knowledge Base (hierarchical folders)
    ↓
File Explorer Tools (ls, cd, find, cat)
    ↓
Agent can navigate and discover before extracting
```

**For DAC-UW-Agent**:
- Medical reference knowledge could be organized hierarchically:
  ```
  /medical_reference/
    /conditions/
      /diabetes/
      /hypertension/
    /lab_ranges/
    /medications/
  ```
- Underwriting agent can explore structure: "Show me all lab tests for diabetes"
- Alternative to flat MCP tool catalog

---

### Episode 3: PII Redaction & Anonymization
**Focus**: Privacy protection before cloud API calls  
**Outputs**: PII redaction layer ensuring sensitive data never reaches cloud LLMs

**Key Capabilities**:
- **Automated PII detection**: Identify names, addresses, SSNs, medical IDs
- **Redaction strategy**: Remove or hash sensitive fields
- **Compliance-aware**: Ensures HIPAA, GDPR, data privacy compliance
- **Local processing**: Redaction happens before cloud LLM call

**Workflow**:
```
Raw Medical Document (with PII)
    ↓
Local PII Detector
    ↓
Redact: Replace PII with placeholders (e.g., "PATIENT_001")
    ↓
Safe Document to Cloud LLM
    ↓
Results re-mapped to original applicant (after LLM processing)
```

**For DAC-UW-Agent**:
- **Critical for Cambodia IRC compliance**: IRC article 5 requires data privacy protection
- Before sending medical PDFs to Claude for extraction: redact patient names, IDs, addresses
- Keep mapping: PATIENT_001 → actual applicant ID (server-side only)
- Demonstrates responsible AI use to regulators

**Privacy Pattern**:
```python
# Local redaction (before API call)
redacted_doc, mapping = redact_pii(medical_pdf)
extracted_data = claude.extract_medical(redacted_doc)  # Safe API call
applicant_data = remap_to_original(extracted_data, mapping)  # Server-side only
```

---

### Episode 4: Agent Skills & Code Sandbox
**Focus**: Reusable agent capabilities + isolated code execution  
**Outputs**: Skills system + Docker-based Python sandbox

**Key Capabilities**:
- **Skills library**: Composable agent actions (e.g., `skill_extract_text`, `skill_analyze_document`)
- **Docker sandbox**: Execute Python code in isolated container
- **Execution safety**: Code runs in restricted environment, no access to host
- **Result capture**: Output JSON from sandbox execution

**Architecture**:
```
Agent decides: "I need to run Python analysis"
    ↓
Skill selected: skill_analyze_csv
    ↓
Python code → Docker container
    ↓
Results captured (JSON)
    ↓
Agent integrates results
```

**For DAC-UW-Agent**:
- **Skill: extract_medical** → Claude Vision in sandbox
- **Skill: price_applicant** → GLM pricing model in sandbox
- **Skill: validate_medical_data** → Schema validation in sandbox
- Each skill runs independently, results flow to next skill
- Enables reproducibility: same skill run twice = same results

**Sandbox Benefits**:
- Deterministic execution (no API variability)
- Reproducible results for audit trail
- Safe execution of untrusted code (if future expansion)
- Isolated from main process

---

### Episode 5: Advanced Tool Calling
**Focus**: Dynamic tool registry + MCP integration  
**Outputs**: Tool discovery, sandbox bridge, MCP servers

**Key Capabilities**:

**1. Dynamic Tool Registry**:
- Problem: Sending all 14+ tools every request = 7K+ tokens overhead
- Solution: Compact tool catalog + `tool_search` for on-demand loading
  - Agent calls `tool_search("medical")` → returns matching tool schemas
  - Only load what's needed (reduces token overhead from 7K to ~500)

**2. Sandbox Bridge**:
- Problem: Executing Python requires sequential tool calls (N round-trips)
- Solution: Python code in sandbox can call platform tools via typed stubs
  - Single Python script in sandbox = multiple tool calls + processing
  - Reduces round-trips, improves efficiency

**3. MCP Integration**:
- MCP (Model Context Protocol) servers auto-discovered
- Configuration: `MCP_SERVERS = [("github", "command", "args"), ...]`
- Enables: GitHub, Slack, databases, custom services as tools
- Dynamic: add/remove servers without code changes

**Architecture**:
```
Agent → Tool Search ("medical")
    ↓
Catalog returns matching tools (compact)
    ↓
Agent loads full schema on-demand
    ↓
OR: Agent uses sandbox bridge to call tools from Python
    ↓
OR: Agent calls MCP-integrated external service
```

**For DAC-UW-Agent**:
- **Tool registry**: Medical reference, actuarial tables, compliance rules
  - `tool_search("lab_range")` → lookup_lab_range tool
  - `tool_search("irc")` → lookup_irc_requirement tool
  - `tool_search("glm")` → lookup_glm_parameter tool

- **Sandbox bridge**: 
  - Extraction agent runs Python + Claude Vision in sandbox
  - Can call validation tools from within Python
  - Single orchestrated execution vs. sequential tool calls

- **MCP integration**: 
  - Connect to regulatory databases (IRC articles)
  - Connect to internal case management system (past decisions)
  - Connect to actuarial data warehouse (mortality tables)

---

### Episode 6: Agent Harness & Workflows
**Focus**: Deterministic phase-based workflows + autonomous agents  
**Outputs**: Agent harness, Deep Mode autonomous agent, domain-specific workflows

**Key Concept**: 
> "The model is commoditized. Structured enforcement of process is the moat."

The harness is a **state machine** enforcing deterministic workflow phases, not letting the LLM decide everything.

#### Deep Mode Autonomous Agent

LLM controls its own flow:
- Create and manage todo lists
- Maintain persistent workspace filesystem
- Delegate tasks to sub-agents
- Pause to ask clarifying questions
- Per-message activation of capabilities

**Benefits**:
- Flexible problem-solving (agent adapts to novel situations)
- Persistent state (survives disconnections)
- Self-directed (no rigid workflow required)

**Drawbacks**:
- Less predictable (LLM decides flow)
- Harder to enforce constraints
- Higher token usage (full context each round)

#### Agent Harness Framework

System enforces deterministic workflow, not the LLM:

**Phase Types**:
1. **Programmatic** — Pure Python, no LLM (deterministic)
2. **LLM Single** — One LLM call with structured JSON output
3. **LLM Agent** — Multi-round agent loop with tools (scoped subtask)
4. **LLM Batch Agents** — Parallel sub-agents (e.g., 5 concurrent)
5. **LLM Human Input** — Pause for user context before proceeding

**Example: Contract Review Harness** (8 phases)
```
Phase 1 (Programmatic): Intake document
Phase 2 (LLM Single): Classify contract type (JSON output)
Phase 3 (LLM Human Input): Gather context from user ("What's your risk tolerance?")
Phase 4 (Programmatic): Fetch relevant standards via RAG
Phase 5 (LLM Agent): Extract clauses (multi-round with tools)
Phase 6 (LLM Batch): Parallel risk analysis on 5 clause types
Phase 7 (LLM Single): Generate redlines (structured JSON)
Phase 8 (Programmatic): Create DOCX report + executive summary
```

**Benefits**:
- Predictable execution flow
- Clear state at each phase (resumable if interrupted)
- Transparent to user (can see progress)
- Easier to test and debug
- Can enforce constraints per-phase

**Harness vs. Blueprint**:
- **Blueprint** (Stripe): Deterministic nodes + agentic nodes, iterative
- **Harness** (AI Automators): Deterministic phases with embedded LLM calls, sequential

Both achieve: "Contain LLM creativity in boxes with deterministic validation gates"

#### Domain-Specific Implementation: Contract Review

**Workflow** (8 phases):
1. Document intake (file validation)
2. Classification (contract type: NDA, Service, Licensing, etc.)
3. Human context (user input on priorities)
4. Playbook RAG (fetch relevant risk framework)
5. Clause extraction (agent + tools finds relevant sections)
6. Risk analysis (5 batched sub-agents analyze clauses in parallel)
7. Redline generation (structured LLM output: suggested changes)
8. Summary report (DOCX with executive summary)

**Key Patterns**:
- **Workspace artifacts**: Each phase produces files consumed by next phase
  - Phase 2 outputs: classification.json
  - Phase 3 outputs: user_context.json
  - Phase 4 outputs: relevant_standards.txt
  - Phase 5 outputs: clauses_extracted.json
  - Phase 6 outputs: risk_analysis.json
  - Phase 7 outputs: redlines.json
  - Phase 8 outputs: summary.docx

- **Batched sub-agents**: 5 concurrent risk analysts (parallel processing)

- **Mid-workflow human input**: Gather context before expensive analysis

- **Resumability**: If interrupted, resume from last complete phase

- **Transparency**: User sees progress through each phase

**For DAC-UW-Agent (Medical Underwriting Harness)**:

Could implement 7-8 phases:
```
Phase 1 (Programmatic): Intake applicant PDF
Phase 2 (LLM Single): Classify document type (medical form, lab results, scan) → JSON
Phase 3 (LLM Human Input): Gather context ("Is this a returning applicant? Any special conditions?")
Phase 4 (Programmatic): Fetch medical reference data via RAG
Phase 5 (LLM Agent): Extract medical fields (multi-round with tools, validation feedback)
Phase 6 (Programmatic): Validate extracted data (schema + domain + consistency)
Phase 7 (Programmatic): Run Frequency-Severity GLM pricing
Phase 8 (LLM Single): Generate explanation + routing decision (JSON)
Phase 9 (Programmatic): Create audit trail + DOCX report
```

---

## Tech Stack & Deployment

**Frontend**: React (TypeScript, Tailwind, shadcn/ui, Vite)  
**Backend**: Python (FastAPI, Pydantic for validation)  
**Database**: Supabase (PostgreSQL, pgvector, auth, file storage)  
**Document Processing**: Docling (multi-format: PDF, DOCX, images)  
**Execution**: Docker (sandboxed Python)  
**Orchestration**: Agent harness (deterministic state machine)  
**Integration**: MCP (Model Context Protocol)  
**Observability**: LangSmith  

**Deployment Options**:
- Local: Docker + self-hosted Supabase
- Cloud: Vercel (frontend) + Supabase Cloud (backend)

---

## Key Architectural Insights

### 1. RAG is Table Stakes, Not Differentiation
Episodes 1-3 establish RAG, but the differentiator comes from Episodes 5-6:
- Tool registry and MCP integration (how to access knowledge)
- Agent harness (how to structure workflows deterministically)

### 2. Determinism + Structured LLM Calls > Pure Agent Loops
- Episode 6's harness enforces phase structure (not pure agentic flow)
- Each phase has curated tools and focused prompt
- Reduces context overhead vs. full 400-line system prompt
- Enables resumability and state inspection

### 3. Token Efficiency Through Lazy Loading
- Episode 5's tool registry avoids sending all tools every request
- `tool_search` reduces overhead from 7K → ~500 tokens
- Scales to 100+ tools without context bloat

### 4. Sandbox Execution Enables Determinism
- Episode 4's Docker sandbox makes code reproducible
- No API variability, no hallucinations in computation
- Suitable for audit trails and compliance

### 5. Privacy Is a First-Class Layer
- Episode 3's PII redaction happens before LLM call
- Demonstrates to regulators: "We protect sensitive data"
- Enables HIPAA/GDPR/IRC compliance

---

## Connections to DAC-UW-Agent

| DAC-UW-Agent Layer | AI Automators Episode | Relevant Pattern |
|---|---|---|
| **Intake (AI Layer 2a)** | Ep1 (RAG), Ep4 (Sandbox) | Document ingestion + isolated extraction |
| **Pricing (Core Engine 1)** | Ep4 (Skills) | GLM pricing as reusable skill |
| **Validation (Control 3)** | Ep1 (RAG), Ep5 (Tools) | Schema validation + tool-based checking |
| **Routing (Control 3)** | Ep6 (Harness) | Deterministic phase determining path |
| **Explanation (Control 3)** | Ep5 (Tool Registry) | Structured output for rationale |
| **Audit (Trust 4)** | Ep6 (Harness) | Workspace artifacts = audit trail |
| **Overall Orchestration** | Ep6 (Harness) | Phase-based workflow with constraints |
| **Privacy** | Ep3 (Redaction) | PII protection before API calls |

---

## Questions for Implementation

1. **Harness vs. Blueprint**: Should medical underwriting use episode 6's deterministic phases or Stripe's blueprint pattern (mixed agentic + deterministic nodes)?
   - **Harness advantage**: Clear phase structure, easy to resume, transparent to user
   - **Blueprint advantage**: Agentic loops allow retries within a node, more flexible

2. **Tool Registry**: Build dynamic tool search or curated subsets per node?
   - **Dynamic**: Agent discovers tools as needed (Episode 5 pattern)
   - **Curated**: Each phase has pre-defined tools (simpler, predictable)

3. **Workspace Artifacts**: Should each phase output files (like contract review example)?
   - Enables resumability and debugging
   - Adds complexity (filesystem management, cleanup)

4. **Sandbox Execution**: Use Docker for medical extraction + pricing?
   - Ensures reproducibility
   - Adds infrastructure overhead

5. **MCP Integration**: What external systems should be available as MCP servers?
   - Case management system (past decisions)
   - Medical reference database
   - Actuarial data warehouse
   - Regulatory database (IRC articles)

---

## References

- **GitHub**: https://github.com/theaiautomators/claude-code-agentic-rag-series
- **YouTube Series**: The AI Automators channel (6 episodes with full walkthroughs)
- **Implementation**: Each episode folder contains PRDs, prompts, planning docs, and reference code
- **Community**: The AI Automators website for full codebase access and learning resources
