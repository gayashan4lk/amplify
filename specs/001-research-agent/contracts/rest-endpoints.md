# Contract: REST Endpoints

**Feature**: 001-research-agent
**Scope**: HTTP endpoints exposed by the FastAPI backend for this slice.
All endpoints are private-network only. Auth context is passed from Next.js
via the `X-User-Id` header (see SAD §6.3 and ADR-006).

---

## Conventions

- **Base path**: `/api/v1`
- **Auth**: middleware reads `X-User-Id`; rejects with `401` if missing.
  Webhook paths are exempt but there are no webhooks in this slice.
- **Content-Type**: `application/json` unless noted (SSE uses `text/event-stream`).
- **Error envelope** (non-SSE responses):
  ```json
  { "error": { "code": "string", "message": "string", "recoverable": true } }
  ```
- **Pagination**: cursor-based via `cursor` query param; responses include
  `next_cursor` (nullable).

---

## `POST /api/v1/chat/stream`

Start or continue a research interaction. Opens an SSE stream.

### Request

**Headers**
- `X-User-Id: <user id>` (required)
- `Accept: text/event-stream`
- `Last-Event-ID: <event id>` (optional; used on reconnect for resume)

**Body**
```json
{
  "conversation_id": "string | null",
  "message": "string"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `conversation_id` | string? | no | Null for a brand-new conversation; server creates one and emits its id on the first event. |
| `message` | string | yes | 1–4000 characters. |

### Responses

**200 OK** — `Content-Type: text/event-stream`. Stream format defined in
`sse-events.md`.

**400** — invalid body (empty message, oversize message).
**401** — missing `X-User-Id`.
**404** — `conversation_id` provided but not owned by user.
**429** — per-user rate limit (10 research requests/hour).

### Side effects

- Creates a `Conversation` row if `conversation_id` is null.
- Creates a user `Message` row immediately.
- Creates a pending `ResearchRequest` if the Supervisor routes to `research`.
- Streams events until `done` or `error`.

---

## `POST /api/v1/chat/ephemeral`

User response to an inline ephemeral UI component (clarification poll in this
slice). Resumes an interrupted LangGraph run.

### Request

**Headers**: `X-User-Id` (required)

**Body**
```json
{
  "conversation_id": "string",
  "research_request_id": "string",
  "component_type": "clarification_poll",
  "response": { "selected_option_index": 0 }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `conversation_id` | string | yes | |
| `research_request_id` | string | yes | Must be in `pending` state awaiting clarification. |
| `component_type` | string | yes | `clarification_poll` for this slice. |
| `response` | object | yes | Shape depends on `component_type`. For `clarification_poll`: `{ selected_option_index: int }`. |

### Responses

**202 Accepted** — the research request has resumed. The frontend should
already have an open SSE stream receiving subsequent events.
**400** — invalid body.
**404** — conversation or research request not found for this user.
**409** — research request is not waiting on clarification (already running /
complete / failed).

---

## `GET /api/v1/conversations`

List the current user's conversations.

### Query
- `cursor` (optional)
- `limit` (optional, default 25, max 100)

### Response `200 OK`

```json
{
  "conversations": [
    {
      "id": "string",
      "title": "string",
      "created_at": "2026-04-13T14:22:00Z",
      "updated_at": "2026-04-13T14:45:12Z",
      "latest_status": "complete | pending | failed"
    }
  ],
  "next_cursor": "string | null"
}
```

---

## `GET /api/v1/conversations/{id}`

Fetch a full conversation with all messages and any embedded intelligence
briefs (resolved from MongoDB) and failure records.

### Response `200 OK`

```json
{
  "id": "string",
  "title": "string",
  "created_at": "2026-04-13T14:22:00Z",
  "updated_at": "2026-04-13T14:45:12Z",
  "messages": [
    {
      "id": "string",
      "role": "user | system | assistant",
      "content": "string",
      "created_at": "2026-04-13T14:22:00Z",
      "progress_events": [ /* ProgressEvent[] */ ],
      "brief": null,
      "failure": null
    },
    {
      "id": "string",
      "role": "assistant",
      "content": "Here is what I found.",
      "created_at": "2026-04-13T14:22:45Z",
      "progress_events": [],
      "brief": { /* full IntelligenceBrief per intelligence-brief.md */ },
      "failure": null
    }
  ]
}
```

**404** — not found or not owned by user (indistinguishable to avoid leaking
existence).

---

## `DELETE /api/v1/conversations/{id}`

Soft-delete (archive) a conversation.

**Response `204 No Content`**

---

## Rate limits (Redis-backed)

| Scope | Limit | Response on breach |
|---|---|---|
| Research requests per user | 10 / hour | `429` with `retry_after_seconds` |
| Chat stream opens per user | 30 / minute | `429` |
| Ephemeral responses per user | 60 / minute | `429` |

---

## Out of scope for this slice

These endpoints will be added by later specs and are intentionally NOT part of
this contract:

- `/api/v1/campaigns/*`
- `/api/v1/integrations/*`
- `/api/v1/webhooks/*`
- Any endpoint that publishes, sends, or deploys content
