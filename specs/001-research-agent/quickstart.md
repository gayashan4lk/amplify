# Quickstart — Research Agent (001)

**Feature**: 001-research-agent
**Audience**: a developer (currently the solo founder) standing up this slice
locally for the first time.

This quickstart gets a working end-to-end research flow running on your laptop:
sign in via Next.js, ask a market question in chat, watch the research stream,
and see a rendered intelligence brief.

---

## Prerequisites

- Node 20 LTS (`node --version`)
- Python 3.13 (`python3.13 --version`)
- `uv` for Python package management (`uv --version`)
- `pnpm` for Node package management
- Cloud accounts (free tiers — see ADR-018):
  - Neon Postgres (https://neon.tech)
  - MongoDB Atlas M0 (https://cloud.mongodb.com)
  - Upstash Redis (https://upstash.com)
- API keys:
  - `OPENAI_API_KEY` (GPT-4o)
  - `ANTHROPIC_API_KEY` (Claude Sonnet)
  - `TAVILY_API_KEY`
  - `LANGSMITH_API_KEY` (optional but recommended)

---

## 1. Provision cloud services (free tiers)

Per ADR-018, local dev uses managed cloud free tiers — no Docker.

1. **Neon Postgres** — create a project, create a `amplify_dev` database (or
   a dev branch), copy the pooled connection string.
2. **MongoDB Atlas** — create an M0 cluster, create a DB user, allow your IP,
   copy the SRV connection string.
3. **Upstash Redis** — create a database (TLS), copy the `rediss://` URL.

---

## 2. Configure environment

Env templates live **per app**. There is no root `.env.example`.

```bash
cp apps/web/example.env apps/web/.env.local
cp apps/api/eample.env  apps/api/.env
```

**`apps/web/.env.local`** — what Next.js, BetterAuth, and Node Prisma need:

```
# Neon Postgres (shared with FastAPI in dev)
DATABASE_URL=postgresql://USER:PASSWORD@ep-xxx.region.aws.neon.tech/amplify_dev?sslmode=require

# BetterAuth
BETTER_AUTH_SECRET=dev-secret-change-me
BETTER_AUTH_URL=http://localhost:3000

# Next.js → FastAPI (private network in prod, localhost in dev)
FASTAPI_INTERNAL_URL=http://localhost:8000
```

**`apps/api/.env`** — what FastAPI, LangGraph, and `prisma-client-py` need:

```
# Same Neon Postgres (dev shares the instance; prod may differ)
DATABASE_URL=postgresql://USER:PASSWORD@ep-xxx.region.aws.neon.tech/amplify_dev?sslmode=require

# MongoDB Atlas
MONGODB_URI=mongodb+srv://USER:PASSWORD@cluster0.xxx.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB=amplify_dev

# Upstash Redis
REDIS_URL=rediss://default:PASSWORD@xxx.upstash.io:6379

# LLMs
OPENAI_API_KEY=sk-…
ANTHROPIC_API_KEY=sk-ant-…

# Research
TAVILY_API_KEY=tvly-…

# Observability
LANGSMITH_API_KEY=ls-…
LANGSMITH_PROJECT=amplify-dev
```

---

## 3. Install and migrate

```bash
# Frontend — owns the canonical Prisma schema and migration history
cd apps/web
pnpm install
pnpm prisma migrate dev --name research_agent_models
pnpm prisma generate

# Backend — mirrors the schema (generator swapped to prisma-client-py)
# and ONLY runs `prisma generate`. Never run `migrate dev` from here.
cd ../api
uv sync
uv run prisma generate
```

Prisma lives in both apps. `apps/web/prisma/schema.prisma` is the single
source of truth; `apps/api/db/prisma/schema.prisma` is a hand-kept mirror
whose only diff is the `generator client` block.

This creates the Postgres tables: `User`, `Session`, `Conversation`,
`Message`, `ResearchRequest`, `FailureRecord`, plus LangGraph's own checkpoint
tables.

---

## 4. Run the dev servers

In two terminals:

```bash
# Terminal 1 — FastAPI
cd apps/api
uv run uvicorn main:app --reload --port 8000
```

```bash
# Terminal 2 — Next.js
cd apps/web
pnpm dev
```

Visit `http://localhost:3000`, sign up, sign in.

---

## 5. Try the happy path

1. Sign in → you land on `/chat`.
2. Type a well-scoped research question, e.g.
   *"What is Notion's pricing and positioning for teams in April 2026?"*
3. Watch the stream:
   - `agent_start: supervisor` → routing
   - `agent_start: research` → planning
   - `progress: searching` → multiple sub-queries against Tavily
   - `progress: synthesizing` → GPT-4o composing the brief
   - `progress: validating` → source verification gate
   - `ephemeral_ui: intelligence_brief` → the rendered card
   - `done`
4. Inspect the brief: each finding should show a confidence label and at
   least one clickable source.
5. Ask a follow-up like *"Tell me more about the second finding."* It should
   answer from the existing brief without re-running the full research.

---

## 6. Try the clarification path

1. Ask a deliberately vague question: *"What should we do?"*
2. The Supervisor routes to `clarification_needed`; a
   `clarification_poll` ephemeral component appears inline with 3–4 options.
3. Click an option. The research request resumes from where it paused and
   continues to completion.

---

## 7. Try the failure path

Manually trigger each failure to verify visible-failure handling:

1. **Tavily unavailable** — unset `TAVILY_API_KEY` or point it at a bad host,
   ask a question. Expect an `error` event with `code: tavily_unavailable`,
   `recoverable: true`, and a retry suggestion.
2. **No findings above threshold** — ask something obscure with no public
   sources. Expect `code: no_findings_above_threshold` with a rephrasing
   suggestion — not a fabricated brief.
3. **Budget exceeded** — temporarily lower the per-request budget in
   `apps/api/config.py` to 1 query / 5 seconds and ask a broad question.
   Expect `code: budget_exceeded`.

Each failure should render as a specific, human-readable message in the
conversation with a clear next step.

---

## 8. Verify persistence

1. Refresh the browser. Your conversation should still be there.
2. Sign out, sign back in. Open the conversation from the list. All messages
   and the full intelligence brief should render identically.
3. Start a new research request, then close the browser tab mid-stream.
   Reopen the conversation. Either the final result or the current progress
   should be visible — never a lost state.

---

## 9. Inspect traces

Open LangSmith (`https://smith.langchain.com/o/<your-org>/projects/amplify-dev`).
You should see:
- A run per research request with the Supervisor → Research node hierarchy.
- Every Tavily call with its inputs and outputs.
- Every LLM call with its prompt and completion.
- The final structured brief.

If `LANGSMITH_API_KEY` is unset, tracing is skipped locally but MUST be
enabled in staging and production per the Constitution.

---

## 10. Run tests

```bash
# Backend
cd apps/api
uv run pytest

# Frontend
cd ../web
pnpm test            # Vitest
pnpm test:e2e        # Playwright
```

Integration tests use recorded Tavily + recorded LLM fixtures — no live API
calls in CI.

---

## You are done when

- Happy path produces a brief in under 30 seconds.
- Every finding in every brief has at least one source that resolves.
- Failure paths surface specific, actionable messages.
- Conversations survive reload, sign-out, and browser restart.
- LangSmith shows a complete trace for every research run.

If any of the above is NOT true, revisit the plan and re-check against the
constitution gates before proceeding to `/speckit.tasks`.
