# Agentic Reasoning in Document AI

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Document AI Course](../sources/2026-04-10_document-ai-course.md), Lessons 1, 3-4

## Definition

**Agentic reasoning**: A system that plans what to do, takes action, observes the result, and iteratively refines until quality threshold is met.

**Loop**: Plan → Act → Observe → Refine → (Repeat until done)

---

## Why Agentic Beats Rigid Pipelines

### The Pipeline Problem

**Traditional pipeline** (Lesson 1):
```
Image → OCR → Regex Rules → JSON Output
```

**Failures**:
- If OCR is wrong → regex fails → wrong output
- If layout changes slightly → regex fails
- No ability to recover; one error cascades

**Why it fails**: No **reasoning**. Just mechanical steps with no understanding.

### The Agentic Approach

**Agentic system** (Lessons 3-4):
```
Document → Agent Reasons → "What type of doc is this? What regions exist?"
          ↓
        Chooses Tools → "Use table-reader for this region, VLM for that figure"
          ↓
        Gets Results → "Got text from table, got description from VLM"
          ↓
        Verifies → "Do these results make sense together? Are there inconsistencies?"
          ↓
        If Uncertain → Re-run, try different approach, gather more context
          ↓
        Return Answer → Confidence score; visual grounding
```

**Why it works**: System can **reason** about what to do, adapt to changes, handle novel situations.

---

## The ReAct Pattern

**ReAct** = Reasoning + Acting

Introduced in Lesson 1, this is the core loop:

### 1. Think
**Agent reasons** about the situation:
- "I'm looking at a utility bill"
- "It has a header with account info, then line items, then a total"
- "To answer the question 'What is the total?', I need to find the total line"

### 2. Act
**Agent takes action** (calls a tool):
- "I'll use the OCR tool to extract text from the document"

### 3. Observe
**Agent observes result**:
- OCR output: `[list of text regions with coordinates]`
- "I got text; let me find the 'total' word"

### 4. Think Again
**Agent reasons** about the result:
- "I found 'total' on line 15. The value next to it is $2,500"
- "But I also see 'subtotal' on line 10 with value $2,300"
- "I need to be careful; 'total' usually comes after subtotal"

### 5. Act Again
If uncertain, take another action:
- "Let me use the LLM to interpret the context"
- LLM reasons: "This is a utility bill. Line 15 is at the bottom, line 10 is at the top. Bottom total is final total."

### 6. Conclude
**Agent returns answer** with confidence:
- Answer: $2,500
- Confidence: High (position + context confirm)
- Source: Line 15, word 'total'

---

## Tool-Calling Agents

A key mechanism in agentic systems: **tools** the agent can call.

### Example Tools (from Lesson 3)

When analyzing a document with charts and tables:

**Tool 1: extract_text**
```python
def extract_text(image, region_bbox):
  """Extract text from a specific region"""
  cropped = image.crop(region_bbox)
  text = ocr(cropped)
  return text
```

**Tool 2: analyze_chart**
```python
def analyze_chart(image, region_bbox):
  """Analyze a chart; extract trends, data points, axes"""
  cropped = image.crop(region_bbox)
  analysis = vlm(cropped, prompt="Describe this chart...")
  return analysis
```

**Tool 3: analyze_table**
```python
def analyze_table(image, region_bbox):
  """Extract table structure and data"""
  cropped = image.crop(region_bbox)
  table = table_transformer(cropped)  # outputs CSV/HTML
  return table
```

### Agent Decides Which Tool to Use

Given question: "What were Q1 revenue and Q2 revenue?"

**Agent reasoning**:
1. "I see a chart and a table in the document"
2. "Revenue is typically in tables for financial docs"
3. "I'll try the table first"
4. Call `analyze_table` on table region
5. Extract Q1 and Q2 revenues
6. Verify: "Did I find both values? Yes."
7. If table extraction is uncertain, try `analyze_chart` as backup

**Key**: Agent chose the tool based on reasoning, not because it was hardcoded.

---

## Quality Verification

Agentic systems don't stop at first attempt; they verify quality.

### Self-Verification Loop

1. **Generate answer** (using tool)
2. **Assess confidence** (model returns confidence score)
3. **Check for inconsistencies**:
   - "I extracted income from three sources; do they agree?"
   - "This person's age is 25 but birthdate shows 1995; does math check out?" (2025-1995=30, not 25)
4. **If uncertain** → Re-run, try different approach, gather more context
5. **If verified** → Return answer with confidence

