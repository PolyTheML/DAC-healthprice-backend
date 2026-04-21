# Dynamic Tool Registry & Discovery

**Last Updated**: 2026-04-09  
**Source**: [AI Automators: Agentic RAG Series — Episode 5](../sources/agentic-rag-series-6-episodes.md)  
**Type**: System Design Pattern  

---

## Problem: Tool Catalog Bloat

### Naive Approach (Inefficient)
When an agent has access to many tools, sending all tool schemas every request wastes tokens:

```python
# Naive: Every LLM call includes all tool definitions
tools = [
  lookup_lab_range,
  lookup_condition_criteria,
  lookup_medication_contraindications,
  lookup_comorbidity_patterns,
  validate_medical_data,
  lookup_irc_requirement,
  lookup_glm_parameter,
  # ... 93 more tools ...
]

# Token cost: ~7,000 tokens just to describe all tools
response = claude.messages.create(
    model="claude-3-5-sonnet",
    messages=messages,
    tools=tools  # All 100 tools, every request!
)
```

**Problems**:
- 7,000+ tokens per request just for tool definitions
- Agent confused by too many tools (which one to use?)
- Many tools irrelevant to current task
- Scales poorly (100 tools = 7K tokens; 500 tools = 35K tokens)

### Stripe's Observation
Stripe had same problem with Minions. Solution: **scoped rule files** (attach by directory). 

We adapt this to tools: **dynamic tool discovery**.

---

## Solution: Dynamic Tool Registry

Instead of sending all tools, the agent discovers tools on-demand.

### Architecture

```
Agent: "I need to look up lab ranges"
    ↓
Agent calls: tool_search("lab_range")
    ↓
Registry returns: [lookup_lab_range, lookup_lab_normal_range, lookup_lab_interpretation]
    ↓
Agent loads full schema for chosen tool
    ↓
Agent calls tool with parameters
    ↓
Result → agent continues
```

### Token Comparison

**Before (All Tools Every Request)**:
```
System prompt:           500 tokens
Tool definitions (100):  7,000 tokens
User message:           100 tokens
Conversation history:   2,000 tokens
Total:                  9,600 tokens
```

**After (Dynamic Registry)**:
```
System prompt:           500 tokens
Tool search result:      200 tokens (compact catalog)
Tool schema (1 tool):    300 tokens
User message:           100 tokens
Conversation history:   2,000 tokens
Total:                  3,100 tokens
```

**Savings**: ~66% reduction (9,600 → 3,100 tokens)

---

## Implementation Pattern

### 1. Tool Registry (Data Structure)

A catalog of all available tools with metadata:

```python
TOOL_REGISTRY = {
    "medical": {
        "lookup_lab_range": {
            "description": "Fetch normal reference ranges for lab test",
            "category": "medical_reference",
            "keywords": ["lab", "range", "normal", "reference"]
        },
        "lookup_condition_criteria": {
            "description": "Fetch diagnostic criteria for medical condition",
            "category": "medical_reference",
            "keywords": ["condition", "diagnosis", "criteria"]
        },
        # ... more medical tools
    },
    "regulatory": {
        "lookup_irc_requirement": {
            "description": "Fetch Cambodia IRC article requirement",
            "category": "regulatory",
            "keywords": ["irc", "cambodia", "regulation", "compliance"]
        },
        # ... more regulatory tools
    },
    "actuarial": {
        "lookup_glm_parameter": {
            "description": "Fetch GLM coefficient and bounds",
            "category": "actuarial",
            "keywords": ["glm", "parameter", "coefficient", "risk"]
        },
        # ... more actuarial tools
    }
}
```

### 2. Tool Search Function

Agent can search for tools by keyword:

```python
def tool_search(query: str) -> list[dict]:
    """Search tool registry by keyword/pattern."""
    results = []
    query_lower = query.lower()
    
    for category, tools in TOOL_REGISTRY.items():
        for tool_name, metadata in tools.items():
            # Match keywords or description
            if (query_lower in tool_name or
                any(kw in query_lower for kw in metadata["keywords"]) or
                query_lower in metadata["description"].lower()):
                
                results.append({
                    "tool_name": tool_name,
                    "description": metadata["description"],
                    "category": metadata["category"]
                })
    
    return results
```

### 3. Lazy Loading: Tool Schema On-Demand

Agent searches, finds tools, then loads full schema:

