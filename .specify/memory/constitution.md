<!--
Sync Impact Report
==================
Version change: 1.0.0 → 1.1.0
Rationale: MINOR bump. Deployment platform redefined from Railway to Vercel in the
Technology & Security Constraints section. No principles added, removed, or
redefined; governance procedure unchanged. Cascading constraints (private-network
auth model, self-hosted Qdrant location) updated and flagged for follow-up ADRs.

Modified principles: none (principle text unchanged)

Modified sections:
  - Technology & Security Constraints — Stack: Deployment target changed from
    "Railway with Railpack" to "Vercel (Next.js frontend); backend hosting per
    forthcoming ADR". Data: Qdrant location no longer "self-hosted on Railway".
  - Technology & Security Constraints — Security: Removed reliance on Railway's
    private network (`api.railway.internal`) for the FastAPI ↔ Next.js trust
    boundary. Token-based auth at the FastAPI layer is now REQUIRED rather than
    a deferred trigger, because Vercel does not provide an equivalent private
    network between the Next.js runtime and a self-hosted FastAPI service.

Added sections: none
Removed sections: none

Templates reviewed:
  ✅ .specify/memory/constitution.md (this file)
  ⚠ .specify/templates/plan-template.md — re-verify Constitution Check still aligns
  ⚠ docs/ADR-Amplify.md — supersede ADR-006 (private-network trust) and add new
     ADR for Vercel deployment + backend hosting target + Qdrant relocation
  ⚠ docs/SAD-Amplify.md — update deployment topology, auth model, Qdrant host
  ⚠ railway.toml — remove or replace once new deployment target is finalized
  ⚠ apps/api/middleware/auth.py — replace `X-User-Id` trust with token-based auth
  ⚠ specs/001-research-agent/plan.md, tasks.md — refresh deployment references

Deferred items:
  - TODO(BACKEND_HOSTING_TARGET): Vercel serverless functions are unsuitable for
    long-lived LangGraph runs, ARQ workers, and SSE streams. Backend hosting
    target (Fly.io, Render, AWS, etc.) MUST be selected via a new ADR before
    the next release.
  - TODO(QDRANT_HOSTING_TARGET): Self-hosted Qdrant must be re-platformed; ADR
    required.
-->

# Amplify Constitution

Amplify is a conversational, AI-powered system that compresses the marketing growth
loop — Research → Content → Outreach → Feedback — into a single continuous workflow.
This constitution defines the non-negotiable principles and constraints that govern
how Amplify is designed, built, and evolved.

## Core Principles

### I. Conversation-First Experience

The chat interface is the primary workspace. The web shell (campaign history,
dashboards, settings, integrations) supports conversation — never the other way
around. Every user-facing feature MUST first be expressible inside the conversation;
dashboard affordances are a supplement, not a substitute.

Structured interaction MUST be delivered via ephemeral UI components rendered inline
within the message stream (variant grids, approval flows, polls, briefs). Users MUST
NOT be forced to leave the conversation to complete a loop stage.

*Rationale:* The product thesis is closing the distance between signal and action.
Context-switching across tools is the core problem being solved; the interface MUST
embody that solution.

### II. Specialist Agents via LangGraph

The growth loop MUST be implemented as a LangGraph state graph with a Supervisor
agent routing to specialist agents (Research, Content, Outreach, Feedback, UI).
Each specialist agent MUST own its prompts, tools, and typed output schemas. The
Supervisor routes; specialists execute. No agent may silently take on another
agent's responsibilities.

New capabilities MUST be added as either (a) a new node in the graph, (b) a new
tool on an existing agent, or (c) a new edge/transition — not as ad-hoc LLM calls
outside the graph. LangGraph checkpointing MUST be used for conversation state
persistence; custom serialisation of graph state is prohibited.

*Rationale:* Specialisation keeps prompts, tools, and evaluations tractable. A
single graph-based orchestrator gives state persistence, conditional routing, and
human-in-the-loop interruption as framework features rather than custom code.

### III. Structured State Over Freeform Text

Every agent output that has downstream consequences — research findings, content
variants, deployment records, feedback reports, ephemeral UI components — MUST be
a typed, versioned, queryable Pydantic model. Freeform text is permitted only for
user-facing message content; it MUST NOT be the source of truth for anything a
later stage of the loop will consume.

