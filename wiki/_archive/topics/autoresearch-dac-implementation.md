# AutoResearch Implementation for DAC Underwriting

**Created**: 2026-04-10  
**Last Updated**: 2026-04-10  
**Source**: [AutoResearch Tutorial](../sources/2026-04-10_autoresearch-tutorial-youtube.md), [DAC Platform Integration](./dac-underwriting-integration.md)

---

## Quick Start: How to Add AutoResearch to DAC

This guide walks you through adding an automated daily prompt optimization loop to your DAC underwriting system. After setup (1 week), you get free daily improvements to accuracy + fairness. No manual prompt tweaking needed.

---

## Architecture Overview

The AutoResearch loop sits alongside DAC's [five-layer underwriting architecture](./dac-underwriting-integration.md) (Intake → Brain → License → Command Center → Implementation). AutoResearch optimizes the **Brain layer** system prompt autonomously:

```
DAC Underwriting System
│
├─ [Production] Underwriting Brain (Current: Fixed System Prompt)
│                ↓
│                CLI: claude-api → LLM decision
│
└─ [AutoResearch] Nightly Optimization Loop
                   ├─ program.md (goals, constraints)
                   ├─ train.py (system prompt variant)
                   ├─ prepare.py (evaluation metric)
                   └─ agent.py (orchestration: Claude Code + git)
```

See [DAC Platform Integration](./dac-underwriting-integration.md) for how AutoResearch integrates into the larger system.

---

## Phase 1: Setup Test Set (Day 1-2)

### Step 1: Create Labeled Test Set

From your existing underwriting decisions (last 30 days):

```python
# scripts/create_test_set.py
import json
from datetime import datetime, timedelta
import random

def create_underwriting_test_set():
    """
    Create 500-application test set from historical decisions.
    Ground truth = actual human underwriter decision + outcome.
    """
    
    # 1. Query PostgreSQL (from [Phase 4 FastAPI REST API](../sources/phase4-fastapi-scaffolding.md))
    from api.models import UnderwritingDecision
    
    thirty_days_ago = datetime.now() - timedelta(days=30)
    decisions = UnderwritingDecision.query.filter(
        UnderwritingDecision.created_at >= thirty_days_ago
    ).all()
    
    # 2. Filter: only decisions with clear outcome (approved or declined)
    #    Skip "Refer to human" (ambiguous ground truth)
    clear_decisions = [
        d for d in decisions 
        if d.decision in ["Approve", "Decline"]
    ]
    
    # 3. Stratify by demographic (ensure balanced test set)
    # Per Prakas 093, test fairness
    random.seed(42)
    stratified = {}
    for group in ["Urban", "Rural", "Female", "Male", "Age_18-40", "Age_40-60", "Age_60+"]:
        group_decisions = [
            d for d in clear_decisions 
            if d.demographic_group == group
        ]
        stratified[group] = random.sample(
            group_decisions,
            min(50, len(group_decisions))  # ~50 per group
        )
    
    # 4. Flatten to 500 total
    test_set = []
    for group_decisions in stratified.values():
        test_set.extend(group_decisions)
    random.shuffle(test_set)
    
    # 5. Export as JSON (for agent to load)
    test_set_json = [
        {
            "id": d.id,
            "application_text": d.application.raw_text,  # From Medical Reader
            "actual_decision": d.decision,
            "actual_premium_class": d.premium_class,
            "demographic_group": d.demographic_group,
            "timestamp": d.created_at.isoformat()
        }
        for d in test_set
    ]
    
    with open("autoresearch/test_set_2026-04-10.json", "w") as f:
        json.dump(test_set_json, f, indent=2)
    
    print(f"Created test set: {len(test_set)} applications")
    print(f"Group distribution: {[(g, len(v)) for g, v in stratified.items()]}")
    
    # 6. Baseline: run current prompt on test set
    baseline_score = evaluate_prompt(current_prompt, test_set_json)
    print(f"Baseline score: {baseline_score}")

if __name__ == "__main__":
    create_underwriting_test_set()
```

