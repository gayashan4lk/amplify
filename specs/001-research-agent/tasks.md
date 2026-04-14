# Tasks: Research Agent

**Input**: Design documents from `/specs/001-research-agent/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Branch**: `001-research-agent`

**Tests**: Included. The plan (§Technical Context and research.md R-013) establishes a contract-test + fixture-based integration test strategy; this slice's anti-hallucination invariant (research.md R-003, contracts/intelligence-brief.md) cannot be verified without tests. Tests are scoped to contract tests, the anti-hallucination gate, and critical end-to-end paths — not exhaustive unit coverage.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and delivered as an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no cross-task dependencies)
- **[Story]**: `US1`, `US2`, `US3` — maps to user stories in spec.md
- File paths are absolute from repo root

## Path conventions

Monorepo: backend at `apps/api/`, frontend at `apps/web/`, spec docs at `specs/001-research-agent/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up the monorepo skeleton, local infrastructure, and toolchains so every later phase has a working build.

- [X] T001 Create monorepo directory structure per plan.md §Project Structure: `apps/web/`, `apps/api/`, `railway.toml` stub, `README.md` pointing to `specs/001-research-agent/quickstart.md`. Env examples live per-app, not at the root.
- [X] T002 [P] Initialize FastAPI project at `apps/api/` with `pyproject.toml` (Python 3.13) and `uv.lock`; dependencies: `fastapi`, `uvicorn[standard]`, `langgraph`, `langchain-openai`, `langchain-anthropic`, `pydantic>=2`, `prisma` (prisma-client-py), `motor`, `arq`, `tavily-python`, `httpx`, `langsmith`, `redis`; dev deps: `pytest`, `pytest-asyncio`, `respx`, `ruff`
- [X] T003 [P] Initialize Next.js 16 project at `apps/web/` with `pnpm`, TypeScript 5.x, Tailwind CSS 4, Shadcn/ui, Zustand, BetterAuth, `zod`, Prisma (`@prisma/client` + `prisma` CLI), Vitest, Playwright; App Router enabled
- [X] T004 [P] Write `apps/web/example.env` and `apps/api/eample.env` (keep existing filenames) with cloud-free-tier URLs (Neon, MongoDB Atlas, Upstash) and the keys each app needs: web gets `DATABASE_URL`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `FASTAPI_INTERNAL_URL`; api gets `DATABASE_URL`, `MONGODB_URI`, `REDIS_URL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`. Both apps point at the same Neon `DATABASE_URL` in dev.
- [X] T005 [P] Configure Ruff for `apps/api/` and Biome for `apps/web/` (project already uses `@biomejs/biome`); add `format` and `lint` scripts in each app. Do NOT introduce ESLint or Prettier.
- [X] T006 [P] Add GitHub Actions CI workflow at `.github/workflows/ci.yml`: runs backend `pytest`, frontend `vitest`, lint, and type checks; uses fixtures not live APIs

**Checkpoint**: `uv run uvicorn main:app` and `pnpm dev` both start cleanly against the cloud-provisioned dev databases; CI passes on an empty project.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the architectural primitives every user story depends on — auth trust boundary, Prisma schema, Pydantic models, LangGraph graph skeleton, SSE transform, LLM router, shared TS types. Nothing user-visible yet; every user story phase depends on this.

### Schema, data layer, and row-level isolation

