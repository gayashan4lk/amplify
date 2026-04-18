# Implementation Plan: Content Generation (Facebook Post Variants)

**Branch**: `002-content-generation` | **Date**: 2026-04-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-content-generation/spec.md`

## Summary

Stage 2 of Amplify — turn the intelligence brief produced by Stage 1 into two
publish-ready Facebook post variants (description + 1:1 image). A new
**Content Generation Agent** is added as a node in the existing LangGraph
graph, routed to by the Supervisor when the user clicks the "Generate Facebook
content" button inline on a rendered brief. The agent first emits suggested
post angles grounded in specific brief findings, waits for the user's creative
direction reply, then generates two variants in parallel — text via Anthropic
Claude Haiku and images via Google Nano Banana 2 — streaming progress per
sub-step. Variants are persisted per-brief and reattach across sessions;
single-variant regeneration (capped at 3 per variant), partial-failure retry,
copy-description, and download-image complete the loop.

**Technical approach:** Reuse the Stage 1 pattern end-to-end. Add a
`ContentGenerationAgent` LangGraph node, a `ContentGenerationRequest`
MongoDB document (with nested `PostVariant` and `PostSuggestion`), a typed
`<ContentVariantGrid />` ephemeral UI component, and new typed SSE event
subtypes for generation progress. Route text to `claude-haiku-4-5-20251001`
and images to Google Nano Banana 2 through the existing `llm_router`. Images
are stored in object storage (hosting ADR pending — align with
TODO(BACKEND_HOSTING_TARGET)) and referenced by signed URL. Concurrency is
gated by a Redis in-flight lock keyed on brief id. Generation is performed by
an ARQ worker driven from the graph so SSE streaming is not blocked on slow
image calls.

## Technical Context

**Language/Version**:
- Backend: Python 3.13
- Frontend: TypeScript 5.x (Node 20 LTS)

**Primary Dependencies**:
- Frontend: Next.js 16 (App Router), React 19, Tailwind CSS 4, Shadcn/ui,
  Zustand, BetterAuth, Prisma (`@prisma/client`), Zod, Biome, native
  `EventSource`; reuses `stream-renderer.tsx`, `agent-status.tsx`,
  `failure-card.tsx`, and the ephemeral-UI dispatch path established in Stage 1
- Backend: FastAPI, LangGraph, LangChain (`langchain-anthropic`,
  `langchain-google-genai` for Gemini/Nano Banana 2), Pydantic v2, Prisma
  (`prisma-client-py`), Motor, ARQ, `httpx`, LangSmith SDK; reuses the
  existing `llm_router`, `brief_store`, `failures`, `tracing`, and
  `resume_bus` services
- Image pipeline: Google Nano Banana 2 via `google-genai` (or REST) through
  `llm_router`; outputs are persisted as 1080×1080 PNG/JPEG in object storage

**Storage**:
- MongoDB — new `content_generation_requests` collection (nested variants,
  suggestions) and variant-embedded image references; `intelligence_briefs`
  gains a back-reference list of request ids (read-only link, briefs remain
  owned by Stage 1)
- Neon Postgres via Prisma — LangGraph checkpoints, failure records, per-user
  usage counters for the regeneration cap
- Redis — in-flight brief lock (`content_gen:inflight:{brief_id}`), ARQ queue
  for background image generation, short-lived retry/backoff state
- Object storage — generated images (signed-URL retrieval); exact provider
  pinned by the backend-hosting ADR

**Testing**:
- Backend: `pytest` + `pytest-asyncio`; `respx` for Anthropic and Nano Banana 2
  mocking; contract tests for the new SSE subtypes and the
  `ContentGenerationRequest` schema; LangSmith eval suites for variant
  diversity and copy length
- Frontend: Vitest + React Testing Library for `<ContentVariantGrid />` and
  related affordances; Playwright for the end-to-end "click generate → two
  variants rendered" scenario and for regenerate-single-variant
- Schema validation: Pydantic v2 on backend; generated Zod schemas on frontend
  via the same pipeline used in Stage 1; SSE payloads `.safeParse`'d at the
  edge

**Target Platform**: Web, modern evergreen browsers. Backend deployment target
per the outstanding `BACKEND_HOSTING_TARGET` ADR; images stored in a
provider-agnostic object store.

**Project Type**: Web application (Next.js frontend + FastAPI backend in the
existing monorepo per ADR-001).

**Performance Goals**:
- Median run (click → both variants rendered) ≤60s; p95 ≤120s (SC-001)
- First streaming progress event within ≤3s of click
- Text variant (Haiku) draft returned within ≤10s per variant (PRD §10)
- Image variant (Nano Banana 2) returned within ≤20s per variant (PRD §10)
- Ephemeral UI render ≤1s after event arrival

**Constraints**:
- Exactly two variants per run; no user-configurable count
- Description length bounded to 80–250 characters (FR-006)
- Image must be 1080×1080, 1:1 aspect (FR-007)
- Max 3 regenerations per variant per request (FR-009)
- While a run is in-flight for a brief, additional triggers are no-ops (FR-013)
- No hardcoded LLM providers outside `llm_router` (Constitution §Stack)
- Fail-visibly for every partial or total failure (Constitution V; FR-012, FR-014)

**Scale/Scope** (MVP validation phase):
- 10–100 beta users; up to ~10 concurrent generation runs
- Variants and images retained indefinitely alongside their source brief
- English-language copy only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Conversation-First Experience | ✅ | Trigger is an inline button on the brief; suggestions, creative-direction Q&A, progress, and the variant grid all render inside the chat stream. No dashboard-only path. |
| II. Specialist Agents via LangGraph | ✅ | `ContentGenerationAgent` is a new node routed to by the existing Supervisor; no ad-hoc LLM calls outside the graph. LangGraph checkpointer continues to own state. |
| III. Structured State Over Freeform Text | ✅ | `ContentGenerationRequest`, `PostVariant`, `PostSuggestion` are versioned Pydantic models persisted in MongoDB. Descriptions are text-as-payload, not source-of-truth prose. |
| IV. Stream Everything | ✅ | New typed SSE subtypes (`content_suggestions`, `content_variant_progress`, `content_variant_ready`, `content_variant_partial`) emitted through the existing typed protocol. Backward compatible — additive only. |
| V. Fail Visibly, Never Silently | ✅ | Partial failures render as partial variants with targeted retry (FR-012); safety-blocked content surfaces an explanation (FR-014); timeouts emit a terminal `error` event with `recoverable=false` (FR-015). |
| VI. Human-in-the-Loop Before Outreach | ✅ N/A | This feature stops at "user copied description / downloaded image". No publishing, sending, or spend. Stage 3 will introduce the approval gate. |
| VII. Solo-Founder Viable | ✅ | Reuses Neon, MongoDB, Redis, ARQ. Only net-new dependency is an object store for images — justified (images cannot live in Postgres or the MongoDB document payload) and provider-pinned by the existing backend-hosting ADR, not a new service decision. |

**Gate result: PASS.** No violations; Complexity Tracking section is not needed.

Post-Phase-1 re-check: ✅ still passes. The Phase 1 artifacts introduce no new
agents outside LangGraph, no untyped state, and no silent-failure paths; the
object-store dependency is already within the scope of the pending backend
ADR rather than a standalone decision.

## Project Structure

### Documentation (this feature)

```text
specs/002-content-generation/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── sse-events.md                  # New SSE subtypes for content gen
│   ├── rest-endpoints.md              # HTTP endpoints (trigger, regenerate, asset fetch)
│   └── content-generation-request.md  # Pydantic schema contract
└── checklists/
    └── requirements.md  # Spec quality checklist (existing)
