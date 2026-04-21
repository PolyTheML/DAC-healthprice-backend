# Strands Agents

**Type**: Open-source agent framework  
**License**: Apache 2.0  
**Repository**: [github.com/stripe-archive/strands-agents](https://github.com/stripe-archive)  
**Created**: 2026-04-10  
**Last updated**: 2026-04-10

## Overview

Strands Agents is an open-source framework for building production-grade agentic systems, showcased by Stripe in their "Minions" engineering paradigm. The framework emphasizes:

- **Deterministic phase coordination** mixed with agentic loops
- **Scoped context engineering** (rule files + MCP tools per phase)
- **Tool registry discovery** (agents find tools on-demand, not all-at-once)
- **Production observability** (trace every agent action for debugging/audit)

## Key Features

- **Blueprint Pattern**: Mix deterministic nodes with agentic refinement loops
- **Context Curation**: Agents see only relevant rules and tools per task
- **Memory Management**: Maintains state across multi-turn interactions
- **Error Handling**: Graceful fallbacks, retry logic, human escalation

## Use Cases

- **Document processing**: Extract fields with adaptive reasoning (not rigid pipelines)
- **Code generation**: Multi-step engineering tasks with strategic advisor
- **Claims assessment**: Multi-document analysis with contradiction detection
- **Underwriting**: Medical record analysis with regulatory compliance checking

## Relevance to DAC-UW

Strands Agents pattern aligns with **agentic reasoning** needed for medical document extraction. See:
- [Agentic Reasoning](../topics/agentic-reasoning.md) — Conceptual foundation
- [Agent Harness: Deterministic Phases](../topics/agent-harness-deterministic-phases.md) — DAC-UW implementation pattern
- [Document AI Course: Lesson 6](../topics/lesson-6-production-aws-deployment.md) — AWS deployment

## Further Reading

- Stripe blog: "Minions: Towards Simplifying the Creation of LLM-Powered Tools and Agents"
- [Stripe Minions: One-Shot Agentic Coding](../sources/stripe-minions-agentic-coding.md) — Full technical overview
