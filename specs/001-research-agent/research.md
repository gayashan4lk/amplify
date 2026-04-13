# Phase 0: Research — Research Agent

**Feature**: 001-research-agent
**Date**: 2026-04-13

This document consolidates the technical decisions required to build the
Research Agent slice. All decisions are grounded in the existing PRD, SAD, and
ADRs; this phase resolves the remaining open questions specific to the first
slice so Phase 1 can proceed without ambiguity.

---

## R-001: LangGraph graph shape for a single-stage slice

**Decision**: A two-node LangGraph graph with a Postgres checkpointer:
`START → supervisor → research → END`, plus a conditional edge `supervisor →
END` for non-research messages (small talk, out-of-scope), and a conditional
edge `supervisor → clarification → END` for vague questions that need
narrowing. State is a `TypedDict` containing `messages`, `user_id`,
`conversation_id`, `current_request`, and `brief`.

**Rationale**: The full Supervisor multi-agent graph from SAD §7 is overkill
for a single-stage slice, but we must not build a one-off that later has to be
torn down. Keeping the Supervisor node from day one means adding Content,
Outreach, Feedback nodes in later specs is pure addition, not refactor. The
Supervisor-as-router pattern is explicitly called out in Constitution II.

**Alternatives considered**:
- *Direct Research node (no Supervisor)* — rejected because it would violate
  Constitution II and create refactor debt in the next spec.
- *Full five-agent graph with stubs* — rejected because stubbed agents are
  dead code until their specs exist, and stubs drift.

---

## R-002: LangGraph checkpointer backend

**Decision**: Use LangGraph's `PostgresSaver` (from `langgraph.checkpoint.postgres`)
pointed at the same Neon Postgres instance Prisma uses, on a dedicated
`langgraph_checkpoints` table managed by LangGraph itself (not Prisma).

**Rationale**: Satisfies FR-024 (resumption after disconnect) and Constitution
principle about no custom state serialisation. Reusing Neon avoids adding a new
datastore. LangGraph owns the schema for its own tables; Prisma owns the rest —
no conflict because the tables are disjoint.

**Alternatives considered**:
- *Redis checkpointer* — faster but volatile. Risks losing in-flight research on
  Redis eviction or restart, which conflicts with FR-024.
- *MongoDB checkpointer* — possible but adds indirection; Postgres is already
  in the stack and better-matched to LangGraph's relational checkpoint model.

---

## R-003: Research execution strategy inside the Research node

**Decision**: The Research node runs a bounded "plan → search → synthesize"
loop:
1. **Plan**: GPT-4o produces 3–5 structured sub-queries from the user's
   question (a `ResearchPlan` Pydantic model).
2. **Search (parallel)**: Each sub-query runs concurrently via Tavily Search
   API (async), with a hard cap of 8 total Tavily calls per request.
3. **Synthesize**: GPT-4o takes the collected snippets and produces an
   `IntelligenceBrief` with strict Pydantic-validated structure — every finding
   carries confidence level, ≥1 source URL drawn from Tavily results, and a
   consulted-at timestamp.
4. **Validate**: A post-synthesis check asserts that every `source_url` in
   every finding appears in the actual Tavily result set. Any finding whose
   sources don't match is dropped or rewritten. This enforces SC-004 (zero
   fabricated attributions).

Wall-clock budget: 60 seconds total; streaming progress events at each phase.

**Rationale**: Parallel sub-queries satisfy FR-009. The post-synthesis source
validation step is the critical anti-hallucination gate — it is the difference
between "we told the LLM to cite sources" and "we enforced that citations are
real." SC-004 demands zero fabrication; only a deterministic post-check
guarantees it.

**Alternatives considered**:
- *Agentic ReAct loop* — higher quality but unbounded. Rejected because it
  conflicts with FR-010 (bounded effort) and the 30s target (SC-002).
- *Trust the LLM's citations without verification* — cheapest but cannot
  guarantee SC-004. Rejected.
- *Full multi-hop deep research* — deferred per PRD §8.2 "bounded depth
  budget"; the slice handles single-hop with parallel sub-queries, multi-hop
  arrives in a later spec.

---

## R-004: Signal source for MVP slice

**Decision**: Tavily Search API only for this slice.

**Rationale**: Tavily is already specified in the SAD integration layer. It
covers general web search including news, blog posts, forum content, and
product pages — sufficient for the P1 user story. Adding Meta Ad Library,
Reddit, Crunchbase, etc. is valuable but multiplies integration complexity and
is better scoped to its own spec once the Research slice is validated.

**Alternatives considered**:
- *Tavily + Reddit + Meta Ad Library from day one* — higher fidelity but
  triples the tool surface and contract-test burden.
