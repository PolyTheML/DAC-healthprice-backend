# AgentOps: Agent Monitoring & Observability

**Source**: [github.com/agentops-ai/agentops](https://github.com/agentops-ai/agentops)

**Type**: Observability Platform / DevTool

**Ingested**: 2026-04-09

---

## Overview

AgentOps is a comprehensive monitoring, observability, and DevTool platform designed for AI agents. It helps developers "build, evaluate, and monitor AI agents—from prototype to production."

**Core Value**: Essential for thesis defense. Shows how every underwriting decision was made, step-by-step, with full traceability.

## Key Features

### Analytics & Debugging
- **Step-by-step execution graphs**: Replay and analyze agent behavior in detail
- **Decision tree visualization**: See exactly which branches the agent took
- **Debugging interface**: Understand why the agent made a specific choice

### Cost Tracking
- LLM spend management across providers
- Monitor API costs per underwriting workflow
- Budget alerts and forecasting

### Multi-Framework Integration
- Native integrations with:
  - CrewAI
  - AG2 (AutoGen)
  - Agno
  - **LangGraph** (your orchestration framework)
  - Others
- Framework-agnostic observability

### Self-Hosting Options
- On-premises deployment available
- Data privacy and compliance control
- Flexibility for regulated environments (important for Cambodia)

### Minimal Setup
- Just two lines of code to enable
- Automatic telemetry collection
- Zero-friction instrumentation

## What It Tracks

AgentOps captures comprehensive telemetry:

**Agent Operations**:
- LLM API calls and interactions
- Agent execution flows and decision paths
- Tool usage and function calls
- Session metadata and performance metrics

**Data & Context**:
- Input/output data for operations
- Intermediate states and reasoning steps
- Exception handling and error information
- Streaming interactions and real-time events

**Session Data**:
- Complete session history
- Performance metrics (latency, cost, tokens)
- User interactions and overrides

## Dashboard & Visualization

All session data accessible through:
- Interactive execution graphs
- Performance metrics (cost, latency, token usage)
- Search and filtering capabilities
- Export for compliance audits

## Relevance to Thesis

This is the **observability layer** that:
1. Proves to regulators how every underwriting decision was made
2. Shows the decision trace: "extract → validate → price → review → approve"
3. Enables debugging when something goes wrong
4. Provides metrics for continuous improvement
5. Supports compliance investigations
6. **Critical for Cambodian regulator acceptance**: "Here's the full audit trail of every decision"

## Use Cases for Insurance

- **Regulatory Compliance**: "Show the underwriter how the AI made this decision"
- **Quality Auditing**: Sample decisions and verify AI reasoning
- **Cost Management**: Track LLM costs per underwriting workflow
- **Performance Improvement**: Identify bottlenecks and inefficiencies
- **Dispute Resolution**: Replay exact decision flow when policyholder contests denial

## Integration with Your Stack

```
Your Underwriting Agent (LangGraph)
         ↓
    AgentOps Integration (2 lines of code)
         ↓
    Step-by-step Execution Logging
         ↓
    Dashboard + Audit Trail
         ↓
    Regulatory Compliance Evidence
```

## Related Topics

- [Agent Orchestration & Frameworks](../topics/agent-orchestration.md)
- [Agent Safety & Reliability](../topics/agent-safety.md)
- [Insurance Compliance & Governance](../topics/compliance-governance.md)

## Cost Considerations

AgentOps has usage-based pricing. For insurance underwriting:
- Typically costs <$1 per policy reviewed
- ROI comes from reduced underwriter review time
- Self-hosting option for large volumes
