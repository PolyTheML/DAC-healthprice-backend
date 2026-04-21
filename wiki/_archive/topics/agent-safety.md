# Agent Safety & Reliability

**Tag**: Safety Layer / Output Validation & Monitoring

---

## Definition

Agent safety ensures that AI systems produce reliable, valid, and trustworthy outputs. In insurance, this means:
- Medical data is never hallucinated
- Risk scores stay within reasonable bounds
- Decisions are explainable and defensible
- Failures are caught before impacting customers

## The Safety Challenge in Insurance

### Why Insurance is High-Stakes

Insurance decisions are **legally binding** and affect people's lives:
- Deny coverage to someone who has a claim → they're unprotected
- Approve someone with hidden risk → insurer losses money
- Hallucinate a lab result → incorrect pricing and legal liability
- Make unexplainable decision → regulators shut you down

**Example of Failure**:
```
Medical PDF says: "Blood Pressure: 140/90"
LLM hallucinates: "Blood Pressure: 340/290" (not physiologically possible)
Risk Score: Inflated by 50x
Premium: $10,000/month instead of $200/month
Customer complaint → Regulatory investigation
```

### Safety Across the Pipeline

```
Input Safety      Processing Safety      Output Safety      Runtime Safety
    ↓                   ↓                       ↓                   ↓
Data Privacy      Agent Monitoring      Output Validation    Observability
Input Injection   Prompt Injection       Hallucination       Decision Audit
PII Exposure      Model Drift            Schema Mismatch     Failure Recovery
```

## Layer 1: Output Validation (Guardrails AI)

**Purpose**: Ensure LLM outputs conform to schema and domain constraints.

**Guardrails Approach**:
1. **Define validators**: Age 18-120, BMI 10-60, SystolicBP 70-200
2. **Wrap LLM calls**: Intercept output before using it
3. **Check constraints**: Does output satisfy schema?
4. **Handle failures**: Reject, re-generate, or flag for review

**Example**:
```
Input: Medical PDF
  ↓
LLM: "Extract BMI"
  ↓
Output Guard:
  - Field present? ✓
  - Type correct (float)? ✓
  - Range valid (10-60)? ✓
  ↓
Pass: Use extracted BMI
Fail: Flag for manual review
```

See [Guardrails AI](../sources/guardrails-ai.md).

## Layer 2: Monitoring & Observability (AgentOps)

**Purpose**: Track every decision so you can prove to regulators how it was made.

**Captures**:
- Which agent nodes executed
- What state was at each step
- How long execution took
- API costs and token usage
- Exceptions and error handling

**For Compliance**:
- "Show me the decision for policy POL-2026-0001"
- AgentOps replays: Extract → Validate → Score → Review → Approve
- Shows exactly what data was used at each step
- Audit trail is immutable

See [AgentOps](../sources/agentops.md).

## Layer 3: Agent Harness (LangGraph + Error Handling)

**Purpose**: Prevent agents from running amok.

**Guardrails**:
- **Timeout**: Agent must complete within 5 minutes
- **Token limits**: API calls capped at $X
- **State validation**: Intermediate results must satisfy checks
- **Fallback paths**: If extraction fails, route to human
- **Pause points**: Inspection gates where human can review before continuing

**Example Harness**:
```
try:
  extract_node.execute()
except ExtractionError:
  flag_for_human_review()
  wait_for_approval()
except TimeoutError:
  escalate_to_underwriter()
  notify_admin()
```

## Layer 4: Prompt Safety

**Risks**:
- Prompt injection: Attacker adds instruction to "ignore validation"
- Model drift: New Claude version behaves differently
- Context leakage: Sensitive info exposed in logs

**Mitigations**:
- Use templated prompts (not user-generated)
- Validate template parameters
- Version your prompts in git
- Regular testing against new models
- Encrypt logs, limit access

## Security Incident Risk

Per [Agentic AI in Financial Services 2026](../sources/agentic-ai-financial-services-2026.md):
- **95% of respondents** experienced at least one AI incident
- **77% resulted in financial losses**
- Expanded attack surface with agents

**Common Incidents**:
- Data exfiltration (agent outputs PII)
- Model poisoning (training data compromised)
- Prompt injection (attacker manipulates agent)
- Denial of Service (API abuse)

**Your Defense**:
- Guardrails prevents hallucinations and invalid outputs
- AgentOps detects anomalies (unusual tokens, costs, latency)
- Monitoring alerts on security events
- Rate limiting on agent API calls
- Regular security audits

## Testing & Validation

**Before Production**:
1. **Unit tests**: Each node works correctly
2. **Integration tests**: Nodes work together
3. **Adversarial tests**: Try to break it
4. **Regression tests**: Old bugs don't resurface
5. **Performance tests**: Latency and cost acceptable

**In Production**:
1. **Canary deployment**: Run on 1% of policies
2. **Monitor metrics**: Is accuracy holding?
3. **Compare to baseline**: Are old underwriting decisions still valid?
4. **Incident response**: Plan for when something breaks

## Regulatory Perspective

Regulators care about:
- **Reliability**: Is the system consistently correct?
- **Explainability**: Can you explain each decision?
- **Auditability**: Can you replay every decision?
- **Recourse**: Can customers appeal?
- **Oversight**: Is a human reviewing decisions?

**Your Safety Stack** addresses all of these:
- Guardrails → Reliability
- Claude + explanations → Explainability
- AgentOps → Auditability
- Human-in-the-loop → Oversight & Recourse

## Failure Modes & Mitigations

| Failure | Symptom | Mitigation |
|---------|---------|-----------|
| Hallucination | Invalid medical value | Guardrails validation |
| Model drift | Accuracy drops | Baseline testing, alerts |
| Prompt injection | Unexpected behavior | Templated prompts, logging |
| Data leakage | PII exposed | Encryption, access control |
| API abuse | Cost spike | Rate limiting, alerts |
| Timeout | Decision delayed | Fallback to human, escalation |

## Relevance to Thesis

Agent safety is the **reliability & trust layer** that:
1. Prevents hallucinations and invalid outputs
2. Provides audit trails for regulatory compliance
3. Catches failures before they impact customers
4. Enables confident scaling from prototypes to production
5. Justifies to Cambodian regulators: "This system is reliable and accountable"

## Implementation Priorities

1. ✅ Understand safety risks in insurance
2. 📌 Implement Guardrails for all LLM outputs
3. 📌 Integrate AgentOps for full observability
4. 📌 Build monitoring dashboards
5. 📌 Create runbooks for common failures
6. 📌 Regular security & compliance audits

## Related Topics

- [Guardrails AI](../sources/guardrails-ai.md)
- [AgentOps](../sources/agentops.md)
- [Agent Orchestration & Frameworks](./agent-orchestration.md)
- [Insurance Compliance & Governance](./compliance-governance.md)
- [Medical Data Validation](./medical-data-validation.md)
