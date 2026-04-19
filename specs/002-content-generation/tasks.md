---
description: "Task list for 002-content-generation"
---

# Tasks: Content Generation (Facebook Post Variants)

**Input**: Design documents from `/specs/002-content-generation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — the plan's Testing section and quickstart explicitly require contract tests (SSE + schema), integration tests, unit tests (variant diversity), and Playwright E2E.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Paths assume the monorepo structure from plan.md (`apps/api/`, `apps/web/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding, env, feature flag, and dependency wiring shared by every user story.

- [X] T001 Add `CONTENT_GEN_ENABLED` feature flag plus `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `IMAGE_STORE_BUCKET`, `IMAGE_STORE_REGION` to backend config loader in apps/api/config/settings.py and document required env in apps/api/.env.example
- [X] T002 [P] Add `langchain-anthropic` and `google-genai` (or `langchain-google-genai`) to apps/api/pyproject.toml and lock with uv
- [X] T003 [P] Add object-storage SDK dependency (boto3 / s3-compatible client per pending backend-hosting ADR) to apps/api/pyproject.toml and lock with uv
- [X] T004 [P] Scaffold empty module files so later tasks can land without import errors: apps/api/agents/content_generation.py, apps/api/routers/content.py, apps/api/services/content_store.py, apps/api/services/image_store.py, apps/api/services/inflight_lock.py, apps/api/tools/generate_copy.py, apps/api/tools/generate_image.py, apps/api/models/content.py
- [X] T005 [P] Scaffold frontend module files: apps/web/components/ephemeral/content-variant-grid.tsx, apps/web/components/ephemeral/content-suggestions.tsx, apps/web/components/ephemeral/variant-card.tsx, apps/web/lib/schemas/content.ts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schemas, routing, storage, and SSE primitives that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 [P] Define Pydantic v2 models `ContentGenerationRequest`, `PostVariant`, `PostSuggestion`, status enums, and `schema_version=1` with validators (length 80–250, emoji-in-description check, regenerations_used cap, variants ≤2, suggestions 2–4) in apps/api/models/content.py
- [X] T007 [P] Extend `EphemeralComponent` union with `ContentVariantGrid` and `ContentSuggestionsList` payload models in apps/api/models/ephemeral.py
- [X] T008 [P] Add new SSE event subtypes `content_suggestions`, `content_variant_progress`, `content_variant_ready`, `content_variant_partial` with Pydantic payload models and typed envelope registration in apps/api/sse/events.py
- [X] T009 [P] Implement Redis in-flight lock service (`acquire(brief_id, ttl=180)`, `release(brief_id)`, `is_locked(brief_id)`) using `SET NX EX` on key `content_gen:inflight:{brief_id}` in apps/api/services/inflight_lock.py
- [X] T010 [P] Implement `image_store` service with `put(bytes, content_type) -> (key, signed_url)`, `sign(key) -> signed_url`, and TTL-aware cache in apps/api/services/image_store.py
- [X] T011 Implement `content_store` service with Motor CRUD for `content_generation_requests` (create, get, list_by_brief, list_by_conversation, update_status, upsert_variant, increment_regenerations_used) and create MongoDB indexes `{brief_id, started_at:-1}`, `{conversation_id, started_at:-1}`, `{user_id, status}` in apps/api/services/content_store.py (depends on T006)
- [X] T012 Extend `llm_router` with a `claude-haiku-4-5-20251001` text route and a `gemini` Nano Banana 2 image route (1080×1080 requested, letterbox fallback) in apps/api/services/llm_router.py (depends on T002)
- [X] T013 Add `content_gen_blocked` and `content_gen_timeout` failure codes plus helper for writing `FailureRecord` rows tied to a `request_id` in apps/api/services/failures.py
- [X] T014 Register the new `/api/v1/content` router in FastAPI app bootstrap in apps/api/main.py (depends on T004)
- [X] T015 [P] Extend Pydantic → Zod generator config and run it to produce apps/web/lib/schemas/content.ts from the new models (depends on T006, T007, T008)
- [X] T016 [P] Extend SSE client parsing to discriminate `content_suggestions` / `content_variant_progress` / `content_variant_ready` / `content_variant_partial` via `.safeParse` against generated Zod in apps/web/lib/sse-client.ts (depends on T015)
- [X] T017 [P] Extend `<StreamRenderer />` dispatcher to route content_* events and new `ephemeral_ui` component discriminators (`content_suggestions`, `content_variant_grid`) to the ephemeral UI layer in apps/web/components/chat/stream-renderer.tsx (depends on T016)

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Generate two Facebook post variants from a brief (Priority: P1) 🎯 MVP

**Goal**: From a rendered intelligence brief, one click produces 2–4 grounded suggestions, a consolidated creative-direction question, then two distinct Facebook post variants (description + 1080×1080 image) rendered side-by-side inline in chat, with streaming progress.

**Independent Test**: Seeded user with a completed brief clicks **Generate Facebook content**, sees suggestions referencing finding ids within 10s, submits direction in chat, and within 120s sees two variants with descriptions in [80,250] chars, ≥1 emoji each, and images at 1080×1080.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T018 [P] [US1] Contract test for `POST /api/v1/content/generate` (200, 202 already_running, 404, 409 incomplete-brief) in apps/api/tests/contract/test_content_endpoints.py
- [ ] T019 [P] [US1] Contract test for `GET /api/v1/content/{request_id}` and `GET /api/v1/briefs/{brief_id}/content-requests` rehydration in apps/api/tests/contract/test_content_rehydrate.py
- [ ] T020 [P] [US1] Contract test for SSE subtypes ordering (`content_suggestions` → `content_variant_progress` → `content_variant_ready`) and envelope shape in apps/api/tests/contract/test_content_sse.py
- [ ] T021 [P] [US1] Contract test for `ContentGenerationRequest` schema (status machine, variant length bounds, suggestion bounds, schema_version) in apps/api/tests/contract/test_content_schema.py
- [X] T022 [P] [US1] Unit test for variant diversity checker (embedding-cosine > 0.9 triggers one retry, emits `diversity_warning` when still too similar) in apps/api/tests/unit/test_variant_diversity.py
- [X] T023 [P] [US1] Unit test for copy-length repair (out-of-band → silent repair → truncate/pad branch) in apps/api/tests/unit/test_copy_length.py
- [ ] T024 [P] [US1] Integration test for full flow with `respx`-mocked Anthropic + Nano Banana 2: trigger → suggestions → direction reply → two variants ready in apps/api/tests/integration/test_content_flow.py
- [ ] T025 [P] [US1] Vitest component test for `<ContentVariantGrid />` rendering two labeled variants with progress states in apps/web/components/ephemeral/__tests__/content-variant-grid.test.tsx
- [ ] T026 [P] [US1] Playwright E2E: click generate → suggestions render → reply → two variants render with correct dimensions and length bounds in apps/web/e2e/content-generation.spec.ts

### Implementation for User Story 1

- [X] T027 [P] [US1] Implement `generate_copy` tool wrapping Haiku through `llm_router`, with prompt enforcing 80–250 chars + ≥1 emoji from the conservative-render set, in apps/api/tools/generate_copy.py (depends on T012)
- [X] T028 [P] [US1] Implement `generate_image` tool wrapping Nano Banana 2 through `llm_router`, enforcing 1080×1080 (or letterbox), persisting bytes via `image_store.put`, returning `(image_key, signed_url)` in apps/api/tools/generate_image.py (depends on T010, T012)
- [X] T029 [US1] Implement ARQ worker tasks `produce_variant(request_id, label)` that run copy + image in parallel via `asyncio.gather`, persist partial progress, emit `content_variant_progress`/`partial`/`ready` events, in apps/api/workers/content_tasks.py (depends on T027, T028, T011, T008)
- [X] T030 [US1] Implement `ContentGenerationAgent` LangGraph node: suggestion step (Haiku with brief findings → 2–4 `PostSuggestion`), wait-for-user-direction via `resume_bus`, diversity gate, dispatch of two parallel `produce_variant` ARQ jobs, terminal completion, in apps/api/agents/content_generation.py (depends on T011, T012, T029)
- [X] T031 [US1] Wire Supervisor intent routing so a "generate content" intent (triggered by the REST endpoint) routes to `ContentGenerationAgent`, in apps/api/agents/supervisor.py and apps/api/agents/graph.py (depends on T030)
- [X] T032 [US1] Implement `POST /api/v1/content/generate`: brief-ownership + completeness check, in-flight-lock acquire, persist `ContentGenerationRequest` in `suggesting`, kick off graph run, return `{request_id, sse_endpoint}` (200) or `202 already_running`, in apps/api/routers/content.py (depends on T009, T011, T031)
- [X] T033 [US1] Implement `GET /api/v1/content/{request_id}` and `GET /api/v1/briefs/{brief_id}/content-requests` for chat rehydration, in apps/api/routers/content.py (depends on T011)
- [X] T034 [US1] Implement `GET /api/v1/content/image/{image_key}` signed-URL refresh endpoint, in apps/api/routers/content.py (depends on T010)
- [X] T035 [US1] Add read-only `generation_request_ids` back-reference append on the `intelligence_briefs` document whenever a new request is created, in apps/api/services/brief_store.py
- [X] T036 [P] [US1] Implement `<ContentSuggestionsList />` ephemeral component rendering 2–4 suggestions with finding-id pills and the consolidated question, in apps/web/components/ephemeral/content-suggestions.tsx (depends on T015)
- [X] T037 [P] [US1] Implement `<VariantCard />` rendering description, 1:1 image, per-half status badges (ready/pending/failed), and progress label, in apps/web/components/ephemeral/variant-card.tsx (depends on T015)
- [X] T038 [US1] Implement `<ContentVariantGrid />` composing two `<VariantCard />` side-by-side with diversity-warning banner, in apps/web/components/ephemeral/content-variant-grid.tsx (depends on T037)
- [X] T039 [US1] Add "Generate Facebook content" button to the rendered brief card that calls `POST /api/v1/content/generate` (disabled while a run is in-flight or the brief has no findings), in apps/web/components/chat/brief-card.tsx
- [X] T040 [US1] Add chat-load rehydration: fetch `/api/v1/briefs/{brief_id}/content-requests` for each rendered brief and re-emit `content_variant_grid` ephemeral events locally, in apps/web/components/chat/conversation-loader.tsx (depends on T033, T038)

**Checkpoint**: User Story 1 is fully functional — two variants generated from a brief, streamed, and persisted across reloads.

---

## Phase 4: User Story 2 - Regenerate or refine a variant (Priority: P2)

**Goal**: User can regenerate a single variant (A or B) independently, optionally with plain-language guidance, capped at 3 per variant per request, without disturbing the other variant.

**Independent Test**: With two variants rendered, trigger regenerate on A with and without guidance — A's description + image are replaced, B is unchanged, and after the 3rd regenerate the button is disabled with "no regenerations left".

### Tests for User Story 2

- [ ] T041 [P] [US2] Contract test for `POST /api/v1/content/{request_id}/regenerate` (200 with incremented counter, 202 already_running, 409 cap reached, 404) in apps/api/tests/contract/test_content_regenerate.py
- [ ] T042 [P] [US2] Integration test: regenerate A with guidance → new variant reflects guidance and only A mutates in apps/api/tests/integration/test_regenerate_flow.py
- [ ] T043 [P] [US2] Vitest component test for regenerate affordance on `<VariantCard />` respecting remaining cap, in apps/web/components/ephemeral/__tests__/variant-card-regenerate.test.tsx
- [ ] T044 [P] [US2] Playwright E2E: regenerate A once, then hit cap after 3 tries, in apps/web/e2e/content-regenerate.spec.ts

### Implementation for User Story 2

- [X] T045 [US2] Implement `POST /api/v1/content/{request_id}/regenerate`: validate label, check cap via `regenerations_used`, acquire in-flight lock, atomically increment counter in `content_store`, enqueue single-variant ARQ job, return `{regenerations_used}` or 409 `regeneration_cap_reached`, in apps/api/routers/content.py (depends on T011, T029)
- [X] T046 [US2] Extend `produce_variant` ARQ task to accept `additional_guidance` and reuse it in the Haiku prompt + image prompt for the target variant only, in apps/api/workers/content_tasks.py
- [X] T047 [US2] Add regenerate button + optional guidance textbox to `<VariantCard />`, disabled when `regeneration_caps[label] == 0`, with server-returned remaining count updating UI state, in apps/web/components/ephemeral/variant-card.tsx (depends on T037)
- [X] T048 [US2] Propagate updated regeneration caps from `ContentVariantGrid` payload through ephemeral event handling in apps/web/components/chat/stream-renderer.tsx

**Checkpoint**: User Stories 1 AND 2 work independently — users can iterate on individual variants.

---

## Phase 5: User Story 3 - Copy a variant out of the app (Priority: P3)

**Goal**: One-click copy of the full description (with emojis) to the clipboard and one-click download of the image in a Facebook-accepted format.

**Independent Test**: For a rendered variant, `copy description` places the full description on the clipboard verbatim, and `download image` saves a 1080×1080 PNG/JPEG locally.

### Tests for User Story 3

- [ ] T049 [P] [US3] Vitest test for copy-to-clipboard (mocked `navigator.clipboard.writeText`) on `<VariantCard />`, in apps/web/components/ephemeral/__tests__/variant-card-copy.test.tsx
- [ ] T050 [P] [US3] Playwright E2E: copy description asserts clipboard contents; download image asserts a saved file with correct mime + dimensions, in apps/web/e2e/content-export.spec.ts

### Implementation for User Story 3

- [X] T051 [US3] Add `copy description` action using `navigator.clipboard.writeText` on `<VariantCard />`, in apps/web/components/ephemeral/variant-card.tsx
- [X] T052 [US3] Add `download image` action that fetches the signed URL (refreshing via `GET /api/v1/content/image/{image_key}` on 403) and triggers a browser download with `<a download>`, in apps/web/components/ephemeral/variant-card.tsx
- [X] T053 [US3] Ensure `image_store` PUT sets `Content-Disposition: attachment; filename=variant-{label}-{request_id}.png` on signed URLs (or maps via response-content-disposition override), in apps/api/services/image_store.py

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Cross-Cutting — Partial failure + safety + timeout (spans FR-012, FR-014, FR-015)

**Purpose**: The visibility-of-failure behaviors called out across multiple stories. Implemented once but exercised by US1/US2.

- [ ] T054 [P] Contract test for `POST /api/v1/content/{request_id}/retry-half` (200 queued, 409 not-partial) in apps/api/tests/contract/test_content_retry_half.py
- [ ] T055 [P] Integration test: image-half failure emits `content_variant_partial` with `retry_target: "image"` and the retry-half endpoint recovers it without bumping `regenerations_used`, in apps/api/tests/integration/test_partial_failure.py
- [ ] T056 [P] Integration test: provider safety block emits `error` event with `recoverable: true`, `code: "content_safety_blocked"`, no variant rendered, in apps/api/tests/integration/test_safety_block.py
- [ ] T057 [P] Integration test: whole-run 180s timeout emits terminal `error` with `recoverable: false`, `code: "content_gen_timeout"`, and releases the in-flight lock, in apps/api/tests/integration/test_run_timeout.py
- [X] T058 Implement `POST /api/v1/content/{request_id}/retry-half` dispatching only the failing half (description OR image) without counter increment, in apps/api/routers/content.py (depends on T029)
- [X] T059 Implement partial-failure path in `produce_variant`: on half-failure, emit `content_variant_partial` with `retry_target`, persist `description_status`/`image_status`, do NOT mark the variant failed, in apps/api/workers/content_tasks.py
- [X] T060 Implement provider-safety detection (Anthropic `stop_reason: "refusal"`, Google safety categories) in tools and surface `error` event with `code: "content_safety_blocked"`, in apps/api/tools/generate_copy.py and apps/api/tools/generate_image.py
- [X] T061 Implement whole-run timeout (180s wall-clock) in `ContentGenerationAgent`: emit terminal `error` with `code: "content_gen_timeout"`, release in-flight lock, write `FailureRecord`, in apps/api/agents/content_generation.py (depends on T030, T013)
- [X] T062 Implement targeted retry UI: when a `<VariantCard />` has `description_status == "failed"` or `image_status == "failed"`, render a small "Retry image/description" button that calls `/retry-half`, in apps/web/components/ephemeral/variant-card.tsx

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T063 [P] Add LangSmith trace annotations at Supervisor → Content transition and on every regeneration/retry-half dispatch, in apps/api/agents/content_generation.py and apps/api/workers/content_tasks.py
- [ ] T064 [P] Add structured logs (request_id, variant_label, step, latency_ms) for every Haiku and Nano Banana 2 call in tools, in apps/api/tools/generate_copy.py and apps/api/tools/generate_image.py
- [ ] T065 [P] Add LangSmith eval suite for variant diversity (SC-002) and copy-length-in-band (FR-006) in apps/api/evals/content_generation_evals.py
- [ ] T066 [P] Document env vars, feature flag, and rollout notes from quickstart.md in apps/api/README.md and apps/web/README.md
- [ ] T067 Run `apps/api` and `apps/web` linters (ruff, biome) and fix; run mypy/tsc with zero errors
- [ ] T068 Execute quickstart.md §"Happy-path smoke test" end-to-end against a local dev environment and record timing against SC-001 (median ≤60s, p95 ≤120s)
- [ ] T069 Verify FR-013 concurrency: fire two `generate` requests in quick succession via a script and assert exactly one run completes and the other gets `202 already_running`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. Blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational; reuses US1 variant path (T029) but is testable on its own seeded state.
- **User Story 3 (Phase 5)**: Depends on Foundational; consumes a rendered variant (can be seeded).
- **Cross-Cutting (Phase 6)**: Depends on Foundational; naturally lands after US1 since it extends the variant path.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Independent. Delivers the MVP.
- **US2 (P2)**: Independent from US3. Integrates with US1's variant pipeline.
- **US3 (P3)**: Independent. Operates on any rendered variant.

### Within Each User Story

- Tests written and failing before implementation.
- Models → services → tools → agent/worker → router → UI.
- Backend contract before frontend wiring.

### Parallel Opportunities

- All Setup [P] tasks parallel.
- All Foundational [P] tasks parallel (T006–T010, T015–T017 after their deps).
- Across stories: once Foundational done, US1, US2, US3 can run in parallel by different developers.
- Within US1: T018–T026 (tests) all parallel; T027 + T028 (tools) parallel; T036 + T037 (UI primitives) parallel.
- Cross-cutting tests T054–T057 parallel.

---

## Parallel Example: User Story 1

```bash
# Launch US1 test tasks in parallel:
Task: "Contract test generate endpoint in apps/api/tests/contract/test_content_endpoints.py"
Task: "Contract test rehydration in apps/api/tests/contract/test_content_rehydrate.py"
Task: "Contract test SSE in apps/api/tests/contract/test_content_sse.py"
Task: "Contract test schema in apps/api/tests/contract/test_content_schema.py"
Task: "Unit test diversity in apps/api/tests/unit/test_variant_diversity.py"
Task: "Unit test copy-length in apps/api/tests/unit/test_copy_length.py"
Task: "Integration test full flow in apps/api/tests/integration/test_content_flow.py"
Task: "Vitest ContentVariantGrid in apps/web/components/ephemeral/__tests__/content-variant-grid.test.tsx"
Task: "Playwright E2E in apps/web/e2e/content-generation.spec.ts"

