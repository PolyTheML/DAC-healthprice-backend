# Microsoft AutoGen: Multi-Agent Framework

**Source**: [github.com/microsoft/autogen](https://github.com/microsoft/autogen)

**Type**: Open-Source Framework (Research)

**Status**: Maintenance mode (Microsoft recommends Agent Framework for new projects)

**Ingested**: 2026-04-09

---

## Overview

AutoGen is a framework for creating multi-agent AI applications where specialized agents work together autonomously or alongside humans. Developed by Microsoft Research, it enables sophisticated conversational AI where agents can delegate, negotiate, and collaborate.

**Key Use Case**: When you want your "Underwriting Agent" to talk to a "Compliance Agent" to resolve conflicts, or have agents specialize in different domains.

## Core Architecture

### Layered Design
1. **Core API**: Message passing and event-driven agent logic (Python & .NET)
2. **AgentChat API**: Simplified interfaces for rapid prototyping and common patterns
3. **Extensions API**: LLM integrations (OpenAI, Azure) and code execution capabilities

### Agent Communication
Agents exchange messages in structured formats, allowing them to:
- Interpret context
- Respond intelligently
- Delegate tasks
- Resolve disagreements through conversation

## Agent Collaboration Mechanisms

### Direct Conversation
- Two-agent interactions
- Group chats where multiple agents exchange information
- Natural negotiation between agents

### Tool-Based Delegation
- `AgentTool` feature enables agents to invoke other agents as specialized resources
- Hierarchical task decomposition

### External Capability Integration
- **MCP (Model Context Protocol) servers**
- Web browsing, file handling, API access
- Expands agent capabilities beyond pure reasoning

## Use Case: Underwriting Conflict Resolution

**Scenario**:
- **Underwriting Agent**: "This applicant is high-risk (BMI = 35, smoker)"
- **Medical Review Agent**: "Wait, she recently quit smoking (lab confirms 6 months)"
- **Pricing Agent**: "Re-price accordingly: 20% instead of 50% loading"
- **Compliance Agent**: "Confirm: decision recorded, audit trail logged"

All agents negotiate and reach consensus autonomously, then present unified recommendation to human underwriter.

## Status & Recommendation

**Note**: AutoGen is currently in **maintenance mode**.

Microsoft recommends new production projects use the **Microsoft Agent Framework** instead, which offers:
- Long-term support
- Better integration with Azure services
- Improved stability and documentation

**For Your Thesis**: Consider AutoGen for prototyping multi-agent conversations. For production, evaluate the Agent Framework or use [LangGraph](./langgraph.md) (more established for orchestration).

## Relevance to Thesis

- Shows how to build **conversational agent workflows**
- Agents can specialize (underwriting, compliance, pricing)
- Useful for scenarios where agents need to **resolve conflicts automatically**
- Alternative to [LangGraph](./langgraph.md) for some use cases

## Related Topics

- [Agent Orchestration & Frameworks](../topics/agent-orchestration.md)
- [LangGraph](./langgraph.md) — Recommended alternative for orchestration
- [Human-in-the-Loop Workflows](../topics/human-in-the-loop.md)