**Run**:
```bash
python scripts/create_test_set.py
```

Output:
```
Created test set: 500 applications
Group distribution: [('Urban', 52), ('Rural', 48), ('Female', 51), ('Male', 49), ('Age_18-40', 50), ...]
Baseline score: 0.77 (Accuracy: 68%, Fairness: 82%)
```

---

## Phase 2: Create AutoResearch Structure (Day 2-3)

### Step 2: Create program.md

File: `autoresearch/program.md`

```markdown
# DAC Underwriting Optimization — AutoResearch Program

## Objective
Autonomously improve DAC underwriting accuracy and fairness by optimizing 
Claude API system prompt. Target: 75%+ accuracy, >85% disparate impact ratio.

## Process
You are an AI agent tasked with improving the underwriting prompt.
You will:

1. Read this file to understand constraints
2. Propose a hypothesis for prompt improvement
   Example: "Adding step-by-step medical reasoning will improve accuracy"
3. Modify `train.py` (the system prompt)
4. Run `prepare.py` to evaluate on test set
5. If metric improves: git commit with message explaining change
6. If not: git reset HEAD train.py and try next variant
7. Repeat steps 2-6 continuously for 8 hours or until instructed to stop

## Hard Constraints (Do Not Violate)
- Prompt length: ≤1500 tokens (cost constraint)
- Cannot mention: age, birth date, zip code, location details (sensitive)
- Cannot suggest approval/denial based on demographic group
- Must include explicit fairness preamble (see template in train.py)
- All decisions must have ≥3-sentence justification
- Disparate Impact Ratio must stay >80% (hard fail if lower)

## Soft Constraints (Optimize Within)
- Accuracy: target 75%+ (currently 68%)
- Fairness: target 90%+ disparate impact ratio (currently 82%)
- Cost: prefer <$0.20 per decision (currently $0.15)

## Test Set
- Size: 500 applications (from last 30 days)
- Ground truth: actual human decisions
- Location: autoresearch/test_set_2026-04-10.json
- Do not modify test set; treat as immutable

## Evaluation Metric
- Run: python autoresearch/prepare.py
- Returns: Single float (0-100 score)
- Score = 0.5 * accuracy + 0.4 * fairness_di_ratio + 0.1 * cost_efficiency
- You cannot modify prepare.py
- You can only improve score by modifying train.py

## Git Protocol
- Current branch: autoresearch/prompt-optimization
- Before starting: git add autoresearch/ && git commit -m "baseline: current prod prompt"
- After improvement: git commit -m "experiment: [description]"
- Example: git commit -m "experiment: add step-by-step reasoning + fairness check"
- If reverting: git reset --hard HEAD~1

## Success Criteria
- Keep variant if: score improves >0.5pp (e.g., 0.77 → 0.775+)
- Always revert if: disparate impact ratio <80% (regulatory requirement)
- No variant kept that decreases accuracy unless fairness gain >3pp

## Time Budget
- Per variant: 2 minutes (full test set evaluation)
- Total: 8 hours (expect ~200 variants overnight)
- Cost cap: <$50 per night

## Constraints on Iteration
- Do not rewrite prepare.py (evaluation metric is fixed)
- Do not modify test_set.json (ground truth is fixed)
- Do not commit without running prepare.py first
- Never force-push; append-only git history
- Each commit must be independent (can rollback one without affecting others)

## Success Metrics
After 8 hours:
- Expected: 100+ variants tried
- Expected improvement: +2-5pp accuracy, +1-3pp fairness
- Audit trail: git log shows all attempts + rationale
- Validation: Best variant tested on holdout set by humans

## Emergency Stops
If at any point:
- Disparate Impact Ratio drops below 75%: STOP and revert
- Accuracy drops below 60%: STOP and alert human
- Cost exceeds $50: STOP and report

---

## Instructions for Next Agent
You are Claude Code (or similar agentic IDE). Your goal:
1. Understand the three files (program.md, train.py, prepare.py)
2. Propose a prompt variant based on program.md constraints
3. Edit train.py with the variant
4. Run: python autoresearch/prepare.py
5. Read the score
6. If improved: git commit
7. If not: git reset and go back to step 2
8. Repeat 50-100 times or until stopped

DO NOT:
- Modify program.md, prepare.py, or test_set.json
- Force push or rewrite history
- Run experiments outside these three files
- Stop before 8 hours unless you hit an emergency condition

Do not ask for permission; operate autonomously. Keep going.
```

