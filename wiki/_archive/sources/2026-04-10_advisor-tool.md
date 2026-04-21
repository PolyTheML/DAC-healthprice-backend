# Advisor Tool (Claude API)

**Source**: https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool  
**Ingested**: 2026-04-10  
**Type**: Technical documentation  
**Related**: [Advisor-Executor Pattern](../topics/advisor-executor-pattern.md), [Command Center + Advisor Integration](../topics/command-center-advisor-integration.md)

## Overview

The advisor tool is a Claude API feature (beta, requires header `advisor-tool-2026-03-01`) that pairs a **faster executor model** with a **higher-intelligence advisor model** for mid-generation strategic guidance. The executor calls the advisor mid-task, the advisor reads the full transcript and produces a plan or course correction (400–700 tokens, ~1,400–1,800 total with thinking), and the executor continues.

## Valid Model Pairs

| Executor | Advisor |
|----------|---------|
| Claude Haiku 4.5 | Claude Opus 4.6 |
| Claude Sonnet 4.6 | Claude Opus 4.6 |
| Claude Opus 4.6 | Claude Opus 4.6 |

Invalid pairings return HTTP 400 `invalid_request_error`.

## How It Works (Request-Level)

All execution happens within a single `/v1/messages` request:

1. **Executor emits**: `server_tool_use` block with `name: "advisor"` and empty `input: {}`
2. **Server-side**: Anthropic runs separate inference on advisor model, passing executor's full transcript (system prompt, tool definitions, all prior turns, all tool results)
3. **Advisor responds**: Text advice (or encrypted `advisor_redacted_result` for compliance models)
4. **Result returns**: `advisor_tool_result` block with `content.type: "advisor_result"` or `"advisor_redacted_result"`
5. **Executor continues**: Informed by the advice, generating its final output

No extra round trips on the client side. The advisor runs without tools and without context management; its thinking blocks are dropped before returning.

## Billing & Cost

Advisor calls are billed separately at the advisor model's rates (Opus pricing):
- Top-level `usage` totals reflect executor tokens only
- Per-call breakdown in `usage.iterations[]`:
  - `type: "message"` → executor iteration, billed at executor rate
  - `type: "advisor_message"` → advisor iteration, billed at Opus rate
- Typical advisor output: 400–700 text tokens, 1,400–1,800 total with thinking
- Cost savings: Executor generates final output at its cheaper rate; advisor only produces the plan

**Cost sweet spots** (per docs):
- Use Sonnet executor + Opus advisor if currently using Sonnet for complex tasks → quality lift at similar/lower total cost
- Use Haiku executor + Opus advisor if currently using Haiku → higher cost than Haiku alone, but lower than switching to Sonnet

## Tool Parameters

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `type` | string | required | Must be `"advisor_20260301"` |
| `name` | string | required | Must be `"advisor"` |
| `model` | string | required | Advisor model ID (e.g., `"claude-opus-4-6"`) |
| `max_uses` | integer | unlimited | Per-request cap; exceeded calls return `error_code: "max_uses_exceeded"` |
| `caching` | object \| null | off | Enable prompt caching: `{"type": "ephemeral", "ttl": "5m" \| "1h"}`. Breaks even at ~3 calls per conversation. |

## Response Structure

### Successful call

```json
{
  "type": "advisor_tool_result",
  "tool_use_id": "srvtoolu_abc123",
  "content": {
    "type": "advisor_result",
    "text": "Use a channel-based coordination pattern..."
  }
}
```

### Error variants

| `error_code` | Meaning |
|--------------|---------|
| `max_uses_exceeded` | Hit the `max_uses` cap |
| `too_many_requests` | Advisor rate-limited |
| `overloaded` | Advisor hit capacity limits |
| `prompt_too_long` | Transcript exceeded advisor context window |
| `execution_time_exceeded` | Advisor sub-inference timed out |
| `unavailable` | Other advisor failure |

Executor sees the error and continues without further advice; request does not fail.

## Best Use Cases

**Good fit:**
- Long-horizon agentic workloads (coding agents, computer use, multi-step research pipelines)
- Tasks where most turns are mechanical but having an excellent plan is crucial
- Complex decision-making mid-task with full context

**Poor fit:**
- Single-turn Q&A (nothing to plan)
- Pure pass-through model pickers
- Workloads where every turn requires full advisor capability

## Multi-Turn Conversations

Pass the full assistant content (including `advisor_tool_result` blocks) back to the API on subsequent turns. If you omit the advisor tool from `tools` while message history still contains `advisor_tool_result` blocks, the API returns a 400 error.

**Conversation-level budgeting**: No built-in cap. Count advisor calls client-side; when reaching budget, remove the tool and strip `advisor_tool_result` blocks from history.

## Prompt Caching

**Two layers**:
1. **Executor-side**: `advisor_tool_result` block is cacheable like any content; `cache_control` breakpoints after it hit on subsequent turns
2. **Advisor-side**: Set `caching` on tool definition. Advisor's N-th call prompt = (N-1)-th call prompt + one delta. Breaks even at ~3 calls; ideal for agent loops.

Warning: Extended thinking with `clear_thinking` (other than `keep: "all"`) shifts advisor's quoted transcript, causing cache misses (cost only, not quality).

## Streaming

Advisor sub-inference does not stream. Stream pauses while advisor runs (quiet except ~30s SSE pings); when advisor finishes, full result arrives in one `content_block_start` event. Executor output then resumes.

## Suggested System Prompt (Coding/Agent Tasks)

For consistent timing (~2–3 advisor calls per task), prepend to executor system prompt:

```
You have access to an `advisor` tool backed by a stronger reviewer model. 
It takes NO parameters — when you call advisor(), your entire conversation 
history is automatically forwarded.

Call advisor BEFORE substantive work — before writing, before committing to 
an interpretation, before building on an assumption. If orientation first is 
needed (finding files, fetching sources), do that, then call advisor.

Also call advisor:
- When you believe the task is complete (AFTER making deliverable durable)
- When stuck (errors recurring, approach not converging)
- When considering a change of approach

Give the advice serious weight. If empirical failure or primary-source evidence 
contradicts a specific claim, adapt. A passing self-test ≠ the advice is wrong.

[Optional conciseness clause to reduce advisor output tokens by ~35–45%:]
The advisor should respond in under 100 words and use enumerated steps, not explanations.
```

## Composability

The advisor tool composes with other server-side and client-side tools. Add them all to the same `tools` array. Executor can search web, call advisor, and invoke custom tools in the same turn.

## Status & Access

- **Availability**: Claude API (Anthropic) only, beta
- **Access**: Request via Anthropic account team
- **Zero Data Retention eligible**: When your org has a ZDR arrangement, data is not stored after API response
