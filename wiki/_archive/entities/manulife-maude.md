# Manulife MAUDE: AI Auto-Decisioning Case Study

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Underwriting Automation Framework](../sources/2026-04-10_underwriting-automation-framework.md)

---

## Overview

**Company**: Manulife Financial  
**Program**: MAUDE (Multi-tier Automated Underwriting Decision Engine)  
**Use Case**: Life insurance instant-issue (personal lines)  
**Result**: **58% automatic approval rate in <2 minutes**

---

## Implementation Details

### Decision Path
- **Standard/Preferred Risk**: Instant approval via automated rules
- **Complex Risk**: Escalated to human underwriter for review
- **Decline Risk**: Auto-declined (uninsurable)

### Timeline
- **Manual review**: 4-8 hours
- **Automated decision**: <2 minutes

### Approval Distribution
```
Instant-issue outcomes:
  58% Auto-Approved (standard/preferred)
  30% Escalated (human review)
  12% Auto-Declined (uninsurable)
```

---

## Key Success Factors

### 1. Decision Rule Clarity
- Clear thresholds for auto-approval (age <65, coverage <$500k, no serious conditions)
- Pre-defined escalation triggers (high coverage, age >65, medical conditions)
- Zero ambiguity in decision tree

### 2. Customer Experience
- Instant approval → immediate online purchase
- Faster than competitors → competitive advantage
- NPS boost: Applicants appreciate speed

### 3. Underwriter Confidence
- AI handles ~60% of volume; underwriter can focus on complex cases
- Clear explainability: Why was this auto-approved/escalated?
- Escalation accuracy: High % of escalated cases eventually approved (underwriters trust the system)

### 4. Regulatory Alignment
- Rules-based approach (no black-box ML) → regulator-friendly
- Every decision is explainable
- Audit trail: Complete record of all decisions

---

## Technology Stack

- **Decision Engine**: Rule-based (if-then-else logic)
- **Backend**: Proprietary Manulife systems
- **Data Source**: Application form + existing policy database + fraud checks
- **Integration**: Seamless with existing underwriting workflows

---

## Business Impact

### Operational Efficiency
- **Faster decisions**: <2 min vs. 4-8 hours
- **Volume handled**: Able to process 50% more applications with same team
- **Cost savings**: Reduced underwriter labor (redirected to complex cases)

### Customer Metrics
- **Approval NPS**: 15+ point boost from fast decisions
- **Online purchase rate**: 45% increase (customers don't have to wait)
- **Policy lapse**: No increase (faster approval → higher satisfaction)

### Risk Metrics
- **Loss ratio**: Consistent with historical data (AI decisions calibrated to past outcomes)
- **Claims accuracy**: Auto-approved cohort has equivalent claims to underwriter-approved cohort

---

## Lessons for DAC Integration

1. **Start with Rules, Not ML**
   - Manulife began with decision trees (simple, auditable)
   - Migrated to ML only after rules became too complex
   - DAC lesson: Build decision rules first (Phase 1); add ML later if needed

2. **Speed = Competitive Advantage**
   - 2 minutes vs. 4-8 hours was the main selling point
   - Applicants will choose insurer with fastest approval
   - DAC lesson: Focus on time-to-decision metric

3. **Escalation SLA Matters**
   - MAUDE's escalation rate (30%) means underwriter can review all escalations same day
   - If escalation rate too high (>50%), humans become bottleneck
   - DAC lesson: Target 75-85% auto-approval rate; keep escalation <25%

4. **Audit Trail is Non-Negotiable**
   - Regulators approved MAUDE because every decision was logged
   - Clear explanation for each decision
   - DAC lesson: Build audit trail from day 1 (Phase 1)

---

## Risks Encountered (and Mitigated)

| Risk | Manulife's Mitigation |
|------|----------------------|
| Auto-decisions reject creditworthy applicants | Manual appeal process; analyst reviews denials; feedback improves rules |
| Rules become outdated | Quarterly review of decision rules; update based on outcomes |
| Applicants frustrated by auto-rejection | Provide appeal mechanism; guaranteed human review within 48 hours |
| Regulatory scrutiny | Transparent rule documentation; IRC pre-clearance |

---

## Related Case Studies

- [Lemonade Claims Automation](./lemonade-claims-automation.md) (claims, not underwriting)
- [AIG Submissions Automation](./aig-submissions-automation.md) (submission analysis)
- [Haven Life Instant Approvals](./haven-life-instant-approvals.md) (instant-issue variant)

---

## Related Topics

- [Instant-Issue Workflow](../topics/underwriting-instant-issue-workflow.md)
- [DAC Integration](../topics/dac-underwriting-integration.md)
- [Implementation Phases](../topics/underwriting-implementation-phases.md)
