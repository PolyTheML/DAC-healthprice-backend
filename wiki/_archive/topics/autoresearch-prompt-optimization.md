# AutoResearch for Prompt Optimization

**Created**: 2026-04-10  
**Last Updated**: 2026-04-10  
**Source**: [AutoResearch Tutorial — YouTube](../sources/2026-04-10_autoresearch-tutorial-youtube.md)

---

## Overview

Prompt engineering is a natural candidate for AutoResearch because system instructions are the **most direct way to shape LLM behavior** without retraining. Rather than manually tweaking prompts, AutoResearch runs hundreds of prompt variants overnight, measuring each against your metric, keeping winners, and discarding losers.

---

## Why Prompt Optimization via AutoResearch

**Traditional approach**:
- Human manually edits prompt
- Tests on a few examples
- Takes days to see meaningful improvement
- Hard to compare variants fairly (different test sets, cherry-picked examples)

**AutoResearch approach**:
- Agent proposes prompt variant (new phrasing, structure, examples, language, proficiency level)
- Tests on **fixed test set** with **automated metric**
- Runs 100+ variants overnight
- Keeps only statistically significant improvements
- Fully auditable (git history of all attempts)

---

## Architecture for Prompt Optimization

### Three Files

1. **program.md**
   - Goal: "Improve underwriting accuracy while maintaining fairness"
   - Constraints:
     - Prompt length: ≤2000 tokens
     - Must include fairness preamble
     - Cannot reference sensitive attributes (age, zip)
     - Max 10 reasoning steps
   - Iteration rules: Keep if metric improves >0.5%; revert otherwise
   - Time budget: 2 min per evaluation (full test set)

2. **train.py** (the system prompt)
   ```python
   SYSTEM_PROMPT = """You are an expert underwriter for DAC Insurance (Cambodia).
   Your task is to assess insurance applications and make approval decisions.
   
   [Agent will iteratively modify this: phrasing, structure, examples, constraints]
   """
   ```

3. **prepare.py** (evaluation metric)
   ```python
   def evaluate_prompt(variant_prompt):
       results = run_prompt_on_test_set(variant_prompt)
       
       accuracy = compute_accuracy(results)
       fairness_score = compute_fairness_metrics(results)  # Disparate impact, demographic parity
       
       # Weighted metric: accuracy 70%, fairness 30%
       score = 0.7 * accuracy + 0.3 * fairness_score
       return score
   ```

   **Key**: prepare.py is **immutable**. Agent cannot tweak the metric to fake improvements.

---

## What the Agent Can Modify

The prompt variant space is **large**:

- **Phrasing**: "Assess the applicant's medical risk" vs. "Determine suitability for standard rates"
- **Structure**: Few-shot examples, step-by-step reasoning, chain-of-thought
- **Language**: English vs. Khmer vs. technical terms vs. simple language
- **Proficiency level**: Beginner, college, PhD-level complexity
- **Examples**: Different medical cases in the prompt
- **Constraints**: Add guardrails (e.g., "Do not make assumptions about marital status")
- **Reasoning steps**: Force explicit reasoning (e.g., "Step 1: Extract key medical facts. Step 2: Assess mortality risk...")
- **Format**: JSON output vs. natural language vs. structured fields

---

## Success Metrics for Prompt Optimization

### Accuracy Metrics
- **Approval rate alignment**: Does variant match historical approval rates for similar applicants?
- **Test set accuracy**: Measure on held-out labeled test set (ground truth = human decisions or outcomes)
- **Confidence calibration**: Does model confidence correlate with actual correctness?

### Fairness Metrics (per [DAC Fairness Framework](../topics/underwriting-fairness-audit.md))
- **Disparate impact ratio**: Approval rate for Group A / Approval rate for Group B (target: >80%)
- **Demographic parity**: Reject reasons equally distributed across groups
- **Equalized odds**: False positive rate + false negative rate balanced across groups

### Efficiency Metrics
- **Time per decision**: Tokens generated, latency
- **Cost per decision**: API calls to LLM, model size

### Combined Metric
```
score = 0.70 * accuracy + 0.20 * fairness + 0.10 * efficiency
```

Adjust weights based on your business priorities. **Must be automated and fast** to enable overnight loops.

---

## Iteration Process

### Step 1: Baseline
- Establish current system prompt performance
- Measure accuracy, fairness, efficiency on test set
- Record in results.tsv

### Step 2: Agent Loop (repeat until convergence or budget exhausted)
1. Agent reads program.md constraints
2. Proposes new prompt variant (with hypothesis: "Adding step-by-step reasoning should improve accuracy")
3. Saves to train.py
4. Runs evaluate (prepare.py) on fixed test set
5. If score > baseline + threshold: git commit, update baseline
6. If not: git reset, try next variant

### Step 3: Analysis
- Review git log to see all variants tried
- Identify patterns (what changed in winners vs. losers)
- Run final winner on holdout validation set
- A/B test against current production prompt before rollout

---

## Real Example: Underwriting Fairness Tuning

**Starting prompt** (baseline):
```
You are an insurance underwriter. Assess medical risk and decide approval.
```

**Agent iterations** (hypothetical):
1. Variant: Add demographic parity constraint → accuracy ↓2%, fairness ↑8% (keep)
2. Variant: Reorder examples by age → accuracy ↑1%, fairness ↓1% (revert)
3. Variant: Add "Do not use age/zip as proxy" → accuracy =, fairness ↑3% (keep)
4. Variant: Add step-by-step medical reasoning → accuracy ↑5%, fairness ↑1% (keep)
5. Variant: Khmer language examples → accuracy ↑2% (Cambodian applicants), overall ↑1% (keep for fairness)

**Result after 100 iterations**: 8% accuracy gain + 12% fairness gain + explicit fairness reasoning = production-ready.

---

## When Prompt Optimization via AutoResearch Works

✅ **Good candidates**:
- High-volume decisions (100s/day) so test set is large
- Quantifiable metric available (accuracy, fairness, latency)
- Prompt is bottleneck (not document quality, not model capability)
- Cost to iterate is low (test set runs in seconds)

❌ **Poor candidates**:
- Low-volume, high-stakes decisions (can't gather test data)
- Metric is subjective (e.g., "tone" of response)
- Prompt is already near-optimal (diminishing returns)
- Model limitation is the constraint, not prompt design

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| **Overfitting to test set** | Hold out separate validation set; test on real data before rollout |
| **Unforeseen failure modes** | Add explicit constraints in program.md (e.g., "Never approve high-risk applicants") |
| **Fairness gaming** | Weight fairness equally with accuracy in metric; require fairness improvement, not just accuracy |
| **Prompt becomes uninterpretable** | Limit prompt length + complexity in program.md; require human-readable reasoning |
| **Rollout risk** | A/B test winner against current prod for 1-2 weeks before full rollout |

---

## Key Takeaway

Prompt optimization via AutoResearch shifts the bottleneck from **manual iteration** (slow, subjective) to **metric design** (must be clear, automated, fair). Once your metric is right, the agent finds improvements you wouldn't discover manually. For insurance underwriting, this means: **Define fairness + accuracy metrics, let AutoResearch find the prompt that wins on both.**

See also: [AutoResearch for Insurance Underwriting](./autoresearch-insurance-underwriting.md), [DAC Implementation Guide](./autoresearch-dac-implementation.md)