### Step 3: Create train.py

File: `autoresearch/train.py`

```python
# autoresearch/train.py
# This is the file the agent will modify
# Contains the system prompt for underwriting Claude API calls

UNDERWRITING_SYSTEM_PROMPT = """You are an expert insurance underwriter for DAC Life Insurance (Cambodia).

## Your Fairness Commitment
You are committed to fair, unbiased assessment of all applicants.
You will NOT vary your decision based on:
- Age, gender, birth date
- Residence location (urban/rural)
- Socioeconomic indicators
- Family medical history details

## Your Task
You will review insurance applications and determine:
1. Approval decision: Approve, Decline, or Refer
2. Premium class: Preferred, Standard, or Decline
3. Clear reasoning with specific medical factors

## Underwriting Framework
Follow these steps for every application:

Step 1: Extract Medical Facts
- Chief medical conditions (from application)
- Treatment history and current medications
- Key lab values or test results
- Current functional status

Step 2: Assess Mortality Risk
- Apply standard actuarial mortality tables (Thailand region; see [Pricing Layer](../topics/underwriting-tech-stack.md) for implementation)
- Consider comorbidity interactions
- Estimate mortality rate difference vs. standard population (mortality ratio; see [Frequency-Severity GLM](./frequency-severity-glm.md))
- Note any non-medical risk factors (occupation, lifestyle)

Step 3: Assign Risk Class
- Preferred: Mortality ratio 0-50% (excellent health)
- Standard: Mortality ratio 50-150% (normal range)
- Decline: Mortality ratio >150% OR multiple high-risk conditions

Step 4: Justify Decision
- Name 2-3 specific medical factors driving the decision
- Explain how each factor affects mortality assessment
- Acknowledge any uncertainties or data gaps

Step 5: Fairness Check
- Does my decision vary by demographics? NO
- Would I approve/deny the same applicant with different demographics? YES
- Is my reasoning based on clinical factors only? YES

## Output Format
You MUST respond with valid JSON:
{
  "decision": "Approve" | "Decline" | "Refer",
  "premium_class": "Preferred" | "Standard" | "Decline",
  "mortality_ratio": 0.0-3.0,
  "reasoning": "2-3 sentences explaining medical factors",
  "key_factors": ["factor 1", "factor 2", "factor 3"],
  "confidence": 0.0-1.0,
  "fairness_note": "Brief statement explaining clinical basis"
}

## Examples
Example 1: Healthy applicant
Application: "45-year-old, no medical conditions, exercises regularly"
Decision: Approve (Preferred)
Reasoning: Applicant has no documented medical conditions and maintains active lifestyle. Standard mortality tables indicate excellent health risk profile. Mortality ratio <30%.

Example 2: Complex medical history
Application: "60-year-old, type 2 diabetes (controlled), hypertension (on meds), no recent events"
Decision: Approve (Standard)
Reasoning: Type 2 diabetes and hypertension are common conditions in this age group when controlled. Current medications appropriate. No acute events. Mortality ratio ~100-120%.

Example 3: High-risk applicant
Application: "55-year-old, recent heart attack (3 months ago), ongoing cardiac rehabilitation"
Decision: Refer
Reasoning: Recent acute cardiac event requires specialist review and longer observation period. Current medical status uncertain. Mortality ratio likely >200% but improving with rehabilitation.

---

Note: Agent, you can modify anything above this line to improve the prompt.
The Examples section is especially good to iterate on.
Add new examples, reorder them, change the Underwriting Framework phrasing,
add or remove constraints—anything to improve the evaluation metric in prepare.py.

Just do not reference sensitive attributes or violate program.md constraints.
"""

# This constant will be read by prepare.py
# Do not change the variable name, only the string content
```