# Launch US1 tools in parallel:
Task: "generate_copy tool in apps/api/tools/generate_copy.py"
Task: "generate_image tool in apps/api/tools/generate_image.py"

# Launch US1 UI primitives in parallel:
Task: "ContentSuggestionsList in apps/web/components/ephemeral/content-suggestions.tsx"
Task: "VariantCard in apps/web/components/ephemeral/variant-card.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (blocks everything).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run the quickstart.md smoke test.
5. Demo — one click → two variants inline.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → MVP ship.
3. Cross-Cutting (Phase 6) → make failure modes visible in the MVP.
4. US2 → regeneration loop.
5. US3 → copy/download polish.
6. Polish (Phase 7) → observability, evals, rollout.

### Parallel Team Strategy

Once Foundational is done:
- Dev A: US1 (P1) — owns the end-to-end path.
- Dev B: US2 (P2) — regenerate endpoint + UI, stub variant pipeline if US1 not yet merged.
- Dev C: US3 (P3) — copy/download actions against seeded variants.
- Dev D: Phase 6 cross-cutting failure paths, after US1's variant pipeline lands.

---

## Notes

- [P] = different files, no dependencies on incomplete tasks.
- [Story] maps tasks to user-story traceability.
- Tests are required per plan.md Testing section — write them first and confirm they fail before implementation.
- Commit after each task or logical group.
- Every generated variant MUST pass FR-006 (80–250 chars + emoji) and FR-007 (1080×1080) before `content_variant_ready` is emitted — enforce server-side, never trust the provider.
- Partial variants (FR-012) are a first-class render state, not an error; the `error` event is reserved for safety blocks (FR-014) and timeouts (FR-015).