- *Direct SerpAPI / Brave Search* — rejected; Tavily is already in the SAD.

---

## R-005: Intent classification — research vs non-research

**Decision**: The Supervisor node uses Claude Sonnet with a structured-output
schema (`SupervisorDecision` Pydantic model) returning one of:
`research | clarification_needed | out_of_scope | followup_on_existing_brief`.
The prompt includes the recent conversation history (last 10 messages) plus
any existing `IntelligenceBrief` from the current conversation.

**Rationale**: Structured output (not freeform) means the router's decision is
machine-readable and testable. Claude Sonnet is the constitution-mandated
router choice per ADR-010. Including the existing brief in context is what
enables FR-020 (answer follow-ups without re-running research).

**Alternatives considered**:
- *Keyword heuristics* — rejected; brittle against natural language.
- *Tool-calling dispatch instead of structured output* — equivalent in this
  context; structured output chosen for simplicity and LangSmith trace
  readability.

---

## R-006: Clarification flow

**Decision**: When the Supervisor classifies a question as
`clarification_needed`, a dedicated clarification sub-node emits an
`ephemeral_ui` event of type `clarification_poll` — a Shadcn-based poll
component with 3–4 narrowing options generated by the LLM. The user selects
one, which is posted back via `POST /api/v1/chat/ephemeral`, injected into the
LangGraph state, and the graph resumes from the Supervisor with the narrowed
question.

**Rationale**: Single-click interaction satisfies FR-019. Using LangGraph's
human-in-the-loop interruption (graph `interrupt` + resume) avoids custom
pause/resume plumbing. The `clarification_poll` ephemeral component is the
first of several ephemeral UI patterns — it is intentionally generalisable.

**Alternatives considered**:
- *Free-text clarification* — rejected; fails FR-019's single-interaction
  requirement.
- *Server-side heuristic narrowing without user input* — rejected; scope
  decisions belong to the user.

---

## R-007: Persistence split — Postgres vs MongoDB

**Decision**:
- **Postgres (Prisma):** `User`, `Session` (BetterAuth), `Conversation`,
  `Message`, `ResearchRequest`, `FailureRecord`, plus LangGraph's own
  checkpoint table.
- **MongoDB (Motor):** `intelligence_briefs` collection. Each document holds
  the full `IntelligenceBrief` including nested `Finding[]` and
  `SourceAttribution[]`.
- **Link**: `Message` rows that represent a brief carry a
  `brief_id: string` (MongoDB ObjectId as string) pointing to the document.

**Rationale**: Matches ADR-004 — deeply nested, schema-evolving documents live
in Mongo; relational user/session/conversation data lives in Postgres.
Messages are relational (ordered, paginated, filtered by conversation); briefs
are document-shaped. The boundary between the two is a single foreign
reference, which is cheap to maintain.

**Alternatives considered**:
- *Everything in Postgres* — ADR-004 already rejected JSONB for campaign data;
  the same reasoning applies to briefs.
- *Everything in MongoDB* — loses BetterAuth/Prisma integration on Neon.

---

## R-008: SSE event protocol versioning

**Decision**: SSE events carry a top-level `v: 1` field. The event `type`
enum is closed and additions require a MINOR version bump. Repurposing an
existing type is forbidden (per Constitution IV). The generated TypeScript
types in `apps/web/lib/types/sse-events.ts` are derived from the Pydantic
models at build time to prevent drift.

**Rationale**: Constitution principle IV mandates backward-compatible event
evolution. A version field + generated types operationalises it.

**Alternatives considered**:
- *Unversioned events* — rejected; no way to evolve safely.
- *GraphQL subscriptions* — heavier; SSE is already locked in per ADR-008.

---

## R-009: LLM router configuration for this slice

**Decision**: The `llm_router` service exposes `get_llm(purpose)` where
`purpose` is one of `supervisor | research_plan | research_synthesize |
ui_schema`. Mapping for this slice:

| Purpose | Model | Rationale |
|---|---|---|
| `supervisor` | Claude Sonnet (latest) | Routing, instruction following (ADR-010) |
| `research_plan` | GPT-4o | Structured decomposition, JSON output |
| `research_synthesize` | GPT-4o | Large context, structured extraction (ADR-010) |
| `ui_schema` | Claude Sonnet | Precise ephemeral UI schema generation (ADR-010) |

**Rationale**: Follows ADR-010 exactly. Having the router in place from day one
means later agents (Content, Outreach) plug in without refactor.

---

## R-010: Tavily rate limits, timeouts, and caching

**Decision**: Each Tavily call has a 10s timeout and is retried once on
network error with exponential backoff. Identical queries within a 5-minute
window are served from a Redis cache (key: SHA-256 of normalized query).
Global per-user rate limit: max 10 research requests per hour, enforced by a
Redis counter with a 1-hour TTL.

