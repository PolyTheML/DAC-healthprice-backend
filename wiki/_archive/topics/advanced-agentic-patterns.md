# Advanced Agentic Patterns

**Last Updated**: 2026-04-09

## Overview

Cutting-edge techniques for building reliable, reasoning-rich agents. Includes ReAct (Reasoning + Acting), Tool-former (learning to use tools), and agent evaluation frameworks.

---

## ReAct: Reasoning + Acting

**Source**: [ReAct Paper - arxiv.org/abs/2210.03629](https://arxiv.org/abs/2210.03629)

### Core Idea

Agents should **think before acting**. Alternate between:
1. **Thought** — Explicit reasoning about what to do
2. **Action** — Call a tool or make a decision
3. **Observation** — Process the result
4. **Reflect** — Update understanding

### Example: Medical Document Review

```
Thought: The applicant has high blood pressure. I should check 
         what the medical guidelines say about hypertension risk.

Action: retriever.search("hypertension risk management")

Observation: [WHO guidelines, CAS mortality tables, company policy]
             Stage 1 hypertension (SBP 140-159) carries 1.2-1.5x risk.

Thought: The applicant has Stage 1. Based on guidelines, I should 
         also check their age and other risk factors.

Action: extract_age_from_application()

Observation: Age 45, no prior cardiac events.

Thought: Age 45 + Stage 1 hypertension = 1.3x baseline risk.
         This is routine—no complex factors. 

Action: score_with_glm(age=45, sbp=145)

Observation: Risk score = 8%, Premium = $800/year

Final Answer: APPROVE, $800/year
```

### Benefits for Insurance

- ✅ Transparent reasoning (auditable)
- ✅ Agents can explain their thinking
- ✅ Fewer hallucinations (explicit constraints)
- ✅ Better performance on complex cases

---

## Toolformer: Learning When to Use Tools

**Source**: [Toolformer Paper - arxiv.org/abs/2303.18223](https://arxiv.org/abs/2303.18223)

### Core Idea

Instead of hardcoding which tools an agent uses, **the LLM learns when to call tools** during training.

### Pattern

```
Input: "What's the 2026 mortality rate for age 45?"

LLM learns:
  "The mortality rate for age 45 in 2026 is [Retriever(mortality_tables_2026_age45)]"

System executes retriever, gets 0.3%, fills in the blank:
  "The mortality rate for age 45 in 2026 is 0.3%"
```

### For Underwriting

LLM could learn to automatically call:
- `[MedicalRecord(applicant_id)]` for medical history
- `[ActuarialTable(age, gender, condition)]` for baseline risk
- `[CompanyPolicy(condition)]` for approval rules

No need to hardcode the workflow—LLM discovers it.

---

## Agent Evaluation Challenges

**Source**: [Agent Evaluation Challenges - arxiv.org/abs/2401.04088](https://arxiv.org/abs/2401.04088)

### Key Problems

1. **Defining Success**
   - Is it accuracy? Speed? Interpretability? Cost?
   - Insurance prioritizes: Accuracy > Explainability > Speed

2. **Reproducibility**
   - Agent uses randomness (temperature sampling)
   - Same input may produce different outputs
   - Need statistical significance testing

3. **Benchmarking**
   - Most public benchmarks are not insurance-specific
   - Need domain-specific test sets

### Evaluation Framework for Underwriting

```
Metric: Decision Accuracy (approval rate matches human)
  - Sample 100 applicants, get human decisions
  - Run agent decisions
  - Compute agreement rate (target: >95%)

Metric: Explainability Quality
  - Auditors review 20 decisions
  - Grade explanations (clear, sufficient, grounded)

Metric: Consistency
  - Run same applicant 5x (different prompts/models)
  - Measure variance in decisions
  - Target: 100% consistency for routine cases

Metric: Speed
  - Document processing + scoring + explanation < 30s
```

---

## Robust Agent Design

### Safety Principles

1. **Fail to manual review**
   - If agent is uncertain, escalate to human
   - Better to skip automation than make wrong decision

2. **Explicit constraints**
   - Age > 100? Reject automatically (medical implausibility)
   - Premium > $10k/year? Flag for compliance review
   - Missing critical data? Refer to human

3. **Audit everything**
   - Log every action, decision, tool call
   - Timestamp and user context
   - Replayability for compliance

---

## Related Topics

- [Agent Orchestration](./agent-orchestration.md) — LangGraph state machines
- [Agent Safety & Reliability](./agent-safety.md) — Monitoring and guardrails
- [XAI & Explainability](./xai-explainability-auditability.md) — Making decisions transparent
