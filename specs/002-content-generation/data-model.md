# Phase 1: Data Model — Content Generation

**Feature**: 002-content-generation
**Date**: 2026-04-19
**Source spec**: [spec.md](./spec.md) §Key Entities + §Functional Requirements

All models are Pydantic v2 on the backend and surfaced to the frontend via
generated Zod schemas. Storage is MongoDB (content docs) + Postgres (usage
counters, failure records) + object storage (image bytes).

## Collections

- `content_generation_requests` — one document per user run; nests variants
  and suggestions.
- `intelligence_briefs` — existing (Stage 1); gains a read-only
  `generation_request_ids: [ObjectId]` back-reference array.

## Entities

### `ContentGenerationRequest`

| Field | Type | Notes |
|---|---|---|
| `id` | `ObjectId` | Primary key. |
| `brief_id` | `ObjectId` | Required. FK to `intelligence_briefs`. |
| `conversation_id` | `UUID` | Required. Denormalised for chat rehydration. |
| `user_id` | `UUID` | Required. Owner (matches brief owner). |
| `status` | `enum` | `suggesting \| awaiting_input \| generating \| complete \| failed`. |
| `suggestions` | `PostSuggestion[]` | 2–4 items when status ≥ `awaiting_input`, else empty. |
| `user_direction` | `string?` | The user's creative-direction reply; present from `generating` onward. |
| `variants` | `PostVariant[]` | Length exactly 2 at `complete`; may be shorter while `generating`. |
| `diversity_warning` | `bool` | True if the similarity check ran out of retries (per research §6). |
| `started_at` | `datetime` | Set when `suggesting`. |
| `completed_at` | `datetime?` | Set on terminal state. |
| `error` | `FailureRecordRef?` | FK into the existing failure-records table (terminal failures only). |
| `schema_version` | `int` | Starts at 1. |

**Validation rules**:
- `variants.length` ∈ {0, 1, 2}; never > 2 (FR-004).
- `suggestions.length` ∈ {2, 3, 4} when surfaced (FR-002).
- `status` transitions only follow the state machine below.

**State machine**:
```
suggesting → awaiting_input → generating → complete
                                         ↘ failed
   ↘ failed (if suggestion step blows up)
```
Re-entry: regenerating a single variant does NOT mutate the parent status;
it operates on the nested `PostVariant` directly.

---

### `PostVariant`

| Field | Type | Notes |
|---|---|---|
| `label` | `enum` | `"A" \| "B"`. Unique within a request. |
| `description` | `string` | 80–250 chars inclusive (FR-006). Must include ≥1 emoji from the conservative-render set. |
| `description_status` | `enum` | `pending \| ready \| failed`. |
| `image_key` | `string?` | Opaque object-storage key. Null until image ready. |
| `image_signed_url` | `string?` | Cached signed URL with TTL (see research §3). |
| `image_width` | `int` | Fixed at 1080. |
| `image_height` | `int` | Fixed at 1080. |
| `image_status` | `enum` | `pending \| ready \| failed`. |
| `regenerations_used` | `int` | Starts at 0; capped at 3 (FR-009). |
| `source_suggestion_id` | `string?` | Optional link to the `PostSuggestion` that seeded this variant. |
| `generation_trace_id` | `string` | LangSmith trace id for the run that produced the current state. |
| `updated_at` | `datetime` | Bumped on every regenerate. |

**Validation rules**:
- A variant is considered `ready` for rendering as soon as EITHER half is
  ready; the other half surfaces as a targeted retry (FR-012).
- `regenerations_used` MUST be rejected at 3 before dispatching a new
  regenerate (FR-009; enforced server-side per research §5).
- `description` regex/check: length 80–250; contains at least one character
  in the Unicode Emoji property set restricted to the approved safe list.

---

### `PostSuggestion`

| Field | Type | Notes |
|---|---|---|
| `id` | `string` | Stable within a request (e.g. `"s-1"`). |
| `text` | `string` | The angle itself. Short (≤140 chars). |
| `finding_ids` | `string[]` | ≥1; references `Finding.id` inside the source brief (FR-002). |
| `low_confidence` | `bool` | True when the brief is thin (spec §Edge Cases). |

---

### `ContentVariantGrid` (ephemeral UI payload)

Emitted via `ephemeral_ui` SSE event (reusing the existing transport).
This is a projection over `ContentGenerationRequest` for rendering; not
persisted separately.

| Field | Type | Notes |
|---|---|---|
| `component` | `"content_variant_grid"` | Discriminator. |
| `request_id` | `ObjectId` | Links back to the request. |
| `variants` | `PostVariant[]` | Exactly what the frontend should render now. |
| `regeneration_caps` | `{A: int, B: int}` | Remaining regenerations for each label. |
| `diversity_warning` | `bool` | Mirror from the request. |

---

### `ContentSuggestionsList` (ephemeral UI payload)

| Field | Type | Notes |
|---|---|---|
| `component` | `"content_suggestions"` | Discriminator. |
| `request_id` | `ObjectId` | Links back. |
| `suggestions` | `PostSuggestion[]` | 2–4 items. |
| `question` | `string` | The consolidated creative-direction question (FR-003). |

---

## Relationships

```
IntelligenceBrief (Stage 1, read-only)
      │
      │  1 ──── *  generation_request_ids
      ▼
ContentGenerationRequest
      │
      ├── 0..4  suggestions:   PostSuggestion
      └── 0..2  variants:      PostVariant
                                   │
                                   └── 0..1  image: key + signed_url
                                               (object storage)
```

Deletion policy: when a brief is deleted (future stage), cascade-delete its
`ContentGenerationRequest` documents and their image objects.

## Indexes (MongoDB)

- `content_generation_requests`: `{brief_id: 1, started_at: -1}` — chat
  rehydration.
- `content_generation_requests`: `{conversation_id: 1, started_at: -1}` —
  list requests across a conversation.
- `content_generation_requests`: `{user_id: 1, status: 1}` — in-flight
  check fallback if Redis is unavailable.

## Schema version / migration

- `schema_version = 1` at launch. Any breaking change bumps the version and
  requires a forward migration per the Development Workflow discipline in
  the Constitution.