```python
# Step 1: Agent searches
> tool_search("lab_range")
< Returns: [{tool_name: "lookup_lab_range", description: "...", category: "medical"}]

# Step 2: Agent requests full schema
> get_tool_schema("lookup_lab_range")
< Returns full JSON schema (300 tokens):
{
    "name": "lookup_lab_range",
    "description": "Fetch normal lab ranges",
    "input_schema": {
        "type": "object",
        "properties": {
            "test_name": {
                "type": "string",
                "description": "Name of lab test (e.g., 'Fasting Glucose')"
            },
            "age": {
                "type": "integer",
                "description": "Patient age (optional)"
            }
        },
        "required": ["test_name"]
    }
}

# Step 3: Agent calls tool
> lookup_lab_range(test_name="Fasting Glucose", age=45)
< Returns: {
    "test": "Fasting Glucose",
    "normal_range": {"low": 70, "high": 100, "unit": "mg/dL"},
    "fasting_required": true
}
```

**Token Usage**: 200 tokens for search, 300 tokens for schema = 500 total (vs. 7K for all tools)

---

## Tool Registry Organization

### By Category
Group tools by domain:

```
Medical Reference:
  - lookup_lab_range
  - lookup_condition_criteria
  - lookup_medication_contraindications

Actuarial:
  - lookup_glm_parameter
  - lookup_mortality_table
  - lookup_risk_tier_examples

Regulatory:
  - lookup_irc_requirement
  - lookup_fair_lending_guidelines
  - lookup_audit_trail

Case Reference:
  - lookup_precedent_decisions
  - lookup_average_premium
  - lookup_applicant_history
```

### By Phase (Agent Harness Context)

Each harness phase gets curated tools:

```python
# Phase 2: Classify Document
PHASE_TOOLS = {
    "classify": [
        # Just search and classify
        tool_search,  # Can search available tools
        # No execution tools yet
    ]
}

# Phase 5: Extract Medical Fields
PHASE_TOOLS = {
    "extract": [
        tool_search,
        lookup_lab_range,
        lookup_condition_criteria,
        validate_medical_data,
        # NOT: glm_parameter, irc_requirement (irrelevant to extraction)
    ]
}

# Phase 8: Generate Explanation
PHASE_TOOLS = {
    "explain": [
        tool_search,
        lookup_irc_requirement,  # For explaining compliance
        lookup_precedent_decisions,  # For benchmarking
        lookup_average_premium,  # For context
        # NOT: lookup_lab_range (already extracted)
    ]
}
```

**Benefit**: Each phase has ~5-10 tools, not 100. Context window stays small.

---

## Advanced: Sandbox Bridge

Episode 5 extends this to enable Python code in sandbox to call tools **without sequential round-trips**.

### Problem: Sequential Tool Calls

Agent wants to:
1. Look up lab range for Fasting Glucose
2. Compare applicant's value to range
3. Determine if abnormal
4. If abnormal, look up related condition criteria
5. Generate assessment

Naive approach: 4 separate tool calls = 4 round-trips (expensive, slow).

### Solution: Sandbox Bridge

Agent writes Python code, runs in sandbox, calls tools from code:

```python
# Agent writes this Python code
def analyze_lab(test_name, applicant_value, age):
    # Call tools from within Python
    lab_range = lookup_lab_range(test_name=test_name, age=age)
    
    if applicant_value < lab_range["normal_range"]["low"]:
        status = "low"
    elif applicant_value > lab_range["normal_range"]["high"]:
        status = "high"
    else:
        status = "normal"
    
    result = {
        "test": test_name,
        "applicant_value": applicant_value,
        "normal_range": lab_range["normal_range"],
        "status": status
    }
    
    if status != "normal":
        condition_info = lookup_condition_criteria("abnormal_lab_result")
        result["further_investigation"] = condition_info
    
    return result

# Single sandbox execution: 4 tool calls, 1 round-trip
response = execute_code(analyze_lab("Fasting Glucose", 125, 45))
```

**Benefits**:
- One round-trip instead of four
- Agent can do logic (if/else, loops) inside sandbox
- Deterministic execution (Python, not LLM)
- Reduced token overhead

---

## MCP Integration: External Tool Servers

Model Context Protocol (MCP) enables dynamic tool discovery from external servers:

### Setup