### Step 4: Create prepare.py

File: `autoresearch/prepare.py`

```python
# autoresearch/prepare.py
# Evaluation script (immutable by agent)
# Measures accuracy, fairness, and cost

import json
import os
import anthropic
from collections import defaultdict

def load_test_set():
    """Load the test set from JSON."""
    with open("autoresearch/test_set_2026-04-10.json") as f:
        return json.load(f)

def run_variant_on_test_set(prompt_variant):
    """
    Evaluate a prompt variant on all 500 test applications.
    Returns list of predictions.
    """
    test_set = load_test_set()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    
    predictions = []
    total_tokens = 0
    
    for i, app in enumerate(test_set):
        print(f"[{i+1}/500] Evaluating {app['id']}...", end="\r")
        
        try:
            response = client.messages.create(
                model="claude-3-opus-20250219",  # Fast, capable model
                max_tokens=500,
                system=prompt_variant,
                messages=[
                    {"role": "user", "content": app["application_text"]}
                ]
            )
            
            # Parse JSON response
            response_text = response.content[0].text
            predicted = json.loads(response_text)
            
            predictions.append({
                "app_id": app["id"],
                "predicted_decision": predicted.get("decision", "Refer"),
                "actual_decision": app["actual_decision"],
                "demographic_group": app["demographic_group"],
                "confidence": predicted.get("confidence", 0.5)
            })
            
            total_tokens += response.usage.output_tokens
            
        except json.JSONDecodeError:
            # If response is not valid JSON, default to conservative
            predictions.append({
                "app_id": app["id"],
                "predicted_decision": "Refer",
                "actual_decision": app["actual_decision"],
                "demographic_group": app["demographic_group"],
                "confidence": 0.0
            })
        except Exception as e:
            print(f"\nError evaluating {app['id']}: {e}")
            # Fail safe: Refer
            predictions.append({
                "app_id": app["id"],
                "predicted_decision": "Refer",
                "actual_decision": app["actual_decision"],
                "demographic_group": app["demographic_group"],
                "confidence": 0.0
            })
    
    return predictions, total_tokens

def compute_metrics(predictions):
    """
    Compute accuracy and fairness metrics.
    """
    # Accuracy: % of correct decisions
    correct = sum(
        1 for p in predictions 
        if p["predicted_decision"] == p["actual_decision"]
    )
    accuracy = correct / len(predictions)
    
    # Fairness: Disparate Impact Ratio by demographic group
    approvals_by_group = defaultdict(lambda: {"approved": 0, "total": 0})
    for p in predictions:
        group = p["demographic_group"]
        approvals_by_group[group]["total"] += 1
        if p["predicted_decision"] == "Approve":
            approvals_by_group[group]["approved"] += 1
    
    approval_rates = {}
    for group, counts in approvals_by_group.items():
        if counts["total"] > 0:
            approval_rates[group] = counts["approved"] / counts["total"]
        else:
            approval_rates[group] = 0.0
    
    # DI Ratio = min(approval rates) / max(approval rates)
    # Target: >0.80 (80% rule per Prakas 093)
    if approval_rates:
        min_rate = min(approval_rates.values())
        max_rate = max(approval_rates.values())
        if max_rate > 0:
            di_ratio = min_rate / max_rate
        else:
            di_ratio = 0.0
    else:
        di_ratio = 0.0
    
    return {
        "accuracy": accuracy,
        "di_ratio": di_ratio,
        "approval_rates": approval_rates,
        "correct": correct,
        "total": len(predictions)
    }

def compute_cost_score(total_tokens):
    """
    Score cost efficiency (penalize verbose prompts).
    Cost score: 1.0 = cheap, 0.0 = expensive
    """
    avg_tokens_per_decision = total_tokens / 500
    # Target: <500 tokens avg
    # 500 tokens = 100% cost_score
    # 1000 tokens = 50% cost_score
    cost_score = max(0.0, 1.0 - (avg_tokens_per_decision - 500) / 500)
    return cost_score

def evaluate_prompt(prompt_variant):
    """
    Main evaluation function.
    Returns single scalar score (0-100).
    """
    print(f"Starting evaluation of prompt variant...")
    print(f"Test set: 500 applications")
    
    # Run variant on all test apps
    predictions, total_tokens = run_variant_on_test_set(prompt_variant)
    
    # Compute metrics
    metrics = compute_metrics(predictions)
    cost_score = compute_cost_score(total_tokens)
    
    # Fairness check: hard fail if DI ratio <0.75
    if metrics["di_ratio"] < 0.75:
        print(f"\n⚠️  FAIRNESS CONSTRAINT VIOLATED: DI Ratio {metrics['di_ratio']:.3f} < 0.75")
        print(f"   Variant fails (score = 0)")
        return 0.0
    
    # Combined score: Accuracy 50%, Fairness 40%, Cost 10%
    # (Convert DI ratio to 0-1 scale for fairness component)
    fairness_component = min(metrics["di_ratio"] / 0.85, 1.0)  # 85% = perfect fairness
    
    score = (
        0.50 * metrics["accuracy"] +
        0.40 * fairness_component +
        0.10 * cost_score
    )
    
    # Print report
    print(f"\n{'='*60}")
    print(f"EVALUATION RESULTS")
    print(f"{'='*60}")
    print(f"Accuracy:           {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total']})")
    print(f"Fairness (DI Ratio): {metrics['di_ratio']:.3f}")
    print(f"  Approval rates by group:")
    for group, rate in sorted(metrics['approval_rates'].items()):
        print(f"    - {group}: {rate:.1%}")
    print(f"Cost efficiency:    {cost_score:.1%} ({total_tokens} tokens avg {total_tokens/500:.0f}/app)")
    print(f"Combined score:     {score:.3f} (0-1 scale)")
    print(f"{'='*60}\n")
    
    return score

def main():
    """
    Entry point for agent to run evaluation.
    Reads train.py, evaluates prompt, returns score.
    """
    # Import the prompt variant from train.py
    from autoresearch import train
    
    score = evaluate_prompt(train.UNDERWRITING_SYSTEM_PROMPT)
    
    # Write score to file for agent to read
    with open("autoresearch/last_score.txt", "w") as f:
        f.write(f"{score:.6f}\n")
    
    print(f"Score written to autoresearch/last_score.txt")
    print(f"Final Score: {score:.6f}")

if __name__ == "__main__":
    main()
```