- [X] T008 Extend the **canonical** Prisma schema at `apps/web/prisma/schema.prisma` (already owns `User`, `Session`, `Account`, `Verification` for BetterAuth) with models `Conversation`, `Message`, `ResearchRequest`, `FailureRecord` and enums `MessageRole`, `ResearchStatus`, `FailureCode` per data-model.md; include indexes `Conversation(userId, updatedAt desc)` and `Message(conversationId, createdAt)`. Then copy/symlink the schema to `apps/api/db/prisma/schema.prisma` and change only the `generator` block to `prisma-client-py`. The web copy is the source of truth.
- [X] T009 From `apps/web/`, run `pnpm prisma migrate dev --name research_agent_models` (migrations live under `apps/web/prisma/migrations/` and are the canonical migration history). Then from `apps/api/`, run `uv run prisma generate` against the mirrored schema to produce the Python client. The Python side NEVER runs `migrate dev`; it only ever runs `prisma generate` (and `prisma db pull` if drift is suspected). Document the sync rule in `apps/api/db/prisma/README.md`.  *(README written; `migrate dev` + `prisma generate` must be run by the user against a real Neon DB.)*
- [X] T010 [P] Implement `apps/api/services/conversation_store.py` as the ONLY access layer for Postgres (Prisma) entities; every method accepts `user_id` and filters by it — no unfiltered API is exposed
- [X] T011 [P] Implement `apps/api/services/brief_store.py` as the ONLY access layer for the MongoDB `intelligence_briefs` collection; uses Motor; every read/write accepts `user_id` and filters by it; creates indexes `{conversation_id:1, generated_at:-1}` and `{user_id:1, generated_at:-1}` on startup

### Pydantic models (single source of truth for the wire + storage)

- [X] T012 [P] Create `apps/api/models/research.py` defining `SourceAttribution`, `Finding`, `IntelligenceBrief`, `ResearchPlan`, `SubQuery` exactly per contracts/intelligence-brief.md and data-model.md (validation rules included)
- [X] T013 [P] Create `apps/api/models/ephemeral.py` defining `IntelligenceBriefComponent`, `ClarificationPollComponent` and the discriminated union `EphemeralComponent`
- [X] T014 [P] Create `apps/api/models/chat.py` defining `ChatRequest`, `EphemeralResponseRequest`, `ProgressEvent`, `SupervisorDecision`
- [X] T015 [P] Create `apps/api/models/errors.py` defining `FailureCode` enum (mirrors Prisma), `FailureRecord` Pydantic model, and `ApiError` response envelope

### SSE event protocol and shared types

- [X] T016 Create `apps/api/sse/events.py` defining every SSE event type from contracts/sse-events.md as a Pydantic discriminated union (`v: Literal[1]`, `type` discriminator) with the exact field sets documented: `ConversationReady`, `AgentStart`, `AgentEnd`, `ToolCall`, `ToolResult`, `Progress`, `TextDelta`, `EphemeralUI`, `Error`, `Done`
- [X] T017 Implement `apps/api/sse/transform.py` that converts LangGraph `astream_events` v2 output into the typed SSE events from T016; assigns monotonically increasing `id` per stream; includes helper `format_sse_frame(event_id, event) -> str`
- [X] T018 [P] Add `apps/web/scripts/generate-sse-types.ts` (or `datamodel-code-generator` pipeline) that reads the Pydantic schemas and emits **Zod schemas** at `apps/web/lib/types/sse-events.ts`, with inferred TypeScript types (`z.infer<...>`) exported alongside — one discriminated `z.union` per event. Wire it into the Next.js build via a prebuild script so drift is caught at build time. `sse-client.ts` (T047) validates every incoming payload through these Zod schemas.

### Auth trust boundary

- [X] T019 [P] Implement `apps/api/middleware/auth.py` per SAD §6.3: webhook paths exempt, all other requests require `X-User-Id`; attaches to `request.state.user_id`; returns `401` with the error envelope on miss
- [X] T020 [P] Configure BetterAuth in `apps/web/lib/auth-server.ts` and `apps/web/lib/auth.ts` using the Prisma adapter pointed at the shared Neon Postgres; create `apps/web/app/api/auth/[...all]/route.ts` handler
- [X] T021 [P] Implement `apps/web/lib/api-client.ts` — a server-side typed fetch wrapper that calls `FASTAPI_INTERNAL_URL` with `X-User-Id` derived from the authenticated BetterAuth session; MUST only run in Server Components / Server Actions (throw if invoked client-side)

