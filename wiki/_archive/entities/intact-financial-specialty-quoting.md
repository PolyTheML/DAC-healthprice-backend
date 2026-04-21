# Intact Financial: AI-Driven Specialty Lines Quoting

**Created**: 2026-04-10  
**Last updated**: 2026-04-10  
**Source**: [Underwriting Automation Framework](../sources/2026-04-10_underwriting-automation-framework.md)

---

## Overview

**Company**: Intact Financial Corporation (major Canadian insurer)  
**Program**: AI-powered specialty lines quoting (commercial business)  
**Use Case**: Auto-generate quotes for complex commercial policies  
**Result**: **$150M annual revenue; 20% volume increase with same capacity**

---

## Implementation Details

### Specialty Lines Scope

Intact focuses on complex commercial insurance:
- Business owners (multi-peril coverage)
- Liability (general liability, errors & omissions)
- Property (commercial real estate)

### Quoting Workflow

```
Commercial prospect submits quote request
    ↓
AI system:
  1. Extract: Business info (industry, size, loss history)
  2. Classify: Risk class (small business, startup, established)
  3. Rate: Apply GLM pricing model + rule adjustments
  4. Generate: Quote with coverage + premiums
    ↓
Agent reviews + presents quote to prospect
    ↓
Prospect accepts → Policy issued
```

### Volume Impact
- **Manual quoting**: 1-2 hours per quote (underwriter research + pricing)
- **AI-assisted**: 5-10 minutes per quote (AI generates candidate quote; underwriter reviews)
- **Scaling**: 50K+ quotes annually (vs. impossible with manual)

---

## Technology Stack

- **Document Processing**: Entity extraction (business info from quote request)
- **Risk Classification**: Gradient boosting model (business risk assessment)
- **Pricing**: GLM + rule engine (base premium + adjustments)
- **Quote Generation**: Template-based synthesis (policy coverage + rates)
- **Integration**: CRM + quote system integration

---

## Key Success Factors

### 1. Underwriter Review Loop
- AI generates quote (candidate)
- Underwriter reviews (1-2 min) + may adjust
- Conservative default (AI quotes slightly high; underwriter can lower)
- Builds confidence (underwriter always has final say)

### 2. Industry-Specific Models
- Separate models for different industries (construction, hospitality, tech)
- Each model trained on industry-specific loss history
- Better accuracy than one-size-fits-all model

### 3. Rule Engine Customization
- Business rules layer on top of ML
- Example: "If construction + high-rise + new building, apply +50% premium"
- Flexible adjustment (rules updated quarterly based on loss experience)

### 4. Integration with CRM
- Quote request auto-extracted from CRM
- Generated quote auto-populated back to CRM
- Agent sees quote ready to present (seamless experience)

---

## Business Impact

### Financial Metrics
- **Annual revenue**: $150M (specialty lines)
- **Volume increase**: 20% (same team, more quotes)
- **Revenue per underwriter**: Increased $500K → $750K
- **Profit margin**: Stable (volume increase from efficiency, not cut-rate pricing)

### Operational Metrics
- **Quotes generated daily**: 100+ (vs. 10-20 manual)
- **Quote accuracy**: 92%+ acceptable to prospect (rarely re-quoted)
- **Underwriter satisfaction**: High (less manual work, more relationship building)

---

## Lessons for DAC Integration

1. **Volume Scaling via Automation**
   - Intact grew 20% without hiring (most valuable metric)
   - AI freed underwriters to focus on complex cases + relationships
   - DAC lesson: Goal should be revenue growth, not headcount reduction

2. **Industry-Specific Models**
   - Different industries = different risk profiles
   - One model insufficient; multiple models needed
   - DAC lesson: Health insurance + life insurance likely need separate models (different morbidity patterns)

3. **Conservative Defaults**
   - AI quotes slightly high (underwriter can lower)
   - Avoids losing deals (if AI quoted too low, prospect accepts but profitability suffers)
   - DAC lesson: Build in safety margin (5-10% premium buffer)

4. **Rule + ML Combination**
   - ML for base pricing
   - Rules for policy-specific adjustments
   - Flexible + interpretable (underwriter understands both components)
   - DAC lesson: Hybrid approach (GLM base + rule adjustments) likely best for Cambodia

---

## Risks Encountered

| Risk | Intact's Mitigation |
|------|-------------------|
| AI quotes too low (profit loss) | Conservative defaults; underwriter can raise; rule adjustments |
| Quotes too high (lose business) | Monitor win rate; adjust model if losing too many quotes |
| Model drift (claims experience changes) | Quarterly retraining; loss history analysis |

---

## Related Case Studies

- [Chubb AI Transformation](./chubb-ai-transformation.md) (broader transformation)
- [AIG Submissions Automation](./aig-submissions-automation.md) (submission processing)

---

## Related Topics

- [Risk Classification](../topics/underwriting-risk-classification.md)
- [Tech Stack](../topics/underwriting-tech-stack.md)
- [Implementation Phases](../topics/underwriting-implementation-phases.md)
- [DAC Integration](../topics/dac-underwriting-integration.md)