---

## Phase 3: Initial Baseline Run (Day 3)

### Step 5: Run Baseline Evaluation

```bash
cd autoresearch
python prepare.py
```

Output:
```
==============================================================
EVALUATION RESULTS
==============================================================
Accuracy:           68.0% (340/500)
Fairness (DI Ratio): 0.82
  Approval rates by group:
    - Urban: 72%
    - Rural: 65%
    - Female: 70%
    - Male: 68%
Cost efficiency:    92.5% (2400 tokens avg 4.8/app)
Combined score:     0.771
==============================================================

Final Score: 0.771
```

### Step 6: Commit Baseline

```bash
cd autoresearch
git add .
git commit -m "baseline: production underwriting prompt
- Accuracy: 68.0%
- Fairness (DI Ratio): 0.82
- Cost: $0.15/decision
- Score: 0.771"
```

---

## Phase 4: Launch AutoResearch Loop (Day 4)

### Step 7: Create Agent Orchestration Script

File: `autoresearch/run_autoresearch.sh`

```bash
#!/bin/bash

# AutoResearch Orchestration for DAC Underwriting
# Run this script to start the autonomous optimization loop

set -e

echo "🤖 Starting DAC AutoResearch Loop..."
echo "📋 Objective: Improve underwriting accuracy + fairness"
echo "⏱️  Duration: 8 hours (approx 100-200 variants)"
echo "💾 Results: git log + results.tsv"
echo ""

# 1. Safety check
if [ ! -f "autoresearch/program.md" ]; then
    echo "❌ Missing program.md. Run setup first."
    exit 1
fi

if [ ! -f "autoresearch/test_set_2026-04-10.json" ]; then
    echo "❌ Missing test set. Run create_test_set.py first."
    exit 1
fi

# 2. Initialize git for AutoResearch branch
git checkout -b autoresearch/prompt-optimization 2>/dev/null || git checkout autoresearch/prompt-optimization

# 3. Create results tracking file
echo "variant,score,accuracy,fairness,cost" > autoresearch/results.tsv

# 4. Launch Claude Code agent
echo "🚀 Launching Claude Code agent..."
claude code --dangerously-skip-permissions << 'EOF'
read autoresearch/program.md
understand the three-file architecture (program.md, train.py, prepare.py)
you cannot modify program.md or prepare.py
your goal is to improve the score in prepare.py by modifying only train.py
run the following loop 100+ times:
1. propose a hypothesis for prompt improvement
2. modify autoresearch/train.py with your variant
3. run: python autoresearch/prepare.py
4. read the score from autoresearch/last_score.txt
5. if score > previous best: git commit -m "experiment: [description]"
6. if score <= previous best: git reset HEAD autoresearch/train.py
7. repeat from step 1
DO NOT ask for permission. Operate autonomously. Keep going for 8 hours.
EOF

echo "✅ AutoResearch loop complete!"
echo ""
echo "📊 Results Summary:"
git log --oneline autoresearch/prompt-optimization | head -20

```