**Rationale**: Protects against cost runaways and respects Tavily's published
limits. The Redis cache cuts repeat cost during follow-up flows where the same
sub-query may recur.

**Alternatives considered**:
- *No caching* — wastes budget on identical queries during clarification
  loops.
- *Longer cache TTL* — risks stale results on a fast-moving market, which
  defeats the product's value proposition.

---

## R-011: Failure taxonomy and recovery

**Decision**: Enumerated `FailureCode`:

| Code | Cause | Recoverable |
|---|---|---|
| `tavily_unavailable` | Tavily API down / timeout | yes |
| `tavily_rate_limited` | 429 from Tavily | yes (backoff) |
| `llm_unavailable` | OpenAI / Anthropic outage | yes |
| `llm_invalid_output` | Pydantic validation failed after retries | no |
| `no_findings_above_threshold` | All candidate findings below min confidence | no (suggest rephrase) |
| `user_cancelled` | User navigated away / cancelled | no |
| `budget_exceeded` | Hit 8-query or 60s cap with nothing returnable | no (suggest narrower question) |
| `rate_limited_user` | User hit 10/hour cap | yes (wait) |

Each failure produces a `FailureRecord` persisted in Postgres and emitted as
an SSE `error` event with `recoverable` flag and a human message. Failures are
visible in the conversation history on reload (FR-025, FR-026).

**Rationale**: An explicit enumeration lets tests assert coverage (SC-006: zero
silent failures). Persisting failure records in Postgres (not just streaming
them) satisfies FR-023's persistence requirement.

---

## R-012: Frontend SSE client reconnection

**Decision**: Use the browser-native `EventSource` API wrapped in a thin
custom client that (a) reconnects with exponential backoff on disconnect, (b)
resumes with the last seen `event_id` via the SSE-standard `Last-Event-ID`
header, (c) de-duplicates events by `event_id` in the Zustand chat store.

**Rationale**: SSE standard reconnection is free; the only custom piece is
dedup on resume, which is a few lines of code. This satisfies FR-024's
reconnection requirement without a custom WebSocket reconnection layer.

**Alternatives considered**:
- *Raw `fetch` with ReadableStream* — more control but we'd rebuild what
  `EventSource` already gives us.
- *A library like `@microsoft/fetch-event-source`* — viable, but the standard
  API is sufficient for this slice.

---

## R-013: Testing strategy for non-deterministic LLM output

**Decision**: Three test layers:
1. **Unit** — pure Python logic (Pydantic validation, source-verification
   gate, progress event transformation) is fully deterministic and unit-tested.
2. **Contract** — SSE event schemas and REST request/response shapes are
   pinned via JSON Schema tests generated from Pydantic; frontend runs the
   same schemas via generated TS types.
3. **Integration with recorded Tavily + recorded LLM** — full LangGraph runs
   against recorded Tavily responses and recorded LLM outputs (stored as
   fixtures under `apps/api/tests/fixtures/`). Record/replay via a thin
   wrapper around `respx` for Tavily and a custom fake `ChatModel` for LLM
   calls that replays stored completions. This gives deterministic end-to-end
   tests without hitting live APIs.
4. **LangSmith evals (separate from CI)** — a small hand-curated eval set of
   research questions scored on (a) did any finding hallucinate a source, (b)
   confidence level calibration, (c) structure validity. Run nightly, not on
   every PR.

**Rationale**: Deterministic CI with realistic fixtures for the integration
layer; quality scoring lives in a separate eval loop so CI stays fast and
green-or-red.

**Alternatives considered**:
- *Live API calls in CI* — flaky, slow, expensive, rate-limit-prone.
- *Only unit tests* — misses the whole point of agent integration bugs.

---

## R-014: What is deliberately deferred from this slice

The following are in the SAD but NOT built in this spec. Each is noted so that
the next spec can pick it up cleanly:

- **Qdrant vector store** — intelligence accumulation is out of scope.
  Introduced by the spec that first reuses prior findings.
- **ARQ background workers** — research runs in the request path for this
  slice because the budget is 60s. ARQ arrives when either (a) research goes
  multi-hop beyond 60s, or (b) Outreach needs post-deployment polling.
- **Content, Outreach, Feedback agents** — separate specs.
- **Channel integrations and OAuth flows** — no channels connected.
- **Webhooks** — no inbound engagement data yet.
- **Performance dashboards** — no aggregated analytics yet.
- **Onboarding flow** — MVP uses plain sign-up → chat.

All Phase 0 decisions are resolved. Phase 1 may proceed.
