# SSE Event Contract — Content Generation

**Feature**: 002-content-generation
**Status**: Additive to the existing Stage 1 protocol. No existing event
type is repurposed (Constitution IV — backward-compatible).

All events share the Stage 1 envelope: `event: <type>`, `data: <json>` with
`conversation_id`, `message_id`, and `trace_id` fields on every payload.

## New event types

### `content_suggestions`

Emitted once per run, right after the Supervisor routes into the Content
Generation Agent. Advances the request from `suggesting` → `awaiting_input`.

```json
{
  "conversation_id": "…",
  "message_id": "…",
  "trace_id": "…",
  "request_id": "…",
  "suggestions": [
    {
      "id": "s-1",
      "text": "Lead with the 3× faster onboarding finding.",
      "finding_ids": ["f-17"],
      "low_confidence": false
    }
  ],
  "question": "What should the post say, who is it for, and what tone?"
}
```

### `content_variant_progress`

Emitted repeatedly while a variant is being produced. `step` is a free-form
short label (e.g., `"drafting copy"`, `"generating image"`), `variant_label`
is `"A"` or `"B"`.

```json
{
  "conversation_id": "…",
  "request_id": "…",
  "variant_label": "A",
  "step": "drafting copy",
  "progress_hint": 0.4
}
```

`progress_hint` is optional and best-effort.

### `content_variant_ready`

Emitted when a full variant (description AND image) is ready to render.

```json
{
  "conversation_id": "…",
  "request_id": "…",
  "variant": { /* PostVariant payload */ }
}
```

### `content_variant_partial`

Emitted when ONE half of a variant is ready but the other failed or is
still pending, so the UI can render what it has and offer a targeted
retry (FR-012).

```json
{
  "conversation_id": "…",
  "request_id": "…",
  "variant_label": "A",
  "description_status": "ready",
  "image_status": "failed",
  "description": "…",
  "image_signed_url": null,
  "retry_target": "image"
}
```

### `ephemeral_ui` (existing type, new component)

Reuses the existing event; adds two new component discriminators:
`content_suggestions` and `content_variant_grid`. See
[data-model.md](../data-model.md) for payload shape.

## Error semantics

Failures reuse the existing `error` event with `recoverable` set:

- Whole-run timeout → `recoverable: false`, `code: "content_gen_timeout"`.
- Safety-blocked → `recoverable: true`, `code: "content_safety_blocked"`,
  with a short user-facing reason.
- Concurrent-click collision → no SSE; the HTTP trigger returns `202` with
  `already_running: true` and the client stays silent (FR-013).

## Ordering guarantees

Per run:
1. Exactly one `content_suggestions` before the first
   `content_variant_progress`.
2. Any number of `content_variant_progress` events, interleaved for A/B.
3. Either `content_variant_ready` (both halves) OR
   `content_variant_partial` (one half) per variant, per regeneration.
4. A terminal `done` event (existing type) once both variants have reached
   a terminal state (ready, partial, or failed).

No `content_variant_ready` for a given `(request_id, variant_label)` MAY
precede that request's `content_suggestions`.
