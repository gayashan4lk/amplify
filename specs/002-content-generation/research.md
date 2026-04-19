# Phase 0 Research: Content Generation

**Feature**: 002-content-generation
**Date**: 2026-04-19

This document resolves the open questions raised by the spec + plan so the
design phase can proceed without NEEDS CLARIFICATION markers.

## 1. Text model routing — Anthropic Haiku

- **Decision**: Use `claude-haiku-4-5-20251001` via the existing `llm_router`
  for both (a) the suggestion step and (b) the per-variant description
  generation. Invoked through `langchain-anthropic`.
- **Rationale**: Haiku 4.5 is the smallest current-gen Anthropic model with
  strong instruction-following and tool-use support, hitting the ≤10s per
  draft target in PRD §10 at a fraction of Sonnet's cost. Haiku's output is
  sufficient for 80–250-char social copy; no reasoning-heavy work is involved.
- **Alternatives considered**:
  - Claude Sonnet 4.6 — higher quality but slower and 5–10× the cost; not
    justified for short-form social copy.
  - OpenAI GPT-4o — already wired in the router for research, but Spec
    Input explicitly names Anthropic Haiku; mixing providers per agent is
    permitted by the constitution as long as the router owns the selection.

## 2. Image model routing — Google Nano Banana 2

- **Decision**: Google Nano Banana 2 (Gemini image generation,
  `gemini-image-…` family) through the `llm_router`, prompted in parallel
  with the Haiku copy step to minimise wall-clock time. Output forced to
  1024×1024 then letterbox-resized to 1080×1080 if the provider cannot emit
  1080 natively; otherwise requested at 1080×1080 directly.
- **Rationale**: Spec Input names Nano Banana 2 explicitly. Its prompt
  adherence and brand-safe defaults are well-suited to marketing creative.
  Parallelising with text keeps the median run inside the 60s SC-001 budget.
- **Alternatives considered**:
  - OpenAI `gpt-image-1` — comparable quality but would break provider
    alignment with the stated spec input.
  - On-device / open models — operational burden; violates Constitution VII.

## 3. Object storage for generated images

- **Decision**: Abstract behind a new `image_store` service with two
  operations: `put(bytes, content_type) -> (key, signed_url)` and
  `sign(key) -> signed_url`. Implement against the object store chosen by
  the outstanding `BACKEND_HOSTING_TARGET` ADR (Fly Volumes + Tigris, Render
  Disks + Cloudflare R2, or AWS S3 depending on final backend host). The
  variant document stores the opaque `key` plus a cached `signed_url` with
  TTL.
- **Rationale**: Images cannot live in the Mongo document payload (size,
  cache-ability, bandwidth) and cannot live in Postgres. Object storage is
  already implicit in the backend-hosting ADR; the only new decision is the
  service abstraction, not a net-new platform choice.
- **Alternatives considered**:
  - Base64 inline in MongoDB — breaks document size limits and wastes
    bandwidth on every read.
  - Serving through the FastAPI app directly — turns the API into a
    bandwidth hot path; signed URLs offload to the CDN/bucket.

## 4. Concurrency gate (in-flight lock)

- **Decision**: Redis `SET NX EX 180` on key
  `content_gen:inflight:{brief_id}` at the start of a run; released on
  terminal state (complete / failed / timeout). The trigger and regenerate
  endpoints both check this lock; a conflict returns `202` with a
  `{"already_running": true}` body and the frontend treats the click as a
  no-op (FR-013).
- **Rationale**: Redis is already on the stack (ARQ + cache). TTL of 180s
  comfortably exceeds the 120s p95 completion bound (SC-001) and auto-heals
  if a worker dies mid-run.
- **Alternatives considered**:
  - Postgres advisory lock — works but couples FastAPI request path to a
    DB round trip that Redis avoids.
  - In-memory lock in a single FastAPI process — breaks as soon as the
    backend scales beyond one instance.

## 5. Regeneration cap enforcement

