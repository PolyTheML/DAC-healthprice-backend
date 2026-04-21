# Haven Life: Instant Life Insurance Approvals

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Underwriting Automation Framework](../sources/2026-04-10_underwriting-automation-framework.md)

---

## Overview

**Company**: Haven Life (Massachusetts Financial Services subsidiary)  
**Program**: Instant life insurance approvals (no medical exam, no underwriting delay)  
**Use Case**: Term life insurance instant-issue  
**Result**: **Minutes instead of days/weeks for approval**

---

## Implementation Details

### Decision Rules

Haven Life uses **simplified underwriting** + **risk-based pricing**:

```
Applicant fills online form (2 min)
    ↓
AI decision engine:
  • Age: Auto-approval up to 60; escalate 61-75; decline >75
  • Coverage: Auto-approve up to $500k; escalate >$500k
  • Health: Simple health questions (no medical exam)
  • Smoking: Include in rating (rate accordingly)
    ↓
Decision: Instant approval (99%+ of cases)
    ↓
Policy issued immediately (online purchase)
```

### Approval Distribution
- **Instant approval**: 99% of applicants
- **Escalation**: <1% (high coverage or unusual circumstances)

### Timeline
- **Traditional**: 2-4 weeks (underwriting + medical exam)
- **Haven Life**: Minutes (online decision + instant policy)

---

## Technology Stack

- **Online Form**: Custom-built (collects only essential health questions)
- **Decision Engine**: Simple decision tree (no complex ML)
- **Pricing**: GLM-based rating (age + smoking + health bucket)
- **Backend**: Proprietary Haven Life system

---

## Key Success Factors

### 1. Extreme Simplicity
- Decision rules are simple (if age >60, escalate; else approve)
- No complex ML models (regulators understand easily)
- No medical exam (reduces friction for applicants)

### 2. Online Experience
- Entire process online (no phone calls, no paperwork)
- Applicant sees approved quote immediately
- Can purchase policy same day

### 3. Risk-Adjusted Pricing
- Simple rating: Age bucket + smoking status
- Smoker pays 2-3× more than non-smoker
- Balances accessibility (instant approval) with risk management

### 4. Customer Delight
- "Approved in minutes" is primary value proposition
- NPS boost: Applicants love speed
- Market differentiation: Competitors require medical exam

---

## Business Impact

### Operational Metrics
- **Approval time**: 2 weeks → 2 minutes (700× faster)
- **Policy lapse**: No increase (faster approval → higher satisfaction)
- **Volume**: Can handle unlimited applications (no underwriter bottleneck)

### Financial Metrics
- **Reduced underwriting cost**: Minimal (mostly automated)
- **Reduced medical exam cost**: $300-500 per policy saved
- **Revenue**: Higher premium due to "instant approval" brand premium

---

## Lessons for DAC Integration

1. **Simplicity Beats Sophistication**
   - Haven Life uses simple rules, not ML
   - Easier to explain + audit + regulate
   - DAC lesson: Start with simple decision rules (Phase 1); add ML only if needed

2. **Online Experience Drives Growth**
   - Instant approval online > waiting for underwriter approval
   - Creates viral growth (friends recommend)
   - DAC lesson: Build digital-first platform (React frontend, FastAPI backend)

3. **Medical Exam is Friction**
   - Haven Life skips medical exam (reduces conversion friction)
   - Prices higher to account for missing medical data
   - DAC lesson: Consider lightweight underwriting (health questions) vs. requiring medical exam

4. **Risk Adjustment via Pricing**
   - Don't decline risks; price them appropriately
   - Smoker pays 2-3× → breaks even on higher mortality risk
   - DAC lesson: Focus on pricing adjustment, not approval/decline binary

---

## Risks Encountered

| Risk | Haven Life's Mitigation |
|------|-------------------------|
| Adverse selection (unhealthy people apply more) | Pricing adjustment (higher premiums offset risk) |
| Claims experience worse than traditional | Monitor claims; adjust pricing annually |
| Medical exam requirements by regulators | Emphasize "non-medical" as feature; offer optional exam for higher coverage |

---

## Related Case Studies

- [Manulife MAUDE](./manulife-maude.md) (instant-issue with exams)
- [Lemonade Claims Automation](./lemonade-claims-automation.md) (instant settlement model)

---

## Related Topics

- [Instant-Issue Workflow](../topics/underwriting-instant-issue-workflow.md)
- [Risk Classification](../topics/underwriting-risk-classification.md)
- [DAC Integration](../topics/dac-underwriting-integration.md)