### Example (from Lesson 4 lab)

Extracting fields from utility bill:

**First pass**:
- Uses ADE to extract account number, charges, due date

**Verification**:
- "All extractions high confidence? Yes"
- "Are there any contradictions?" No
- "Return results"

If extractions had low confidence or contradictions:
- "Flag for human review"
- "Provide visual grounding"
- "Request clarification"

---

## When Agentic Beats Specialist Tools

| Situation | Specialist Tool | Agentic System |
|-----------|-----------------|----------------|
| **Document type fixed** | ✅ Best (optimized) | ✓ Works |
| **Document type varies** | ❌ Must build separate | ✅ Adapts |
| **Layout changes** | ❌ Breaks | ✅ Adjusts |
| **Complex reasoning** | ❌ Can't | ✅ Plans approach |
| **Error recovery** | ❌ Fails hard | ✅ Retries, tries alternatives |
| **Novel situations** | ❌ Not designed for | ✅ Can reason about it |
| **Speed critical** | ✅ Faster | ⚠️ Slower (multiple steps) |
| **Compliance proof** | Depends | ✅ Shows reasoning |

---

## Relevance to DAC-UW

Insurance underwriting involves agentic reasoning naturally.

### Underwriter's Mental Process

1. **Think**: "This is a life insurance application; I need medical + financial + identity info"
2. **Act**: "Let me request documents from applicant"
3. **Observe**: "I got a medical report, bank statement, passport"
4. **Think**: "Medical report mentions hypertension; that's a risk factor"
5. **Act**: "Let me check income from bank statement"
6. **Observe**: "Income is $50K/year; for insurance amount requested ($500K), that's an outlier"
7. **Think**: "Income seems low for requested coverage; let me verify tax returns"
8. **Act**: "Request last 2 years tax returns"
9. **Observe**: "Tax returns show $200K average income; applicant claimed $50K" (inconsistency)
10. **Think**: "Discrepancy requires clarification; may indicate fraud risk"
11. **Conclude**: "Request applicant to explain income difference; flag for manual review"

**Agentic system should do the same**:

```
DAC-UW Agent:
1. Receives application documents
2. Plans: "Need to extract identity, medical, financial info"
3. Acts: Calls ADE to parse each document
4. Observes: Gets extracted fields + visual grounding
5. Verifies: Checks consistency across documents
6. Flags: "Income discrepancy between stated ($50K) and tax return ($200K)"
7. Queries: "Get more context; are there recent raises?"
8. Decides: "Recommend manual underwriting review; flag for fraud risk"
9. Reports: Presents findings + visual proof (show contradicting documents side-by-side)
```

---

## Implementation

### With LangChain (Lesson 1, 3)

```python
from langchain.agents import create_react_agent, AgentExecutor

agent = create_react_agent(
  llm=OpenAI(...),  # The reasoning engine
  tools=[ocr_tool, analyze_chart_tool, analyze_table_tool],
  prompt=system_prompt
)

executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

result = executor.invoke({"input": "What were net sales in 2023?"})
# Agent runs the ReAct loop automatically
```

### With Strands Agents (Lesson 6)

```python
from strands.agents import Agent

agent = Agent(
  model="claude-opus-4-6",
  system_prompt="You are a medical insurance underwriting assistant...",
  tools=[
    search_knowledge_base,
    calculate_risk_score,
    flag_for_review,
  ],
  memory=agent_memory,  # Remembers past interactions
)

response = agent.invoke(
  input="Does applicant have pre-existing conditions?",
  actor_id="underwriter_123",
  session_id="case_456"
)
# Agent runs ReAct loop + maintains memory
```

---

## Limitations

### What Agentic Systems Don't Solve

- ❌ **Domain knowledge**: Agent can't reason about insurance risk without underwriting rules
- ❌ **Policy enforcement**: Agent calls tools; you implement business logic
- ❌ **Liability**: Agent recommends; human makes final decision

**Implication**: Agentic document extraction is layer 1 (information extraction); you need layer 2 (business logic) and layer 3 (human oversight).

---

## See Also

- [Lesson 1: Why OCR Fails](./lesson-1-why-ocr-fails.md) — Introduction to agentic approach
- [Lesson 3: Layout Detection & Reading Order](./lesson-3-layout-and-reading-order.md) — Agentic routing to tools
- [Lesson 4: Agentic Document Extraction](./lesson-4-agentic-document-extraction.md) — Full implementation
- [Entity: Strands Agents](../entities/strands-agents.md) — Framework for building agents