### LangGraph graph skeleton

- [X] T022 Implement `apps/api/services/llm_router.py` with `get_llm(purpose)` supporting `supervisor`, `research_plan`, `research_synthesize`, `ui_schema` per research.md R-009; centralizes model names, temperature, and API keys
- [X] T023 Implement `apps/api/agents/graph.py` defining the LangGraph `StateGraph` with state `{messages, user_id, conversation_id, current_request, brief}`, nodes `supervisor`, `research`, `clarification`, conditional edges per research.md R-001, and `PostgresSaver` checkpointer pointed at the Neon URL (thread_id = conversation_id)  *(InMemorySaver for now; PostgresSaver wiring deferred to T062.)*
- [X] T024 [P] Implement skeleton node stubs `apps/api/agents/supervisor.py`, `apps/api/agents/research.py`, `apps/api/agents/clarification.py` — each returns a "not yet implemented" state update so the graph compiles and runs end-to-end before real logic lands in Phase 3
- [X] T025 [P] Wire LangSmith tracing in `apps/api/main.py` startup: set `LANGSMITH_TRACING=true` and `LANGSMITH_PROJECT` from env; assert the graph is traced

### FastAPI app wiring

- [X] T026 Create `apps/api/main.py`: FastAPI app, CORS for private network only, mounts `middleware/auth.py`, imports routers (stubs for now), startup/shutdown lifecycle for Prisma client, Motor client, Redis pool
- [X] T027 [P] Create `apps/api/config.py`: Pydantic `Settings` class loading all env vars from T004; exposes `RESEARCH_BUDGET_QUERIES=8`, `RESEARCH_BUDGET_SECONDS=60`, `TAVILY_CACHE_TTL_SECONDS=300`, `USER_RESEARCH_RATE_LIMIT_PER_HOUR=10`

### Contract tests (foundational — run in CI against the above scaffolding)

- [X] T028 [P] Add `apps/api/tests/contract/test_sse_events_schema.py` asserting every Pydantic SSE event in T016 matches its JSON Schema documented in contracts/sse-events.md (round-trip serialize/deserialize, required fields, `v==1`)
- [X] T029 [P] Add `apps/api/tests/contract/test_rest_endpoints_schema.py` asserting FastAPI's OpenAPI output for `/api/v1/chat/stream`, `/api/v1/chat/ephemeral`, `/api/v1/conversations`, `/api/v1/conversations/{id}` matches contracts/rest-endpoints.md request/response shapes
- [X] T030 [P] Add `apps/api/tests/contract/test_intelligence_brief_schema.py` asserting valid and invalid `IntelligenceBrief`/`Finding` payloads against the Pydantic validators and invariants 1, 3, 4 from contracts/intelligence-brief.md
- [X] T031 [P] Add `apps/api/tests/unit/test_row_level_isolation.py` asserting `conversation_store` and `brief_store` cannot return data for a different `user_id` (cross-user leakage test)

**Checkpoint**: FastAPI starts, Next.js authenticates via BetterAuth, a signed-in user can hit any stub endpoint and get a typed response. The graph compiles and runs with stub nodes. All contract tests pass. No user-visible research yet.

---

## Phase 3: User Story 1 — Ask a question, receive a structured intelligence brief (P1) 🎯 MVP

**Story goal**: A signed-in user opens `/chat`, asks a well-scoped research question, watches streamed progress, and receives a typed intelligence brief rendered inline with ≥3 findings, confidence labels, and clickable sources.

**Independent test**: Per spec.md §US1 — sign in, send `"What pricing models are top 5 CRM competitors using?"`, observe streamed progress, receive a brief with ≥3 findings each carrying confidence + ≥1 resolvable source URL within ~30s.

### Backend: Research execution (the thing that produces the brief)

