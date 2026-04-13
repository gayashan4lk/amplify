# Implementation Plan: Research Agent

**Branch**: `001-research-agent` | **Date**: 2026-04-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-research-agent/spec.md`

## Summary

Ship the first shippable slice of Amplify: a conversational research experience
where a signed-in user asks a market question and receives a structured
**intelligence brief** rendered inline in the chat. This slice stands up the
architectural foundation the rest of the product depends on — Next.js chat UI,
FastAPI backend with SSE streaming, LangGraph Supervisor → Research agent
routing, typed Pydantic outputs, inline ephemeral UI components, and persistent
conversation state — while explicitly deferring Content, Outreach, Feedback, and
intelligence accumulation.

**Technical approach:** A Next.js 16 App Router frontend renders chat + a
`<IntelligenceBrief />` ephemeral component driven by typed SSE events. A FastAPI
backend exposes `POST /api/v1/chat/stream` which runs a LangGraph graph
(Supervisor → Research) with a Postgres checkpointer. The Research agent uses
Tavily for web search, synthesizes findings with GPT-4o, and emits a typed
`IntelligenceBrief` Pydantic model. Conversations and messages live in Neon
Postgres (Prisma); briefs live in MongoDB as nested documents. Auth is
BetterAuth-in-Next.js only; FastAPI trusts `X-User-Id` on the private network.
Observability via LangSmith from day one.

## Technical Context

**Language/Version**:
- Backend: Python 3.12
- Frontend: TypeScript 5.x (Node 20 LTS)

**Primary Dependencies**:
- Frontend: Next.js 16 (App Router), React 19, Tailwind CSS 4, Shadcn/ui,
  Zustand, BetterAuth, native `EventSource`
- Backend: FastAPI, LangGraph, LangChain (`langchain-openai`,
  `langchain-anthropic`), Pydantic v2, Prisma (`prisma-client-py`), Motor (async
  MongoDB driver), ARQ, `tavily-python`, `httpx`, LangSmith SDK

**Storage**:
- Neon Postgres via Prisma — users, sessions (BetterAuth), conversations,
  messages, research requests, failure records, LangGraph checkpoints
- MongoDB — `intelligence_briefs` collection (findings nested as subdocuments)
- Redis — ARQ queue + short-lived cache (Tavily response cache, rate limit
  counters)
- Qdrant — **not used in this slice**; intelligence accumulation is out of scope

**Testing**:
- Backend: `pytest` + `pytest-asyncio`; `respx` for HTTP mocking; contract tests
  for SSE event schemas; LangSmith eval suites for research quality
- Frontend: Vitest + React Testing Library for components; Playwright for
  end-to-end chat → brief scenarios
- Schema validation: Pydantic models on the backend, generated TS types on the
  frontend (via `datamodel-code-generator` or `pydantic2ts`) to keep SSE event
  shapes in sync

**Target Platform**:
- Web, modern evergreen browsers (Chrome/Safari/Firefox/Edge latest two majors)
- Railway cloud (Railpack) for both Next.js and FastAPI; Next.js is public,
  FastAPI is private network only

**Project Type**: Web application (Next.js frontend + FastAPI backend in one
monorepo per ADR-001).

**Performance Goals**:
- Acknowledge a research request in ≤2s (FR-006)
- Stream first progress event within ≤3s
- Produce initial intelligence brief in ≤30s under normal conditions (FR-008,
  SC-002)
- Ephemeral UI render ≤1s after event arrival

**Constraints**:
- Bounded research effort per request (FR-010): max ~8 Tavily queries and max
  ~60s wall-clock per research run
- No fabricated source attributions (FR-016, SC-004): every finding must link
  to a real URL returned by Tavily
- Fail visibly always (Constitution V): zero silent empty briefs
- FastAPI MUST NOT be publicly exposed; all auth logic stays in Next.js

**Scale/Scope** (MVP validation phase):
- 10–100 beta users
- Up to 10 concurrent research runs
- Conversations retained indefinitely; briefs retained indefinitely
- English-language sources only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Conversation-First Experience | ✅ | Chat is the primary surface; brief renders inline as an ephemeral component. No dashboard-only paths. |
| II. Specialist Agents via LangGraph | ✅ | Supervisor node routes to Research node in a LangGraph state graph. Postgres checkpointer persists state. No ad-hoc LLM calls outside the graph. |
| III. Structured State Over Freeform Text | ✅ | `IntelligenceBrief`, `Finding`, `SourceAttribution` are Pydantic models stored in MongoDB. Findings are queryable, not prose. |
| IV. Stream Everything | ✅ | Typed SSE event protocol: `agent_start`, `agent_end`, `text_delta`, `tool_call`, `tool_result`, `ephemeral_ui`, `error`, `done`. Frontend renders progressively. |
| V. Fail Visibly, Never Silently | ✅ | All failures surface as `error` events with `recoverable` flag + next-step suggestion. FR-025–FR-028 enforce this in the spec. LangSmith traces every run. |
| VI. Human-in-the-Loop Before Outreach | ✅ N/A | No outreach in this slice. FR-029 explicitly forbids it. |
| VII. Solo-Founder Viable | ✅ | Monorepo, managed Neon/MongoDB-on-Railway/Redis-on-Railway, no new services introduced beyond what the SAD already approved. Qdrant deferred to next slice. |

**Gate result: PASS.** No violations; Complexity Tracking section is not needed.

Post-Phase-1 re-check: ✅ still passes (see Phase 1 section below).

## Project Structure

### Documentation (this feature)

```text
specs/001-research-agent/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── sse-events.md         # Typed SSE event schemas
│   ├── rest-endpoints.md     # HTTP endpoint contracts
│   └── intelligence-brief.md # Pydantic schema contract
└── checklists/
    └── requirements.md  # Spec quality checklist (existing)
