# Guardrails AI: LLM Reliability & Output Validation

**Source**: [guardrailsai.com/docs](https://guardrailsai.com/docs)

**Type**: Python Framework for Output Safety

**Ingested**: 2026-04-09

---

## Overview

Guardrails AI is a Python framework that ensures LLM outputs are reliable, valid, and safe by wrapping LLM interactions with input/output guards. Critical for insurance: **you cannot have AI hallucinate a blood pressure reading**.

**Core Purpose**: Force LLMs to output valid JSON, avoid hallucinations, and meet domain constraints.

## The Problem It Solves

### Hallucination Risk in Insurance
- LLM might invent a medical value: "systolic BP: 142" (when document says 140)
- Slight inaccuracy in extracted data compounds downstream
- Pricing models depend on accurate inputs
- Regulators require auditability of source data

### Constraint Enforcement
- Medical variables must be in valid ranges (BMI: 10-60, not 1000)
- Required fields must be present
- Data types must match schema (integer for age, not "young")

## How It Works

### Two-Phase Protection

**Input Guards**:
- Validate user input before sending to LLM
- Detect problematic or unsafe inputs
- Reduce confusion or manipulation attempts

**Output Guards**:
- Intercept LLM output before returning to application
- Check against expected schema
- Detect hallucinations, inconsistencies, invalid values
- Force re-generation if needed

### Risk Detection & Mitigation

Guardrails:
1. **Detects** specific risks (hallucination, toxicity, PII exposure, format violations)
2. **Quantifies** severity of detected issues
3. **Mitigates** automatically (rejects output, requests re-generation, flags for review)

### Structured Data Generation

Ensures LLMs output valid structured formats:
- **JSON Schema**: {"age": int, "bmi": float, "smoker": bool, "conditions": string[]}
- **Validation**: Rejects outputs that don't match schema
- **Correction**: Can automatically request re-generation with corrections

## The Hub: Validator Library

**Guardrails Hub** is a repository of pre-built validators:
- **Toxicity Check**: Detect offensive language
- **PII Detection**: Find personal identifiable information leaks
- **Format Validation**: Ensure JSON/CSV compliance
- **Domain-Specific**: Medical value ranges, field requirements
- **Custom**: Build your own validators

**Composition**: Chain multiple validators into comprehensive guards.

## Example: Medical Data Extraction Guard

```
Input: PDF medical record
  ↓
LLM: Extract to JSON
  ↓
Output Guard:
  - age: 20-100 ✓
  - systolic_bp: 80-200 ✓
  - diastolic_bp: 40-120 ✓
  - bmi: 10-60 ✓
  - conditions: non-empty list ✓
  ↓
Valid JSON returned
  ↓
Risk Score calculation
```

If any value fails validation:
- Flag for manual review
- Request LLM re-extraction
- Log the error for audit trail

## Relevance to Thesis

This is the **reliability & safety layer** that:
1. Ensures extracted medical data is valid JSON (not hallucinated)
2. Prevents garbage data from reaching pricing models
3. Catches errors before regulatory audit
4. Provides confidence scores for decisions
5. Builds auditable evidence that outputs were validated

**For Insurance Compliance**:
- Demonstrates rigor in data validation
- Shows due diligence to regulators
- Supports "Human-in-the-Loop" by flagging uncertain extractions
- Critical for Cambodia: "We validate every data point"

## Integration Points

Works with:
- LLMs (Claude, GPT, etc.)
- [LangGraph](./langgraph.md) workflows
- [Document extraction](../topics/document-extraction.md) pipelines
- [Risk scoring](../topics/risk-scoring.md) models

## Architecture in Your Stack

```
Medical PDF
  ↓
LlamaParse (extract tables)
  ↓
Claude (structure to JSON)
  ↓
Guardrails (validate schema & values)
  ↓
Frequency-Severity GLM (calculate risk)
```

## Related Topics

- [Agent Safety & Reliability](../topics/agent-safety.md)
- [Document Extraction & Medical Parsing](../topics/document-extraction.md)
- [Medical Data Validation](../topics/medical-data-validation.md)
- [Insurance Compliance & Governance](../topics/compliance-governance.md)