- [X] T032 [US1] Implement `apps/api/tools/tavily_search.py`: async wrapper around `tavily-python` with 10s timeout, single retry with backoff, Redis-cached responses (5-min TTL, SHA-256 key per research.md R-010), and a module-level registry of returned URLs per research_request_id used by the anti-hallucination gate
- [X] T033 [US1] Implement `apps/api/agents/supervisor.py` using `llm_router.get_llm("supervisor")` and structured output of `SupervisorDecision` per research.md R-005; returns route ∈ {`research`, `clarification_needed`, `out_of_scope`, `followup_on_existing_brief`}; reads last 10 messages + any current brief as context
- [X] T034 [US1] Implement `apps/api/agents/research.py` per research.md R-003: (1) planning step via `llm_router.get_llm("research_plan")` producing `ResearchPlan` (3–5 `SubQuery`s), (2) parallel Tavily calls capped by `RESEARCH_BUDGET_QUERIES`, (3) synthesis via `llm_router.get_llm("research_synthesize")` producing `IntelligenceBrief`, (4) anti-hallucination gate that drops or rewrites any Finding whose source URLs are not in the Tavily result registry for this request
- [X] T035 [US1] Emit `ProgressEvent` at each phase (`planning`, `searching`, `synthesizing`, `validating`) from `agents/research.py` via the LangGraph event stream so `sse/transform.py` can surface them as `progress` SSE events
- [X] T036 [US1] On successful synthesis, persist the brief via `brief_store.create(...)`, create/update the `ResearchRequest` row with status `complete` and `briefId`, and append an assistant `Message` row with `briefId` set; emit an `ephemeral_ui` event with `component_type: "intelligence_brief"` carrying the full brief
- [X] T037 [US1] Enforce `RESEARCH_BUDGET_SECONDS` via `asyncio.wait_for` around the full research node; on timeout, raise `BudgetExceeded` which is converted to a `budget_exceeded` failure (connected to US3 but scaffolded here)

### Backend: Routing and the main endpoint

- [X] T038 [US1] Implement `apps/api/routers/chat.py::POST /api/v1/chat/stream` per contracts/rest-endpoints.md: creates a new `Conversation` if `conversation_id` is null, appends the user `Message`, invokes `graph.astream_events(..., thread_id=conversation_id)`, runs events through `sse/transform.py`, returns `StreamingResponse` with `X-Accel-Buffering: no`
- [X] T039 [US1] Emit `conversation_ready` as the first event of every stream (with `is_new` flag), followed by balanced `agent_start`/`agent_end` pairs around each LangGraph node invocation, terminating with exactly one `done` or one `error`
- [X] T040 [P] [US1] Implement the per-user research rate limiter in `apps/api/services/rate_limit.py` (Redis INCR with 1-hour TTL); enforced in `chat.py` before invoking the graph; returns `429` + `rate_limited_user` error envelope when exceeded

### Backend: Follow-ups that reference an existing brief (FR-020, FR-021)

- [X] T041 [US1] When `SupervisorDecision.route == "followup_on_existing_brief"`, the graph MUST answer via a plain `text_delta` stream grounded in the already-stored brief (not re-run research); `supervisor.py` loads the most recent brief from `brief_store` for that conversation and passes it as context
- [X] T042 [P] [US1] Implement the clarification sub-node `apps/api/agents/clarification.py`: when the Supervisor decides clarification is needed, emit an `ephemeral_ui` event of type `clarification_poll` with 3–4 LLM-generated options per research.md R-006, then `interrupt` the graph pending user input

### Backend: Ephemeral response endpoint (to resume after clarification)

- [X] T043 [US1] Implement `apps/api/routers/chat.py::POST /api/v1/chat/ephemeral` per contracts/rest-endpoints.md: validates `research_request_id` ownership and state, injects the selected option into the LangGraph state, and resumes the graph from the interrupt point; the open SSE stream receives subsequent events

### Frontend: Chat UI and stream rendering

