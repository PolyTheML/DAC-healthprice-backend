# Agent Context Engineering at Scale

**Last Updated**: 2026-04-09  
**Source**: [Stripe Minions: One-Shot Agentic Coding](../sources/stripe-minions-agentic-coding.md)  
**Type**: System Design  

---

## Problem

Large codebases (or large problem domains) create a tension:

- **Too much context**: Agent context window fills with rules before the agent starts working
- **Too little context**: Agent doesn't know domain conventions, best practices, constraints
- **Wrong context**: Agent gets global rules for code it's not touching

At Stripe, 100M+ LOC + homegrown libraries = impossible to fit everything. Solution: **scoped, just-in-time context**.

For DAC-UW-Agent: Medical underwriting domain is smaller, but requires specialized knowledge (medical field ranges, regulatory rules, actuarial conventions).

---

## Context Engineering Strategy

### Layer 1: Static Context (Rule Files)

**Principle**: Attach context just-in-time by directory/file pattern.

**Stripe's Approach**:
- Rule files (Cursor format) attached automatically as agent works
- Example: `src/auth/RULES.md` only loads when agent opens `src/auth/` files
- Scope by directory or file pattern (glob)
- Don't use unconditional global rules

**For DAC-UW-Agent**:

```
sources/
  medical_extraction/
    RULES.md           # "BMI range is 10-60", "extract lab dates as ISO-8601"
  pricing/
    RULES.md           # "Frequency-Severity GLM parameters", "apply Tweedie dist"
  compliance/
    RULES.md           # "IRC article X requires Y", "audit trail must include Z"
  
topics/
  RULES.md             # General knowledge (when to use Claude Vision vs. OCR)
```

**Content Guidelines**:
- **Medical extraction rules**: Field ranges, data types, required fields, mapping conventions
- **Pricing rules**: GLM parameters, risk tiers, premium bounds, edge cases
- **Compliance rules**: Cambodia IRC requirements, audit trail format, decision rationale template

**Benefits**:
- Agent doesn't memorize rules; they're available when needed
- Rules stay close to code (easier to update)
- Different agents (extraction, pricing, compliance) see only relevant rules
- Reduces context window bloat

### Layer 2: Dynamic Context (MCP Tools)

**Principle**: Agents call tools to fetch context dynamically, not bake it into prompts.

**Stripe's Approach**:
- Centralized MCP server ("Toolshed") with 500 tools
- Per-agent curated subset (e.g., minions get 50-100 relevant tools)
- Tools for internal docs, ticket details, build status, code intelligence

**For DAC-UW-Agent**:

Could implement MCP tools for:

1. **Medical Reference Tools**
   - `lookup_lab_range(test_name)` → normal range, units, collection method
   - `lookup_condition_criteria(diagnosis)` → diagnostic criteria, staging
   - `lookup_medication_contraindications(drug_name)` → risk, interactions
   - `lookup_comorbidity_patterns(condition)` → commonly co-occurring conditions

2. **Regulatory Reference Tools**
   - `lookup_irc_requirement(article_number)` → full text, interpretation
   - `lookup_compliance_precedent(case_type)` → similar cases, decisions
   - `lookup_fair_lending_guidelines(attribute)` → what's allowed/prohibited

3. **Actuarial Reference Tools**
   - `lookup_mortality_table(age, gender)` → base mortality rate
   - `lookup_glm_parameter(risk_factor)` → coefficient, bounds, examples
   - `lookup_risk_tier_examples(tier)` → similar cases, benchmark premiums

4. **Case Reference Tools**
   - `lookup_precedent_decisions(applicant_profile)` → similar cases
   - `lookup_average_premium(age, gender, risk_tier)` → market comparison
   - `lookup_audit_trail(case_id)` → prior decisions for same applicant

**Tool Design Principles**:
- **Narrow scope**: Each tool does one thing (lookup, not multi-step reasoning)
- **Structured output**: Return JSON with clear fields (unit, range, source)
- **Cite source**: Every tool result includes where it came from (RFC number, GLM paper, case record)
- **Fallback safe**: If tool fails, provide sensible default, don't hallucinate

**Curated Subsets**:
- **Extraction agent**: Medical reference tools + case reference tools
- **Pricing agent**: Actuarial reference tools + mortality tables
- **Compliance agent**: Regulatory reference tools + audit guidelines
- **Review agent**: All tools + precedent cases

