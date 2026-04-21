# AutoResearch for Insurance Underwriting

**Created**: 2026-04-10  
**Last Updated**: 2026-04-10  
**Source**: [AutoResearch Tutorial — YouTube](../sources/2026-04-10_autoresearch-tutorial-youtube.md), [DAC Platform Integration](./dac-underwriting-integration.md)

---

## Overview

Insurance underwriting is a high-volume, measurable-outcome domain ideally suited for AutoResearch. Unlike brand design or pricing (subjective), underwriting decisions have clear metrics: **accuracy** (does the AI match historical human decisions?), **fairness** (equal approval/denial rates across demographics?), and **efficiency** (cost per decision). AutoResearch can autonomously improve all three simultaneously.

---

## Why Insurance Underwriting Fits AutoResearch

| Factor | Why It Works |
|--------|-------------|
| **High volume** | 100s-1000s decisions/day = large test set for reliable metrics |
| **Measurable outcomes** | Accuracy (vs. actuals), fairness (disparate impact), cost (tokens/decision) |
| **Fast iteration** | Evaluation runs in seconds; overnight loops = 100+ variants |
| **Regulatory requirement** | Fairness audits mandatory (Cambodia Prakas 093); AutoResearch produces auditable improvement trail |
| **Continuous improvement** | Insurance portfolios shift seasonally; metrics evolve; AutoResearch adapts prompt daily |
| **Clear success metric** | Approval rate accuracy + fairness score = one scalar number per variant |

---

## Three-Layer Setup for Underwriting

### 1. program.md — Underwriting Goals & Constraints

```markdown
# Underwriting Optimization Loop

## Goal
Maximize insurance accuracy and fairness. Balance approval decisions to 
match historical accuracy (~70%) while maintaining demographic parity 
(Disparate Impact Ratio >80%) per Prakas 093.

## Constraints
1. System prompt must include explicit fairness preamble
2. Prompt length: ≤1500 tokens (cost constraint)
3. Cannot mention: age, zip code, birth date (sensitive attributes)
4. Must provide 3+ reasoning steps for every decision
5. Approval/denial decision must be explicit and justified

## Iteration Rules
- Keep variant if: accuracy improves ≥0.5% AND fairness improves ≥1%
- Keep variant if: fairness improves ≥3% even if accuracy unchanged
- Always revert if: disparate impact ratio drops below 75%

## Test Set
- Size: 500 representative applications (random sample from last month)
- Ground truth: Actual historical decisions (verified by compliance team)
- Split: 400 train, 100 holdout validation

## Time Budget per Evaluation
- 2 minutes (must complete full test set in <2 min)
- Cost cap: <$1 per evaluation
```

### 2. train.py — Underwriting System Prompt

This is the file the agent will iterate on. Structure:

```python
UNDERWRITING_PROMPT = """You are an expert insurance underwriter for DAC Life Insurance (Cambodia).

## Fairness Commitment
You evaluate all applicants fairly regardless of:
- Age, gender, birth date
- Residence location
- Socioeconomic indicators
- Family medical history

## Your Task
Given an insurance application, determine approval status and premium class.

## Decision Framework
Step 1: Extract key medical facts from application
Step 2: Assess mortality risk using medical underwriting standards
Step 3: Classify into risk tier (Standard, Preferred, Decline)
Step 4: Justify decision with specific clinical reasoning
Step 5: Check decision for bias (do not vary by demographics)

## Output Format
{
  "decision": "Approve" | "Decline" | "Refer",
  "premium_class": "Standard" | "Preferred" | "Decline",
  "reasoning": "3+ sentences explaining key medical factors",
  "confidence": 0.0-1.0
}

## Examples
[Agent will vary these: medical cases, outcomes, reasoning patterns]

[End of prompt]
"""

# Agent will modify:
# - Phrasing of decision framework
# - Structure (step-by-step vs. holistic)
# - Examples (add/remove/reorder medical cases)
# - Constraints (explicit guardrails against bias)
# - Language (English vs. Khmer vs. technical)
```

### 3. prepare.py — Evaluation Metric (Immutable)

```python
import json
from sklearn.metrics import accuracy_score, confusion_matrix
from collections import defaultdict

def evaluate_underwriting_prompt(prompt_variant):
    """
    Evaluate underwriting prompt on test set.
    Returns single scalar score (0-100).
    """
    
    # Load test set
    test_set = load_test_applications(n=500)  # Last month's decisions
    
    results = []
    for app in test_set:
        # Run variant prompt
        response = call_claude_api(
            system_prompt=prompt_variant,
            user_message=app["text"],
            model="claude-opus-4-6"
        )
        results.append({
            "predicted": parse_decision(response),
            "actual": app["actual_decision"],
            "demographic": app["demographic_group"]  # For fairness calc
        })
    
    # Accuracy: % of decisions matching historical
    accuracy = accuracy_score(
        [r["actual"] for r in results],
        [r["predicted"] for r in results]
    )
    
    # Fairness: Disparate Impact Ratio (group A approval / group B approval)
    approvals_by_group = defaultdict(lambda: {"approved": 0, "total": 0})
    for r in results:
        demo = r["demographic"]
        approvals_by_group[demo]["total"] += 1
        if r["predicted"] == "Approve":
            approvals_by_group[demo]["approved"] += 1
    
    approval_rates = {
        g: v["approved"] / v["total"] 
        for g, v in approvals_by_group.items()
    }
    
    # Disparate Impact Ratio (must be >80% per Prakas 093)
    group_A_rate = approval_rates.get("Group_A", 0.5)
    group_B_rate = approval_rates.get("Group_B", 0.5)
    di_ratio = min(group_A_rate, group_B_rate) / max(group_A_rate, group_B_rate) * 100
    
    # Cost: API cost per decision
    # (Simplified: tokens generated / 500 test decisions)
    cost_score = 100 - (avg_tokens / 10)  # Penalize verbose prompts
    
    # Combined metric (weights per program.md)
    # Accuracy 50%, Fairness 40%, Cost 10%
    score = 0.5 * accuracy + 0.4 * (di_ratio / 100) + 0.1 * (cost_score / 100)
    
    # Safety check: Never compromise safety
    if di_ratio < 75:  # Hard constraint
        return 0  # Fail variant
    
    return score * 100  # Return 0-100 score

def parse_decision(response):
    """Extract decision from Claude response."""
    try:
        return json.loads(response)["decision"]
    except:
        return "Refer"  # Default to conservative

def load_test_applications(n=500):
    """Load labeled test set from compliance database."""
    # Returns list of dicts: {"text": application_text, "actual_decision": ..., "demographic_group": ...}
    pass
```