- [X] T044 [P] [US1] Build `apps/web/app/(dashboard)/layout.tsx` (authenticated shell) and `apps/web/app/(dashboard)/chat/page.tsx` — the primary workspace entry; redirects to `/login` if not authenticated
- [X] T045 [P] [US1] Build `apps/web/app/(dashboard)/chat/[conversationId]/page.tsx` — SSR shell that loads prior messages via `api-client` and hydrates the chat store; opens a fresh SSE stream on new user input
- [X] T046 [P] [US1] Build `apps/web/lib/stores/chat-store.ts` (Zustand): holds the message list, the live stream buffer keyed by `message_id`, and dedup state keyed by SSE `event_id`
- [X] T047 [US1] Build `apps/web/lib/sse-client.ts`: thin wrapper over `EventSource` that (a) reconnects with exponential backoff, (b) sends `Last-Event-ID`, (c) de-dupes by `event_id`, (d) validates every payload with the Zod discriminated union from `lib/types/sse-events.ts` (`.safeParse`) and drops payloads with `v != 1` or failing Zod validation, surfacing a visible toast
- [X] T048 [US1] Build `apps/web/components/chat/message-input.tsx` — Shadcn-based composer; posts via a Server Action that calls `api-client` and then opens the SSE stream from the client
- [X] T049 [US1] Build `apps/web/components/chat/message-list.tsx` and `apps/web/components/chat/stream-renderer.tsx` — stream-renderer switches on `event.type` and renders text deltas, agent status badges, progress lines, and ephemeral components
- [X] T050 [P] [US1] Build `apps/web/components/chat/agent-status.tsx` — compact badge showing the currently active LangGraph node based on the last `agent_start`/`agent_end` pair

### Frontend: Intelligence brief ephemeral component

- [X] T051 [US1] Build `apps/web/components/ephemeral/intelligence-brief.tsx` — renders an `IntelligenceBrief` with: header (scoped question, status label), ordered `Finding` cards with claim + evidence + confidence badge + expandable sources list; each source is a clickable link with source-type icon; unsourced findings show a visible "unsourced" label; contradictions show a visible disagreement indicator per FR-017 and intelligence-brief.md invariant 5
- [X] T052 [P] [US1] Build `apps/web/components/ephemeral/clarification-poll.tsx` — Shadcn button-group poll; single click posts to `POST /api/v1/chat/ephemeral` via a Server Action and optimistically disables the poll

### Tests for User Story 1

- [X] T053 [P] [US1] Add `apps/api/tests/integration/test_happy_path_research.py`: runs the full graph end-to-end with recorded Tavily fixture and fake `ChatModel` replaying stored completions (per research.md R-013); asserts the final brief has `status == "complete"`, ≥3 findings, at least one `confidence == "high"`, and every source URL exists in the Tavily fixture
- [X] T054 [P] [US1] Add `apps/api/tests/integration/test_anti_hallucination_gate.py`: feeds the synthesis LLM a stub that emits a fabricated URL; asserts the gate in `agents/research.py` drops or rewrites that finding and the persisted brief contains zero fabricated URLs (covers SC-004)
- [X] T055 [P] [US1] Add `apps/api/tests/integration/test_followup_reuses_brief.py`: first call creates a brief; second call asks "tell me more about the second finding" and asserts (a) no Tavily calls are made, (b) the response streams `text_delta` events only, (c) the response content references the stored brief
- [X] T056 [P] [US1] Add `apps/api/tests/integration/test_clarification_flow.py`: sends a vague question, asserts a `clarification_poll` `ephemeral_ui` event is emitted, posts to `/chat/ephemeral`, asserts the graph resumes and produces a brief
- [X] T057 [P] [US1] Add `apps/web/tests/e2e/research-happy-path.spec.ts` (Playwright): sign in, open `/chat`, send a scoped question, wait for `<IntelligenceBrief />` to render, assert ≥3 finding cards, assert every source link has a non-empty `href`

**Checkpoint — MVP**: A signed-in user can ask a question and receive a rendered intelligence brief inline. This is the shippable MVP; US2 and US3 harden it.