### Layer 3: Implicit Context (User Guidance)

**Principle**: User's task description itself contains rich context.

**Stripe's Approach**:
- Minions triggered from Slack threads (full conversation history is context)
- Links in Slack message automatically fetched
- Previous decisions/comments provide precedent

**For DAC-UW-Agent**:
- Case submission includes: applicant demographics, document list, prior decisions (if returning customer)
- Medical documents themselves are rich context (test results, provider notes)
- Underwriter can provide: "This applicant has Stage 3 diabetes, be thorough in extraction"

**Best Practice**: Let the agent see the "messy reality" (Slack thread, linked docs) rather than distilling into sanitized context.

---

## Context Budget: What Fits?

### Problem Tokens: Stripe Context Budget

Stripe's context allocation for a minion run:

```
Total: ~100k tokens (Claude 200k)

80% Work:  80k tokens for actual code/reasoning
           - Task description: 2k tokens
           - Relevant files: 50k tokens
           - Rule files: 10k tokens
           - Tool call results: 18k tokens

20% Overhead: 20k tokens
           - Conversation turns (agent planning + tool results): 15k
           - System prompt / base context: 5k
```

### DAC-UW-Agent Context Budget

For medical extraction + pricing + routing:

```
Total: ~100k tokens (Claude 200k)

Work: ~70k tokens
  - Applicant medical PDF (converted to text): 10-20k tokens
  - Rule files (medical + pricing + compliance): 5k tokens
  - MCP tool results (lookup_lab_range, lookup_irc, etc.): 5-10k tokens
  - Prior case (if returning customer): 3-5k tokens
  - System prompt (extraction task, validation constraints): 2k tokens
  - Conversation history (extraction feedback, retries): 5k tokens

Reserve: ~30k tokens for:
  - Longer documents
  - Multiple retries
  - Complex edge cases
  - Buffer for uncertainty
```

**Strategy**:
- Inline medical extraction rules (under 1k tokens)
- For compliance rules: reference via MCP tool, not inline
- For actuarial tables: fetch dynamically (MCP), not baked in
- For similar cases: RAG lookup (MCP), not training examples

---

## Implementation: Scoped Rules File Format

### RULES.md Conventions

```markdown
# Medical Extraction Rules (for sources/medical_extraction/)

## Field Definitions

**Age**: 
- Type: integer
- Range: 18-120 years
- Extraction hint: Look for "Date of Birth" or "Age" field
- If unclear: Use patient's stated age, mark confidence < 0.8

**Body Mass Index (BMI)**:
- Type: float
- Range: 10-80 kg/m²
- Calculation: weight_kg / (height_m ** 2)
- Source: [WHO BMI Classification](https://who.int/...)
- Extraction hint: May be pre-calculated on form, or extract weight+height
- If missing: Ask "Can you provide weight and height?"

**Blood Pressure (Systolic)**:
- Type: integer
- Range: 70-250 mmHg (mmHg = millimeters of mercury)
- Format: "SYS/DIA" (e.g., "140/90")
- Extraction hint: "BP:", "Blood Pressure:", table in vital signs
- If unclear: Flag as low confidence

## Consistency Rules

- **Diabetes → glucose lab required**: If Diabetes diagnosis present, must have fasting glucose or HbA1c
- **Hypertension → BP readings required**: If BP > 140/90 or on antihypertensive, must have multiple readings
- **Age → smoking eligibility**: If Age < 18, smoking status should be "never"

## Confidence Scoring

- 0.95+: All fields present, clear, no interpretation needed
- 0.80-0.94: Some fields inferred, minor interpretation, but no ambiguity
- 0.70-0.79: Some fields estimated, field may have multiple interpretations
- <0.70: Major fields missing or highly ambiguous → flag for human review

## Common Extraction Errors

- **Height confusion**: "Height: 5'10"" → Convert to cm (177cm), not feet
- **Age vs. DOB**: If both present, prefer DOB for accuracy
- **BP units**: Ensure mmHg, not other units (kPa, etc.)
- **Weight units**: Ensure kg, convert from pounds if needed (1 lb = 0.45 kg)
```

### Tool Definition Format (for MCP)