Research findings MUST carry confidence levels, source attribution, and timestamps.
Content variants MUST carry target segment metadata and an explicit testable
hypothesis. Campaign records MUST be versioned. Intelligence accumulated across
cycles MUST be retrievable by structured query, not by re-reading chat history.

*Rationale:* The "each cycle starts sharper" promise depends on prior findings
being machine-readable. Freeform chat history cannot compound into intelligence.

### IV. Stream Everything

All agent execution visible to the user MUST stream to the frontend via SSE as it
happens: agent start/end, tool calls, tool results, partial text, ephemeral UI
emissions, and errors. Users MUST NOT stare at a spinner wondering what is
happening. The SSE event protocol MUST remain typed and backward-compatible across
releases; adding new event types is permitted, repurposing existing types is not.

*Rationale:* Long-running agent work is opaque by default. Streaming converts
latency into perceived progress and gives users the information they need to
intervene mid-cycle.

### V. Fail Visibly, Never Silently

When an agent fails, a tool errors, or a third-party API is unavailable, the
system MUST surface the failure clearly in the conversation with a suggested next
step. Silently dropping context, swallowing exceptions, or returning empty
results without explanation is prohibited.

Every failure MUST be distinguishable as recoverable or terminal via the SSE
`error` event's `recoverable` flag. Recoverable failures MUST offer the user a
concrete retry or alternate path. LangSmith tracing MUST be enabled in all
environments so failures can be reconstructed after the fact.

*Rationale:* User trust in an autonomous system collapses the first time it
quietly loses their work. Visible failure is a safety property, not a nice-to-have.

### VI. Human-in-the-Loop Before Outreach

Any action that publishes, sends, or spends money on a third-party channel
(LinkedIn post, email send, ad campaign launch, paid deployment) MUST require
explicit user approval via an ephemeral approval-flow component before execution.
The approval surface MUST show exactly what will be sent and where. Fire-and-forget
outreach is prohibited in the MVP and any subsequent release until an explicit
constitution amendment authorizes auto-deploy rules with per-channel scoping.

Compliance checks (GDPR, CAN-SPAM, platform ToS, opt-out handling) MUST run inside
the Outreach Agent before the approval surface is shown. The user approves
content that has already been validated; they are not the first line of compliance.

*Rationale:* User trust and legal exposure are the two highest-risk failure modes
of autonomous outreach. Both are mitigated by the same gate.

### VII. Solo-Founder Viable (Simplicity & Managed Services)

Every infrastructure and tooling choice MUST favour managed services, minimal
operational burden, and a single monorepo. Complexity is pushed into the LangGraph
graph definition and typed schemas — not into deployment topology, custom
orchestration, or bespoke infrastructure.

New services, databases, queues, or deployment targets MUST be justified against
this principle in an ADR. Self-hosting is permitted only when (a) no suitable
managed option exists, or (b) vendor lock-in or cost would materially harm the
product. Adding a second orchestration layer, a microservice split, or a
workspace tool (Turborepo/Nx) requires an amendment.

*Rationale:* The product is being built by a solo founder. Ops burden is the
scarcest resource. Every hour spent managing infrastructure is an hour not spent
on the growth loop itself.

## Technology & Security Constraints

The following constraints are binding. Deviations require an ADR and a
constitution amendment.

**Stack (per SAD v1.1 and ADRs):**
- Frontend: Next.js 16 App Router, Tailwind 4, Shadcn/ui, Zustand for client state,
  Next.js native features for server state (no TanStack Query unless justified).
- Backend: FastAPI (async), LangGraph for orchestration, Prisma (prisma-client-py)
  for Postgres, Motor for MongoDB, ARQ for background jobs.
- Data: Neon Postgres (users, sessions, integrations, preferences), MongoDB
  (campaign documents), Qdrant (vector store; hosting target per forthcoming
  ADR — see deferred items), Redis (cache + ARQ queue).
- LLMs: Multi-provider (OpenAI GPT-4o, Anthropic Claude Sonnet, Google Nano Banana 2)
  routed per agent via `llm_router` service. No agent may hardcode a provider
  outside the router.