---

## Phase 4: User Story 2 — Persistence across sessions (P2)

**Story goal**: A returning user reopens Amplify the next day, finds their prior conversation, and re-reads the intelligence brief with all findings and sources intact.

**Independent test**: Per spec.md §US2 — run US1 flow, sign out, sign in on a new browser session, open the conversation list, select the prior conversation, observe the full message history and rendered brief unchanged.

### Backend: Conversation list and detail endpoints

- [X] T058 [US2] Implement `apps/api/routers/conversations.py::GET /api/v1/conversations` per contracts/rest-endpoints.md: cursor paginated, sorted by `updatedAt desc`, filtered by `request.state.user_id`; derives `latest_status` from the last message's state
- [X] T059 [US2] Implement `apps/api/routers/conversations.py::GET /api/v1/conversations/{id}`: returns all messages in order; for every `assistant` message with `briefId`, resolves the full brief via `brief_store.get(brief_id, user_id)` and embeds it; for messages with `failureRecordId`, embeds the failure record
- [X] T060 [P] [US2] Implement `apps/api/routers/conversations.py::DELETE /api/v1/conversations/{id}` (soft delete) setting `archivedAt`; excludes archived rows from the list query
- [X] T061 [US2] Derive and persist `Conversation.title` from the first user message in `routers/chat.py` (truncate to 140 chars); update `updatedAt` on every new message

### Backend: Resume an in-flight research run (FR-024)

- [X] T062 [US2] Ensure `graph.astream_events(..., thread_id=conversation_id)` with `PostgresSaver` is correctly wired so a disconnected client reconnecting to the same `conversation_id` resumes from the last checkpoint; expose a GET variant of `/chat/stream` or a reconnection query param if required by `sse-client.ts`
- [X] T063 [US2] Persist every streamed event's summary into `Message.progressEvents` (append on each event) so a reload of the conversation renders the same progress trail that was seen live

### Frontend: Conversation list and reload behavior

- [X] T064 [P] [US2] Build `apps/web/app/(dashboard)/conversations/page.tsx` — SSR-fetched paginated list of prior conversations, each linking to `/chat/[id]`; shows title, updated-at, and latest-status badge
- [X] T065 [P] [US2] Extend `apps/web/app/(dashboard)/chat/[conversationId]/page.tsx` to SSR-hydrate the Zustand chat store from the `GET /conversations/{id}` response, including any embedded briefs, so the rendered message list on reload is byte-for-byte what the user saw live
- [X] T066 [P] [US2] Update `apps/web/lib/sse-client.ts` to resume an in-flight stream on conversation reload if `latest_status == "pending"`; otherwise render the stored final state only

### Tests for User Story 2

- [X] T067 [P] [US2] Add `apps/api/tests/integration/test_conversation_persistence.py`: complete a research run, close the Prisma client, reopen, fetch `/conversations/{id}`, assert all messages + the full brief render identically
- [X] T068 [P] [US2] Add `apps/api/tests/integration/test_resume_inflight.py`: start a research run, kill the stream mid-way, reconnect to the same `thread_id`, assert the graph resumes from the last checkpoint and produces a brief (or current progress) — never a lost state
- [X] T069 [P] [US2] Add `apps/web/tests/e2e/persistence.spec.ts` (Playwright): happy path, sign out, sign in, open the prior conversation, assert the `<IntelligenceBrief />` renders with the same findings

**Checkpoint**: Conversations and briefs survive sign-out and reload; in-flight research resumes cleanly.

---

## Phase 5: User Story 3 — Visible failure, never silent (P2)

**Story goal**: Every research failure produces a specific, actionable, in-conversation message. Zero silent failures, zero fabricated briefs, zero generic "something went wrong" responses.

**Independent test**: Per spec.md §US3 — inject a failure at each documented failure point (Tavily unreachable, LLM error, no findings above threshold, user cancel, budget exceeded, rate limited) and verify that in every case the user sees a specific, actionable message, and every failure is persisted so the conversation replays correctly.