---

## The Optimization Loop in Practice

### Day 1: Baseline
1. Run current prod prompt on 500-application test set
2. Record: accuracy 68%, fairness (DI ratio) 82%, cost $0.15/decision
3. Score: 0.5×0.68 + 0.4×0.82 + 0.1×0.94 = **0.77** (baseline)

### Day 1-2: Overnight AutoResearch
Agent runs ~100 variants:

| Variant # | Change | Accuracy | Fairness | Cost | Score | Action |
|-----------|--------|----------|----------|------|-------|--------|
| 1 | Reorder examples | 68.5% | 81% | $0.16 | 0.76 | ❌ Revert |
| 2 | Add fairness preamble | 68% | 84% | $0.17 | 0.77 | ✅ Keep |
| 3 | Step-by-step reasoning | 71% | 82% | $0.19 | 0.78 | ✅ Keep |
| 4 | Remove verbose intro | 70% | 83% | $0.14 | 0.79 | ✅ Keep |
| ... | ... | ... | ... | ... | ... | ... |
| 87 | Khmer examples | 72% | 85% | $0.18 | 0.81 | ✅ Keep |
| 100 | Combined best | 73% | 86% | $0.17 | 0.82 | ✅ Final |

### Day 2: Analysis
1. Best variant: 0.82 score (6.5% improvement over baseline)
   - Accuracy: 73% (+5pp)
   - Fairness: 86% DI ratio (+4pp)
   - Cost: $0.17/decision (+13%)
2. Review git log: winners shared two patterns:
   - Explicit Khmer medical terminology
   - Step-by-step reasoning with fairness check
3. Hold out 100 validation apps: test best variant independently
4. A/B test for 1 week: 50% prod, 50% new variant; monitor fairness metrics

### Day 9: Rollout
New prompt deployed to 100% of new applications. Start next optimization loop.

---

## Weekly/Monthly Cadence

- **Daily**: Overnight AutoResearch loop on prompt
- **Weekly**: Manual review of variant winners; fairness audit
- **Monthly**: Lint full knowledge base; check for prompt drift; re-baseline if new data distribution detected
- **Quarterly**: Regulatory review (Prakas 093 compliance); update fairness targets if portfolio composition changes

---

## Use Cases

1. **Daily prompt improvement**: Run overnight, deploy winners with 1-week A/B test
2. **Fairness tuning**: Add constraint to program.md ("Improve fairness by 5% without losing accuracy"), let AutoResearch focus on fairness
3. **New product launch**: Bootstrap underwriting prompt by optimizing on similar product's test set
4. **Regulatory change**: Update program.md constraints (e.g., "Add age-dependent reasoning for new gender-specific mortality tables"), run AutoResearch
5. **Language expansion**: Add Khmer examples; agent learns phrasing that works for local applicants

---

## Risks & Safeguards

| Risk | Safeguard |
|------|-----------|
| **Fairness degradation** | Hard constraint in prepare.py: DI ratio <75% = variant fails immediately |
| **Silent failures** | Every variant tested on full 500-app set; no cherry-picking |
| **Prompt gaming** | prepare.py is immutable; agent cannot rewrite metric |
| **Rollout risk** | 1-week A/B test before full deployment; rollback if metrics degrade |
| **Data drift** | Re-baseline monthly; if test set accuracy drops, pause AutoResearch |
| **Regulatory audit** | Full git history of prompts; log explains rationale for each change |

---

## Implementation Roadmap

**Phase 1** (Week 1): Set up test set, baseline, program.md  
**Phase 2** (Week 2): Deploy AutoResearch loop on staging; monitor for 100 iterations  
**Phase 3** (Week 3): A/B test best variant vs. production for 1 week  
**Phase 4** (Week 4+): Weekly optimization cycles; integrate into prod deployment pipeline  

See: [DAC Implementation Guide](./autoresearch-dac-implementation.md)

---

## Key Takeaway

Insurance underwriting has **everything AutoResearch needs**: high volume, measurable outcomes, regulatory pressure for fairness, and continuous improvement cycles. Rather than manually tuning prompts quarterly, AutoResearch finds improvements automatically every night—both on accuracy and fairness—while maintaining a complete audit trail for compliance.

See also: [Prompt Optimization](./autoresearch-prompt-optimization.md), [Fairness Audit](./underwriting-fairness-audit.md)