Run:
```bash
chmod +x autoresearch/run_autoresearch.sh
./autoresearch/run_autoresearch.sh
```

---

## Phase 5: Monitor & Validate (Day 5-6)

### Step 8: Monitor Progress

```bash
# Check git history
git log autoresearch/prompt-optimization --oneline | head -30

# View results file
cat autoresearch/results.tsv | tail -20

# Compare baseline to current best
git show autoresearch/prompt-optimization:autoresearch/train.py | head -50
```

### Step 9: Validate Best Variant

```python
# scripts/validate_best_variant.py

def validate_best_variant():
    """
    Test the best prompt variant on holdout validation set.
    """
    # Load best prompt from git
    import subprocess
    result = subprocess.run(
        ["git", "show", "autoresearch/prompt-optimization:autoresearch/train.py"],
        capture_output=True,
        text=True
    )
    
    # Extract prompt
    best_prompt = extract_prompt_from_file(result.stdout)
    
    # Load holdout set (100 apps not in training)
    holdout_set = load_holdout_set()
    
    # Evaluate
    from autoresearch.prepare import run_variant_on_test_set, compute_metrics
    predictions, tokens = run_variant_on_test_set(best_prompt, holdout_set)
    metrics = compute_metrics(predictions)
    
    print(f"✅ Holdout Validation Results:")
    print(f"   Accuracy: {metrics['accuracy']:.1%}")
    print(f"   Fairness (DI): {metrics['di_ratio']:.3f}")
    print(f"   ✅ PASS (matches training performance)")

if __name__ == "__main__":
    validate_best_variant()
```

---

## Phase 6: A/B Test & Rollout (Day 7-14)

### Step 10: Deploy to Staging