```

### Source Code (repository root)

```text
amplify/
├── apps/
│   ├── api/                                       # FastAPI backend (existing)
│   │   ├── agents/
│   │   │   ├── content_generation.py              # NEW: LangGraph node + prompts
│   │   │   ├── graph.py                           # EDIT: wire Supervisor → Content
│   │   │   └── supervisor.py                      # EDIT: route on content-gen intent
│   │   ├── models/
│   │   │   ├── content.py                         # NEW: ContentGenerationRequest, PostVariant, PostSuggestion
│   │   │   └── ephemeral.py                       # EDIT: add ContentVariantGrid payload
│   │   ├── routers/
│   │   │   └── content.py                         # NEW: trigger, regenerate, get-image endpoints
│   │   ├── services/
│   │   │   ├── content_store.py                   # NEW: Motor CRUD for requests/variants
│   │   │   ├── image_store.py                     # NEW: object-storage put/get + signed URLs
│   │   │   ├── inflight_lock.py                   # NEW: Redis per-brief lock
│   │   │   └── llm_router.py                      # EDIT: add Haiku + Nano Banana 2 routes
│   │   ├── sse/
│   │   │   └── events.py                          # EDIT: add content_* event subtypes
│   │   ├── tools/
│   │   │   ├── generate_copy.py                   # NEW: Haiku tool wrapper
│   │   │   └── generate_image.py                  # NEW: Nano Banana 2 tool wrapper
│   │   └── tests/
│   │       ├── contract/test_content_sse.py
│   │       ├── contract/test_content_schema.py
│   │       ├── integration/test_content_flow.py
│   │       └── unit/test_variant_diversity.py
│   └── web/                                       # Next.js frontend (existing)
│       ├── app/(dashboard)/chat/
│       │   └── [conversationId]/page.tsx          # no change; renders new component via dispatcher
│       ├── components/
│       │   ├── chat/stream-renderer.tsx           # EDIT: dispatch content_* events
│       │   └── ephemeral/
│       │       ├── content-variant-grid.tsx       # NEW: two-variant side-by-side
│       │       ├── content-suggestions.tsx        # NEW: suggestion chips
│       │       └── variant-card.tsx               # NEW: single variant (copy/download/regen)
│       ├── lib/
│       │   ├── sse-client.ts                      # EDIT: parse content_* events
│       │   └── schemas/content.ts                 # NEW: generated Zod for content types
│       └── e2e/
│           └── content-generation.spec.ts         # NEW: click-to-variants Playwright
└── specs/002-content-generation/…
```

**Structure Decision**: Extend the existing monorepo. Backend adds one
LangGraph agent, one router, two tools, three services, one Pydantic models
module. Frontend adds three ephemeral components and two lib additions. No
new app, package, or workspace is introduced — per Constitution VII. The
only net-new infrastructure dependency is object storage for generated
images, scoped to the outstanding backend-hosting ADR.

## Complexity Tracking

> No Constitution violations; this section is intentionally empty.
