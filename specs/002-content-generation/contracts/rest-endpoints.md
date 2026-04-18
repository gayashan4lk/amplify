# REST Endpoint Contract — Content Generation

**Feature**: 002-content-generation
**Base path**: `/api/v1/content`
**Auth**: Every request MUST carry the short-lived token established by the
Constitution security amendment (BetterAuth-minted JWT, verified by the
FastAPI auth middleware). `X-User-Id` trust is prohibited.

## `POST /api/v1/content/generate`

Trigger a new Content Generation Request for a brief.

**Request body:**
```json
{
  "brief_id": "…",
  "conversation_id": "…"
}
```

**Responses:**

- `200 OK` — run started.
  ```json
  { "request_id": "…", "sse_endpoint": "/api/v1/chat/stream?…" }
  ```
- `202 Accepted` — another run is already in-flight for this brief.
  ```json
  { "already_running": true, "request_id": "…" }
  ```
- `404 Not Found` — brief does not exist or is not owned by the caller.
- `409 Conflict` — brief exists but is incomplete (no findings to ground on).

## `POST /api/v1/content/{request_id}/regenerate`

Regenerate a single variant within an existing request.

**Request body:**
```json
{
  "variant_label": "A",
  "additional_guidance": "make it punchier"
}
```

`additional_guidance` is optional. `variant_label` is required and MUST be
`"A"` or `"B"`.

**Responses:**
- `200 OK` — regeneration queued.
  ```json
  { "request_id": "…", "variant_label": "A", "regenerations_used": 1 }
  ```
- `202 Accepted` — a run is currently in-flight for this brief; no-op.
- `409 Conflict` — regeneration cap reached.
  ```json
  { "reason": "regeneration_cap_reached", "regenerations_used": 3, "cap": 3 }
  ```
- `404 Not Found` — request or variant not found.

## `POST /api/v1/content/{request_id}/retry-half`

Targeted retry for the failing half of a partial variant (FR-012).

**Request body:**
```json
{
  "variant_label": "A",
  "half": "image"
}
```

`half` ∈ {`"description"`, `"image"`}. Does NOT count against the
regeneration cap — this only recovers a known failure rather than
producing new creative.

**Responses:**
- `200 OK` — retry queued.
- `409 Conflict` — variant is not in a partial-failure state.

## `GET /api/v1/content/{request_id}`

Fetch the full request (used for chat rehydration on page load).

**Responses:**
- `200 OK` — full `ContentGenerationRequest` document.
- `404 Not Found`.

## `GET /api/v1/content/image/{image_key}`

Returns a fresh signed URL for a stored image. Used when the cached URL on
a persisted variant has expired.

**Responses:**
- `200 OK` — `{ "signed_url": "…", "expires_at": "…" }`.
- `404 Not Found`.

## `GET /api/v1/briefs/{brief_id}/content-requests`

Rehydration helper: list all generation requests (newest first) for a
brief. Empty list if none.

**Responses:**
- `200 OK` — `{ "requests": [ContentGenerationRequest] }`.

## Idempotency & concurrency

- `generate` is gated by the Redis in-flight lock on `brief_id`
  (research §4).
- `regenerate` is gated by the same lock PLUS the per-variant
  `regenerations_used` counter (research §5).
- Clients SHOULD treat `202 already_running` as success-with-no-op and
  not retry automatically.