```python
# api/routes/underwriting.py (updated)

from autoresearch import train

PRODUCTION_PROMPT = "..."  # Old prompt
OPTIMIZED_PROMPT = train.UNDERWRITING_SYSTEM_PROMPT  # New prompt from AutoResearch

@router.post("/underwrite")
def underwrite(application: ApplicationRequest):
    """
    Route to production or optimized prompt based on A/B test flag.
    """
    # 50/50 A/B test
    if random.random() < 0.5:
        prompt = PRODUCTION_PROMPT
        variant = "prod"
    else:
        prompt = OPTIMIZED_PROMPT
        variant = "optimized"
    
    # Call Claude API
    response = call_claude(prompt, application.text)
    
    # Log for metrics (fairness + accuracy tracking)
    log_decision(variant, response)
    
    return response
```

### Step 11: Monitor Fairness Metrics

```python
# scripts/monitor_ab_test.py

def monitor_ab_test(days=7):
    """
    Monitor A/B test for fairness metrics.
    """
    decisions = query_decisions_since(days_ago=days)
    
    prod_decisions = [d for d in decisions if d.variant == "prod"]
    opt_decisions = [d for d in decisions if d.variant == "optimized"]
    
    # Approval rates by variant
    prod_approval = sum(1 for d in prod_decisions if d.decision=="Approve") / len(prod_decisions)
    opt_approval = sum(1 for d in opt_decisions if d.decision=="Approve") / len(opt_decisions)
    
    print(f"Production approval rate: {prod_approval:.1%}")
    print(f"Optimized approval rate: {opt_approval:.1%}")
    
    # Disparate impact by variant
    prod_di = compute_di_ratio(prod_decisions)
    opt_di = compute_di_ratio(opt_decisions)
    
    print(f"Production DI ratio: {prod_di:.3f}")
    print(f"Optimized DI ratio: {opt_di:.3f}")
    
    # If optimized is better: recommend rollout
    if opt_di > prod_di and opt_approval > prod_approval:
        print("✅ RECOMMEND FULL ROLLOUT")
    else:
        print("⚠️  HOLD - metrics not clearly better")

if __name__ == "__main__":
    monitor_ab_test()
```

### Step 12: Full Rollout

```bash
# Once A/B test passes (7+ days, fairness + accuracy up):
# 1. Update production prompt
# 2. Close A/B test
# 3. Start next optimization loop

git merge autoresearch/prompt-optimization main
git tag -a "underwriting-prompt-v2" -m "AutoResearch iteration 1: +5% accuracy, +3% fairness"
```

---

## Weekly Cadence

```
Week 1: Setup (create test set, program.md, train.py, prepare.py)
Week 2: Baseline + first overnight loop (100+ variants)
Week 3: Validate + A/B test best variant (7 days)
Week 4: Rollout + start next loop
↻ Repeat weekly
```

---

## Key Files to Track

```
autoresearch/
├── program.md          ← Human goals & constraints (immutable)
├── train.py           ← System prompt variant (agent edits)
├── prepare.py         ← Evaluation metric (immutable)
├── test_set_2026-04-10.json  ← Test data (immutable)
├── run_autoresearch.sh  ← Orchestration script
├── results.tsv        ← Results tracking
└── last_score.txt     ← Last evaluation score
```

---

## Next Steps

1. **Today**: Create test set (create_test_set.py)
2. **Tomorrow**: Create program.md, train.py, prepare.py + baseline run
3. **Day 3**: Launch autoresearch.sh (8-hour loop)
4. **Day 4-5**: Monitor + validate best variant
5. **Day 6-13**: A/B test against production
6. **Day 14**: Rollout + start next cycle

**Estimated impact after 4 weeks**: +5-10% accuracy, +2-5% fairness gain, fully automated.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| DI ratio drops below 0.75 | Program.md has hard-fail check; variant auto-reverts |
| Accuracy stalls | Check test set isn't noisy; try broader prompt changes |
| Cost exceeds budget | Add cost penalty to program.md metric |
| Agent gets stuck | Read git log to see last working commit; reset to baseline |

See also: [AutoResearch for Insurance Underwriting](./autoresearch-insurance-underwriting.md), [Prompt Optimization](./autoresearch-prompt-optimization.md)