### Backend: Failure taxonomy and persistence

- [ ] T070 [US3] Implement `apps/api/services/failures.py` exposing `record_failure(user_id, conversation_id, code, user_message, suggested_action, trace_id) -> FailureRecord`; persists via Prisma and returns a Pydantic model ready for SSE emission
- [ ] T071 [US3] Catch each failure case in `apps/api/agents/research.py` and `apps/api/routers/chat.py` and route to `record_failure` with the correct `FailureCode`: `tavily_unavailable`, `tavily_rate_limited`, `llm_unavailable`, `llm_invalid_output`, `no_findings_above_threshold`, `budget_exceeded`, `user_cancelled`, `rate_limited_user`
- [ ] T072 [US3] In `apps/api/sse/transform.py`, ensure every caught failure is emitted as exactly one `error` SSE event with `recoverable`, `message`, `suggested_action`, and `failure_record_id`; on an `error`, the stream terminates WITHOUT a subsequent `done` per contracts/sse-events.md sequencing rules
- [ ] T073 [US3] Enforce Constitution V invariant in `record_failure`: reject empty or generic `user_message` at runtime (raise in dev, log-and-substitute an explicit "no-op failure of X" message in prod) so no silent/generic message can reach the user
- [ ] T074 [P] [US3] Enforce the no-findings-above-threshold path in `agents/research.py`: when the anti-hallucination gate leaves zero qualifying findings, do NOT persist a brief; emit `no_findings_above_threshold` failure with a rephrase suggestion (covers FR-027)
- [ ] T075 [P] [US3] Enforce paywalled/blocked source disclosure: when the Tavily tool marks a result as `accessible == False`, surface this in the parent `Finding.notes` and keep the source cited per FR-028 and intelligence-brief.md invariant 6

### Frontend: Failure rendering

- [ ] T076 [P] [US3] Build `apps/web/components/chat/failure-card.tsx` — renders an `error` SSE event as a distinct in-conversation card with the failure message, a "Retry" button (only when `recoverable`), and the `suggested_action` text; "Retry" re-posts the original user message
- [ ] T077 [P] [US3] Extend `apps/web/components/chat/stream-renderer.tsx` to route `error` events to `<FailureCard />`; extend the conversation reload path to render persisted failure records identically

### Tests for User Story 3 (the full failure matrix — critical for SC-006)

- [ ] T078 [P] [US3] Add `apps/api/tests/integration/test_failure_tavily_unavailable.py`: Tavily fixture returns 503; asserts a single `error` event with `code=tavily_unavailable, recoverable=true`, a non-empty `suggested_action`, and a persisted `FailureRecord`
- [ ] T079 [P] [US3] Add `apps/api/tests/integration/test_failure_llm_invalid_output.py`: LLM fake returns unparseable JSON thrice; asserts a single `error` event with `code=llm_invalid_output, recoverable=false`
- [ ] T080 [P] [US3] Add `apps/api/tests/integration/test_failure_no_findings.py`: Tavily fixture returns empty/irrelevant results; asserts `no_findings_above_threshold` error — and crucially, that no `IntelligenceBrief` document is written to MongoDB
- [ ] T081 [P] [US3] Add `apps/api/tests/integration/test_failure_budget_exceeded.py`: config override drops `RESEARCH_BUDGET_SECONDS` to 1; asserts `budget_exceeded` error
- [ ] T082 [P] [US3] Add `apps/api/tests/integration/test_failure_rate_limited.py`: 11 back-to-back research requests from one user; asserts the 11th returns `429` with `rate_limited_user`
- [ ] T083 [P] [US3] Add `apps/api/tests/unit/test_zero_silent_failures.py`: parametrized over every `FailureCode`, asserts `record_failure` rejects empty/generic `user_message` strings
- [ ] T084 [P] [US3] Add `apps/web/tests/e2e/failure-visibility.spec.ts` (Playwright): intercepts the SSE stream to inject a `tavily_unavailable` error event, asserts the `<FailureCard />` renders with the correct message, the Retry button is visible, and clicking Retry re-submits the original question