```python
# Example MCP tool definition (for Toolshed-like system)

@mcp_tool(
    name="lookup_lab_range",
    description="Fetch normal reference ranges for a medical test",
    category="medical_reference"
)
def lookup_lab_range(test_name: str, age: int = None, gender: str = None) -> dict:
    """
    Returns normal lab ranges for a test.
    
    Args:
        test_name: Lab test name (e.g., "Fasting Glucose", "HbA1c", "Total Cholesterol")
        age: Age of patient (ranges may vary by age)
        gender: "M" or "F" (ranges may vary by gender)
    
    Returns:
        {
            "test": "Fasting Glucose",
            "normal_range": {
                "low": 70,
                "high": 100,
                "unit": "mg/dL"
            },
            "fasting_required": true,
            "collection_method": "Venipuncture after 8-12 hour fast",
            "source": "American Diabetes Association 2023",
            "note": "Ranges may vary by lab; this is standard"
        }
    """
    # Implementation...
```

---

## Context Flow Through Workflow

### Extraction Node

```
Input: PDF + task description
Context:
  ✓ Rule file (medical_extraction/RULES.md)
  ✓ MCP tools: lookup_lab_range, lookup_condition_criteria
  ✓ System prompt: "Extract medical data with high fidelity"
  ✗ Pricing rules (not needed yet)
  ✗ Compliance rules (not needed yet)
Output: Extracted JSON + confidence scores
```

### Validation Node (Deterministic)

```
Input: Extracted JSON
Context:
  ✓ Pydantic schema (types, constraints)
  ✓ Rule file (consistency rules from medical_extraction/RULES.md)
  ✓ MCP tools: lookup_lab_range (for bounds checking)
  ✗ LLM calls (this is deterministic, not agentic)
Output: Validation report (pass/fail + flags)
```

### Pricing Node (Deterministic)

```
Input: Validated medical data
Context:
  ✓ Rule file (pricing/RULES.md with GLM parameters)
  ✓ MCP tools: lookup_mortality_table, lookup_glm_parameter
  ✓ Actuarial model (coefficients, bounds)
  ✗ LLM calls (pure math, no ML)
Output: Risk score + premium
```

### Review Node (Agentic)

```
Input: Case summary (extracted + priced + routing decision)
Context:
  ✓ Rule file (compliance/RULES.md)
  ✓ MCP tools: lookup_irc_requirement, lookup_precedent_decisions, lookup_audit_trail
  ✓ Full case history (prior decisions)
  ✗ Medical extraction rules (not needed, already done)
Output: Explanation + underwriter recommendations
```

---

## Best Practices

### 1. **Rule Files Stay Current**
- Version rule files alongside code
- Update when medical/regulatory guidelines change
- Include source & date: "WHO 2023 standards as of 2026-04"

### 2. **MCP Tools Have Documentation**
- Each tool has clear schema (inputs, outputs, edge cases)
- Agent can call tool with confidence
- Fallback graceful: tool failure doesn't halt workflow

### 3. **Context Is Cited**
- When agent extracts a value, it should cite the rule or tool
- When pricing uses a coefficient, cite the GLM paper + parameter name
- Auditability requires traceability

### 4. **Test Context Completeness**
- Can agent extract a medical document with only rule file + MCP tools?
- Can agent price a case with only GLM parameters + risk tier rules?
- Missing context = missing capability

### 5. **Scope Rules Aggressively**
- "Never put global rules unless truly global"
- Medical rules → medical_extraction/ directory
- Pricing rules → pricing/ directory
- Compliance rules → compliance/ directory

---

## Questions to Ask

1. **Context completeness**: What would the agent need to know to succeed? (Rule file? MCP tools? Training data?)
2. **Context size**: How many tokens will context consume? Is it within budget?
3. **Context freshness**: How often do rules change? (medical guidelines yearly? IRC regulations as-needed?)
4. **Context location**: Should context live in rule files, MCP tools, or knowledge base?
5. **Context fallback**: If context tool fails, what's the graceful failure? (use default? ask user? escalate?)

---

## References

- [Stripe Minions: One-Shot Agentic Coding](../sources/stripe-minions-agentic-coding.md) — Scoped rules and MCP tool design
- [Agent Orchestration & Frameworks](./agent-orchestration.md) — Tool calling and context management
- [RAG: Retrieval-Augmented Generation](./rag-retrieval-augmented-generation.md) — Knowledge grounding and citation
