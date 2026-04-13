# Contract: SSE Event Protocol

**Feature**: 001-research-agent
**Scope**: Typed events emitted by `POST /api/v1/chat/stream`.
**Protocol version**: `v: 1`

The event type set is closed. Adding a new event type is a MINOR version bump
per Constitution IV. Repurposing an existing type is prohibited.

---

## Wire format

Standard SSE frames:

```
id: <event_id>
event: <type>
data: <JSON>

```

- `id` is a monotonically increasing integer scoped to the stream. The client
  echoes the last seen id in `Last-Event-ID` on reconnect.
- `event` is the discriminator (`type` field inside `data` is duplicated for
  client convenience).
- `data` is a JSON object with the schema defined below.

Every `data` payload has these common fields:

```json
{
  "v": 1,
  "type": "<event_type>",
  "conversation_id": "string",
  "at": "2026-04-13T14:22:05.123Z"
}
```

Event-specific fields are added on top.

---

## Event types

### `conversation_ready`

Emitted once, first, when the stream opens. Sends the conversation id (new or
existing) so the client can update its URL.

```json
{
  "v": 1,
  "type": "conversation_ready",
  "conversation_id": "cuid",
  "at": "…",
  "is_new": true
}
```

### `agent_start`

A LangGraph node started.

```json
{
  "v": 1, "type": "agent_start", "conversation_id": "…", "at": "…",
  "agent": "supervisor | research | clarification",
  "description": "Routing your question"
}
```

### `agent_end`

A LangGraph node finished.

```json
{
  "v": 1, "type": "agent_end", "conversation_id": "…", "at": "…",
  "agent": "supervisor | research | clarification"
}
```

### `tool_call`

An agent invoked a tool.

```json
{
  "v": 1, "type": "tool_call", "conversation_id": "…", "at": "…",
  "tool": "tavily_search",
  "input": { "query": "…" }
}
```

### `tool_result`

A tool returned.

```json
{
  "v": 1, "type": "tool_result", "conversation_id": "…", "at": "…",
  "tool": "tavily_search",
  "result_count": 7,
  "duration_ms": 842
}
```

Note: tool results do NOT include raw payloads on the wire (only counts and
durations). Full results go into LangSmith traces.

### `progress`

Human-readable progress update during a long-running phase.

```json
{
  "v": 1, "type": "progress", "conversation_id": "…", "at": "…",
  "phase": "planning | searching | synthesizing | validating",
  "message": "Searching competitor ad activity…",
  "detail": { "sub_query": "…" }
}
```

### `text_delta`

Streamed text token for chat-style assistant responses (used when the
Supervisor routes to plain reply, not to research).

```json
{
  "v": 1, "type": "text_delta", "conversation_id": "…", "at": "…",
  "message_id": "cuid",
  "delta": "…"
}
```

### `ephemeral_ui`

An inline UI component to render in the conversation. Schema types live in
`apps/api/models/ephemeral.py` and are mirrored to TS types at build time.

```json
{
  "v": 1, "type": "ephemeral_ui", "conversation_id": "…", "at": "…",
  "message_id": "cuid",
  "component_type": "intelligence_brief | clarification_poll",
  "component": { /* component-specific schema */ }
}
```

For this slice:

**`intelligence_brief` component** — the full `IntelligenceBrief` payload per
`intelligence-brief.md`.

**`clarification_poll` component**:
```json
{
  "research_request_id": "cuid",
  "prompt": "Which direction do you want me to take?",
  "options": [
    "Focus on LinkedIn activity only",
    "Look across LinkedIn and Twitter",
    "Include their website and blog"
  ]
}
```

### `error`

A failure occurred. Per Constitution V, every failure path emits exactly one
of these — never silent.

```json
{
  "v": 1, "type": "error", "conversation_id": "…", "at": "…",
  "code": "tavily_unavailable | tavily_rate_limited | llm_unavailable | llm_invalid_output | no_findings_above_threshold | user_cancelled | budget_exceeded | rate_limited_user",
  "message": "Our search provider is temporarily unreachable.",
  "recoverable": true,
  "suggested_action": "Try again in a minute.",
  "failure_record_id": "cuid"
}
```

**Invariants**
- `message` is non-empty and user-meaningful (no "something went wrong").
- `recoverable: true` requires `suggested_action` to be set.
- `failure_record_id` references a persisted `FailureRecord` that will also be
  visible on conversation reload.

### `done`

The stream terminates successfully. Always the last event for a successful
interaction. Not emitted after an `error`.

```json
{
  "v": 1, "type": "done", "conversation_id": "…", "at": "…",
  "final_status": "brief_ready | text_only | awaiting_clarification",
  "summary": "3 findings, 2 high-confidence"
}
```

---

## Sequencing rules

- `conversation_ready` is always first.
- `agent_start` and `agent_end` are always balanced per agent invocation.
- Every research run produces exactly one of: an `ephemeral_ui` with
  `component_type: "intelligence_brief"`, an `ephemeral_ui` with
  `component_type: "clarification_poll"`, or an `error`.
- A stream terminates with exactly one of: `done`, `error`.

---

## Client contract

- The frontend (`apps/web/components/chat/stream-renderer.tsx`) MUST:
  1. Handle all documented event types.
  2. Ignore unknown event types gracefully (forward-compat).
  3. De-duplicate events by `id` on reconnect.
  4. Reject payloads with `v != 1` with a visible error.

- A typed TypeScript discriminated union is generated from Pydantic models
  into `apps/web/lib/types/sse-events.ts` at build time to enforce this
  contract in both directions.