```python
# Configuration
MCP_SERVERS = [
    ("github", "github-server", "--token $GITHUB_TOKEN"),
    ("slack", "slack-server", "--token $SLACK_TOKEN"),
    ("medical_db", "medical-server", "--url http://medical:5000"),
]
```

### Discovery

```python
# Agent asks: what MCP tools are available?
available_mcp_tools = await discover_mcp_tools()
# Returns: [pull_request_search, slack_message, lookup_patient_record, ...]

# Search MCP registry
tool_search("medical")  # Searches both local + MCP tools
# Returns: [lookup_lab_range, lookup_condition_criteria, lookup_patient_record, ...]
```

### Usage

```python
# Call external MCP tool (transparently)
result = lookup_patient_record(applicant_id="APP_123")
# Under the hood: agent → MCP client → medical_db server → result
```

---

## Design Decisions

### 1. Search vs. Curated Subsets

**Dynamic Search Approach** (Episode 5):
```python
# Agent searches, discovers tools on-demand
tools_needed = tool_search("medical")
```

**Pros**: Flexible, agent adapts to new tools, no manual configuration  
**Cons**: Agent might find wrong tool, slower discovery

**Curated Subsets Approach** (Harness):
```python
# Phase 5 has pre-defined tools
PHASE_5_TOOLS = [lookup_lab_range, lookup_condition_criteria, validate_data]
```

**Pros**: Fast, predictable, no discovery overhead  
**Cons**: Less flexible, need to maintain per-phase configs

**Recommendation for DAC-UW-Agent**: Hybrid
- Core tools per phase (curated, fast)
- tool_search available for edge cases (flexible)
- Best of both worlds

### 2. Tool Discoverability

**Metadata**: Each tool has keywords for discovery
```python
lookup_lab_range:
  keywords: ["lab", "range", "normal", "reference", "glucose", "hemoglobin"]
```

**Searchable Description**:
```python
lookup_lab_range:
  description: "Fetch normal reference ranges for medical lab tests. Includes fasting requirements, units, and specimen collection."
```

### 3. Tool Versioning

As tools evolve, maintain backwards compatibility:

```python
lookup_lab_range:
  version: "2"
  deprecated_versions: ["1"]  # Old version still works
  breaking_changes: "version 2: 'fasting_required' is now 'requires_fasting'"
```

### 4. Rate Limiting

If tools are external APIs, consider quotas:

```python
# Each agent phase gets quota
PHASE_QUOTAS = {
    "extract": {"lookup_lab_range": 50},  # Max 50 lab lookups per case
    "pricing": {"lookup_glm_parameter": 10},  # Max 10 GLM parameter lookups
}
```

---

## Implementation Checklist

- [ ] Build tool registry data structure (category + metadata)
- [ ] Implement `tool_search(query)` function
- [ ] Implement `get_tool_schema(tool_name)` lazy loading
- [ ] Organize tools by category or phase
- [ ] Create curated tool subsets for each harness phase
- [ ] Test tool discovery (search finds intended tools)
- [ ] Measure token savings (compare all-tools vs. dynamic)
- [ ] Add tool versioning (backwards compatibility)
- [ ] Document tool metadata (keywords, description, examples)
- [ ] (Optional) Implement sandbox bridge for Python execution
- [ ] (Optional) Integrate MCP servers for external tools

---

## Token Budget Estimation

**Case**: Medical underwriting (extract, validate, price, explain)

**All-Tools Approach** (naive):
```
Tool definitions (100 tools):    7,000 tokens
Per request overhead:            7,000 tokens × 3 requests = 21,000 tokens total
```

**Dynamic Registry Approach**:
```
Tool search (3 searches):        200 tokens × 3 = 600 tokens
Tool schemas (3 tools):          300 tokens × 3 = 900 tokens
Per request overhead:            1,500 tokens total
```

**Savings**: 21,000 → 1,500 = **93% reduction** (20,500 tokens saved per case)

At 100 cases/day: **2 million tokens/day saved** = **$0.30/day** at Claude pricing

---

## References

- [AI Automators: Agentic RAG Series — Episode 5](../sources/agentic-rag-series-6-episodes.md) — Dynamic tool registry, sandbox bridge, MCP integration
- [Agent Context Engineering at Scale](./agent-context-engineering-at-scale.md) — Scoped context per phase/task
- [Agent Harness: Deterministic Phases](./agent-harness-deterministic-phases.md) — Tool curation per phase