```

### Source Code (repository root)

```text
amplify/
├── apps/
│   ├── web/                              # Next.js 16 App Router
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── signup/page.tsx
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── chat/
│   │   │   │   │   ├── page.tsx                # New conversation
│   │   │   │   │   └── [conversationId]/page.tsx
│   │   │   │   └── conversations/page.tsx       # List of prior conversations
│   │   │   ├── api/
│   │   │   │   └── auth/[...all]/route.ts       # BetterAuth handler
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── message-list.tsx
│   │   │   │   ├── message-input.tsx
│   │   │   │   ├── agent-status.tsx
│   │   │   │   └── stream-renderer.tsx
│   │   │   ├── ephemeral/
│   │   │   │   ├── intelligence-brief.tsx
│   │   │   │   └── clarification-poll.tsx
│   │   │   └── ui/                              # Shadcn primitives
│   │   ├── lib/
│   │   │   ├── auth.ts                          # BetterAuth client
│   │   │   ├── auth-server.ts                   # BetterAuth server
│   │   │   ├── sse-client.ts
│   │   │   ├── api-client.ts                    # Typed fetch to FastAPI (server-side)
│   │   │   ├── stores/
│   │   │   │   ├── chat-store.ts                # Zustand: stream buffer, drafts
│   │   │   │   └── ui-store.ts
│   │   │   └── types/
│   │   │       └── sse-events.ts                # Generated from Pydantic
│   │   └── tests/
│   │       ├── components/                      # Vitest + RTL
│   │       └── e2e/                             # Playwright
│   │
│   └── api/                                     # FastAPI backend
│       ├── main.py
│       ├── routers/
│       │   ├── chat.py                          # /chat/stream, /chat/ephemeral
│       │   └── conversations.py                 # /conversations list + detail
│       ├── middleware/
│       │   └── auth.py                          # X-User-Id trust middleware
│       ├── agents/
│       │   ├── graph.py                         # LangGraph definition (Supervisor → Research)
│       │   ├── supervisor.py
│       │   └── research.py
│       ├── tools/
│       │   └── tavily_search.py
│       ├── models/
│       │   ├── chat.py                          # ChatRequest, ProgressEvent
│       │   ├── research.py                      # IntelligenceBrief, Finding, SourceAttribution
│       │   ├── ephemeral.py                     # EphemeralComponent schemas
│       │   └── errors.py                        # FailureRecord
│       ├── services/
│       │   ├── llm_router.py                    # Claude Sonnet (supervisor/UI) + GPT-4o (research)
│       │   ├── brief_store.py                   # MongoDB Motor operations
│       │   └── conversation_store.py            # Prisma operations
│       ├── sse/
│       │   ├── events.py                        # Typed SSE event models
│       │   └── transform.py                     # LangGraph astream_events → SSE events
│       ├── db/
│       │   └── prisma/
│       │       └── schema.prisma
│       ├── config.py
│       ├── pyproject.toml
│       └── tests/
│           ├── contract/                        # SSE event + REST schema tests
│           ├── integration/                     # LangGraph end-to-end with recorded Tavily
│           └── unit/
│
├── .specify/
│   └── memory/constitution.md
├── docs/                                        # PRD, SAD, ADR
├── specs/001-research-agent/                    # This feature
├── railway.toml
├── .env.example
└── README.md
```

**Structure Decision**: Web application monorepo with `apps/web` (Next.js 16)
and `apps/api` (FastAPI), matching ADR-001 and SAD §4. No `packages/` workspace
tooling per ADR-001. Shared SSE event types are generated from Pydantic models
into `apps/web/lib/types/sse-events.ts` at build time to keep the contract in
sync without introducing Turborepo.

## Complexity Tracking

No constitution violations — section intentionally empty.