- Observability: LangSmith tracing MUST be enabled in dev, staging, and production.
- Deployment: Vercel hosts the Next.js frontend (App Router, Edge/Node runtimes
  as required). The FastAPI backend, ARQ workers, and self-hosted services
  (Qdrant, Redis) MUST run on a host that supports long-lived processes and
  SSE; the specific target is selected per the forthcoming backend-hosting ADR.
  The single monorepo is preserved.

**Security (non-negotiable):**
- OAuth 2.0 for all channel integrations. User credentials MUST NEVER be stored in
  plaintext. API keys and OAuth tokens MUST be encrypted at rest.
- Authentication lives in Next.js via BetterAuth. Because the Vercel-hosted
  Next.js runtime and the FastAPI backend no longer share a provider-private
  network, FastAPI MUST authenticate every inbound request with a verifiable,
  short-lived token (e.g., signed JWT minted by the Next.js auth layer or a
  shared secret HMAC) at the API boundary. Bare `X-User-Id` trust is prohibited.
  FastAPI SHOULD remain network-restricted (allow-list, VPC, or platform
  equivalent) where the chosen host supports it; token verification is the
  primary gate, network restriction is defense in depth.
- Webhook endpoints MUST validate inbound signatures (HMAC or platform-equivalent)
  and are exempt from the `X-User-Id` requirement.
- SOC 2 Type I is a 12-month post-launch target; design decisions MUST NOT
  foreclose that path.

**Non-functional targets (per PRD §10):**
- Research initial findings: 15–30s. Content generation: 10–20s per variant.
  Outreach deployment confirmation: ≤5s after approval. Ephemeral UI render: ≤1s.
- 99.5% uptime for the core platform.
- No data loss on session disconnect; LangGraph state MUST be checkpointed to
  Postgres so conversations survive restarts.

## Development Workflow & Quality Gates

**Spec-driven development.** Features MUST flow through the speckit lifecycle:
specification → plan → tasks → implementation. The Constitution Check in
`plan-template.md` MUST verify compliance with the principles above before
implementation begins. Plans that violate a principle MUST either be revised or
accompanied by an amendment to this constitution.

**Monorepo discipline (per ADR-001).** All changes land in the single `amplify/`
repository. Cross-cutting changes (schema updates, shared types, API contract
changes) SHOULD be delivered in one PR rather than split across repos.

**Schema as contract.** The Prisma schema (Neon Postgres) and Pydantic models
(MongoDB documents, SSE events, ephemeral UI schemas) are the contract between
frontend and backend. Breaking changes to these schemas require a migration plan
and MUST be called out in the PR description.

**Observability gates.** Every new agent, tool, or graph node MUST be traceable
end-to-end in LangSmith before merge. Adding an untraced code path is a blocker.

**Testing discipline.** Agent behaviour MUST be evaluated against representative
inputs before deployment to production. Tool integrations MUST have contract tests
against their external APIs (recorded or live). Ephemeral UI components MUST have
schema validation tests so frontend-backend drift is caught at build time.

**Compliance and safety review.** Any change touching the Outreach Agent, its
tools, or the approval flow requires explicit review against Principle VI before
merge.

## Governance

This constitution supersedes ad-hoc practices and informal conventions. When a
principle here conflicts with convenience, the principle wins or the constitution
is amended — not quietly ignored.

**Amendment procedure.** Amendments MUST be proposed as a PR that (a) modifies
this file, (b) includes a Sync Impact Report in the file header, (c) updates any
dependent templates and runtime guidance, and (d) bumps the version per the
policy below.

**Versioning policy (semantic).**
- **MAJOR:** Removal or backward-incompatible redefinition of a principle or a
  governance rule.
- **MINOR:** Addition of a new principle or materially expanded guidance in an
  existing principle or section.
- **PATCH:** Clarifications, wording fixes, typo corrections, non-semantic
  refinements.

**Compliance review.** Every PR description MUST note which principles the
change touches. Reviewers MUST verify that streaming, structured state,
human-in-the-loop, and fail-visibly requirements are honoured wherever
applicable. Complexity beyond what a principle permits MUST be justified in an
ADR under `docs/`.

**ADRs as the companion record.** Architectural decisions that shape or depend on
this constitution live in `docs/ADR-Amplify.md`. When an ADR is added or
superseded, this constitution MUST be reviewed for required updates in the same
PR.

**Version**: 1.1.0 | **Ratified**: 2026-04-13 | **Last Amended**: 2026-04-18