- **Decision**: Store `regenerations_used` per `PostVariant`; increment on
  each regenerate call before dispatching work. Backend rejects requests
  where `regenerations_used >= 3` with a 409 and a human-readable
  `reason: "regeneration_cap_reached"`. Frontend disables the button after
  the third use and shows the reason inline.
- **Rationale**: Authoritative state lives where the variant lives
  (MongoDB); the frontend is advisory. Cap is enforced server-side so users
  cannot bypass it via the network tab.
- **Alternatives considered**:
  - Redis counter with TTL — simpler but loses the count if Redis evicts;
    MongoDB source-of-truth is durable alongside the variant.

## 6. Variant diversity guarantee

- **Decision**: After both variants are drafted, run a lightweight
  similarity check — cosine similarity of sentence embeddings (reuse the
  existing embeddings provider) on the descriptions AND structural hash
  comparison on the image prompts. If either description similarity > 0.9
  or image-prompt hash collides, regenerate once before rendering; if
  still too similar, render with a low-diversity flag so the user sees
  both but is informed.
- **Rationale**: Meets FR-005 and the edge case of "too similar" without
  making it a hard failure. Keeps the implementation cheap (single extra
  LLM call at worst).
- **Alternatives considered**:
  - Always regenerate both — doubles cost and latency with no guaranteed
    gain.
  - Skip the check entirely — breaks SC-002.

## 7. SSE event strategy

- **Decision**: Add four additive event subtypes to the existing typed
  protocol — `content_suggestions`, `content_variant_progress`,
  `content_variant_ready`, `content_variant_partial`. All existing
  subscribers continue to work (Constitution IV, backward-compatible).
  Errors reuse the existing `error` event with `recoverable` set.
- **Rationale**: Avoids overloading the generic `ephemeral_ui` event for
  progress updates that don't correspond to a full component re-render.
- **Alternatives considered**:
  - Repurpose `tool_call` / `tool_result` — semantically wrong; those are
    for agent-visible tool invocations, not UI progress.
  - Single `content_event` with a discriminator — legal but harder to
    type on the frontend.

## 8. Safety and policy

- **Decision**: Rely on provider-native safety filters (Anthropic for
  text, Google for image); surface any `blocked`/`safety` response as an
  `error` event with `recoverable=true` and a short explanation, per
  FR-014. Add a server-side prefilter that strips obvious policy-violating
  phrasing from the user's direction before the Haiku call, to avoid
  wasting provider budget on guaranteed-refusals.
- **Rationale**: Redundant client-side filtering is a losing game against
  novel phrasings; providers already do this better. The prefilter is a
  cheap cost optimisation, not a safety layer.
- **Alternatives considered**:
  - Full custom moderation pipeline — not justified for v1; would inflate
    scope beyond Stage 2.

## 9. Copy length enforcement

- **Decision**: Constrain Haiku via prompt ("80–250 characters, inclusive")
  AND validate on server. If the model returns outside the window, run one
  silent repair call with a tightened instruction; if still off, truncate
  or pad with a trailing emoji (still within spec) and log a diversity-
  lite warning.
- **Rationale**: Prompt-only control is unreliable for exact bounds;
  deterministic post-check guarantees FR-006 without UI surprises.
- **Alternatives considered**:
  - Reject + surface error — punishes the user for a model quirk; worse UX.

## 10. Persistence & reattachment

- **Decision**: `ContentGenerationRequest` is a top-level MongoDB document
  keyed by `brief_id` + `created_at`; on chat load, the frontend fetches
  any existing requests for the briefs in the conversation and rehydrates
  the inline variant grid. No LangGraph state replay is required.
- **Rationale**: LangGraph checkpoints capture agent run state, not
  product artifacts; artifacts belong in the document store where Stage 1
  briefs already live, so reattachment (FR-016) is trivial.
- **Alternatives considered**:
  - Reconstructing from graph checkpoints — fragile and over-coupled.

---

All NEEDS CLARIFICATION markers resolved. Phase 1 may proceed.