**Checkpoint**: Every failure path is observable, specific, and persistent. SC-006 (100% of failures surface an actionable message; zero silent failures) is testable and enforced.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Harden the slice, finalize observability, and prepare for deployment.

- [ ] T085 [P] Wire LangSmith trace id into every Pydantic model that reaches the frontend (`IntelligenceBrief.trace_id`, `FailureRecord.traceId`) and render a small dev-only "view trace" link on finding cards and failure cards when `NODE_ENV !== "production"`
- [ ] T086 [P] Add `apps/api/tests/unit/test_source_confidence_rules.py` covering intelligence-brief.md invariant 3 (high-confidence requires 2+ sources OR 1 strong source type) across a parametrized matrix
- [ ] T087 [P] Add a nightly LangSmith eval job config (docs only for now, no CI wiring) that runs a hand-curated set of 10 research questions and scores each brief against: zero fabricated sources, ≥3 findings, at least one high-confidence finding (per research.md R-013)
- [ ] T088 Add a Railway deployment config at `railway.toml` covering two services (`web` for `apps/web`, `api` for `apps/api`) with the API listening only on Railway's private network per ADR-006 / Constitution Technology & Security Constraints
- [ ] T089 [P] Update `README.md` at repo root with a short summary and a link to `specs/001-research-agent/quickstart.md`
- [ ] T090 [P] Run the full quickstart.md walkthrough manually on a clean clone and fix any gap between the quickstart and the actual setup; sign off when happy-path, clarification-path, and all failure paths work end-to-end

---

## Dependencies

**Phase dependencies:**
- Phase 1 (Setup) → unlocks everything
- Phase 2 (Foundational) → unlocks all user story phases
- Phase 3 (US1) → MVP; unblocks Phase 4 and Phase 5
- Phase 4 (US2) → depends only on Phase 3 for end-to-end verification
- Phase 5 (US3) → depends on Phase 3; parallelizable with Phase 4
- Phase 6 (Polish) → after all user stories

**Story independence:**
- US1 is the MVP and MUST ship first.
- US2 and US3 can be worked on in parallel after US1 is in.

## Parallel execution opportunities

**Within Phase 1**: T002, T003, T004, T005, T006 can all run in parallel after T001.

**Within Phase 2**:
- Pydantic model files T012, T013, T014, T015 → all in parallel.
- Store layer T010, T011 → parallel after T008/T009.
- Auth boundary T019, T020, T021 → parallel.
- Graph stub nodes T024, T025 → parallel after T022, T023.
- Contract tests T028, T029, T030, T031 → all in parallel, block nothing in the same phase.

**Within Phase 3 (US1)**:
- Frontend T044, T045, T046, T050, T052 → parallel with each other.
- Backend T032 (Tavily tool) can start before T034 (research node consumes it).
- US1 tests T053–T057 → all parallel after the implementation tasks they cover.

**Within Phase 5 (US3)**: All failure-path tests T078–T084 are in separate files and run in parallel.

## Implementation strategy

**Recommended path for the solo founder:**

1. **Ship US1 first (MVP).** Run Phase 1 → Phase 2 → Phase 3. Stop. Use it yourself for a week. This is the smallest thing that proves the architecture.
2. **Add US3 next** (not US2). Visible failure handling is a safety property of the MVP; shipping US1 without US3 means the first real outage looks like a bug in the product rather than a known failure path. US3 is smaller than US2 and compounds more.
3. **Then US2.** Persistence across sessions is the "come back tomorrow" property; by now there's real data to persist.
4. **Polish (Phase 6)** only once the slice has survived a week of self-use.

Task count: 90 total — Setup: 7, Foundational: 24, US1: 26, US2: 12, US3: 15, Polish: 6.
