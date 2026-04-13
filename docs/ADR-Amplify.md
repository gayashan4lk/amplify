# Architecture Decision Records: Amplify

**Version:** 1.0
**Date:** April 12, 2026
**Author:** Gayashan
**Status:** Active

---

## About This Document

This document captures the key architectural decisions made during the design of the Amplify. Each record follows a consistent format: the context that prompted the decision, the options considered, the decision made, and the consequences (both positive and negative) of that choice.

Decisions are numbered sequentially. Superseded decisions are marked as such with a reference to the replacing ADR.

---

## ADR-001: Monorepo Structure

**Status:** Accepted
**Date:** April 12, 2026

### Context

The platform consists of two primary applications — a Next.js frontend and a FastAPI backend — plus shared configuration (Prisma schema, environment variables, Docker Compose). As a solo founder, minimising context-switching between repositories and keeping deployments coordinated is critical.

### Options Considered

1. **Monorepo (single repository, no workspace tooling)** — both apps in one repo under `apps/web` and `apps/api`, with shared config at the root.
2. **Separate repositories** — independent repos for frontend and backend, deployed separately.
3. **Monorepo with Turborepo/Nx** — workspace-managed monorepo with build orchestration and caching.

### Decision

Option 1 — simple monorepo without workspace tooling.

### Consequences

- **Positive:** Single clone, single PR for cross-cutting changes, shared `.env` management, Railway deploys from one repo with path-based service detection.
- **Positive:** No learning curve or configuration overhead from Turborepo/Nx.
- **Negative:** No cross-app build caching or task orchestration. Acceptable at current scale — the build times for a Next.js app and a FastAPI app are individually fast enough.
- **Migration path:** If build times become painful with team growth, Turborepo can be added incrementally without restructuring the directory layout.

---

## ADR-002: Agent Orchestration Framework — LangGraph

**Status:** Accepted
**Date:** April 12, 2026

### Context

The growth loop requires multiple specialised AI agents (Research, Content, Outreach, Feedback) that need to be orchestrated with state management, conditional routing, and the ability to pause execution while waiting for user input (e.g., content approval). The orchestration framework is a foundational choice that affects every part of the backend.

### Options Considered

1. **LangGraph** — state graph-based orchestration with built-in checkpointing, conditional edges, and human-in-the-loop support.
2. **CrewAI** — role-based multi-agent framework with simpler abstractions.
3. **Custom orchestration** — hand-rolled state machine on top of raw LLM calls.

### Decision

LangGraph.

### Rationale

- The growth loop maps directly to a state graph: each agent is a node, transitions between stages are edges, and the supervisor agent is the entry/routing node.
- Built-in checkpointing to Postgres means conversation state persists across sessions without custom serialisation logic.
- Human-in-the-loop support (graph interruption and resumption) is essential for the approval flow before outreach deployment.
- LangSmith integration provides full observability over every agent run, tool call, and LLM invocation out of the box.
- CrewAI's role-based abstraction is simpler but less flexible for the conditional routing and parallel execution patterns the platform needs.

### Consequences

- **Positive:** State persistence, conditional routing, and human-in-the-loop are framework-level features rather than custom code.
- **Positive:** LangSmith tracing gives production-grade observability from day one.
- **Negative:** LangGraph has a steeper learning curve than CrewAI. The graph definition syntax requires understanding state reducers and conditional edges.
- **Negative:** Vendor coupling to the LangChain ecosystem. Mitigated by the fact that individual agents use standard LLM clients (ChatOpenAI, ChatAnthropic) which are easily replaceable.

---

## ADR-003: Primary Database — Neon Postgres with Prisma

**Status:** Accepted
**Date:** April 12, 2026

### Context

The platform needs a relational database for users, authentication sessions, channel integrations, conversations, and user preferences. This data is highly relational (users have integrations, conversations belong to users) and benefits from strong consistency and transactional guarantees.

### Options Considered

1. **Neon Postgres (serverless) + Prisma ORM**
2. **Supabase Postgres + Supabase client**
3. **PlanetScale (MySQL) + Prisma**

### Decision

Neon Postgres with Prisma.

### Rationale

- Neon's serverless architecture means zero capacity planning — the database scales to zero when idle and auto-scales under load, which is ideal for an early-stage product with unpredictable traffic.
- Prisma provides type-safe queries and schema migrations, reducing runtime errors. The `prisma-client-py` package brings this to the FastAPI side as well.
- Postgres is the most widely supported database in the ecosystem — every tool, ORM, and service integrates with it.
- Supabase was considered but adds a broader platform dependency (auth, storage, edge functions) beyond what's needed. The platform already uses BetterAuth for auth and Railway for infrastructure.
- PlanetScale was considered but MySQL's JSON support is weaker than Postgres, and PlanetScale's free tier has been discontinued.

### Consequences

- **Positive:** Serverless scaling, zero ops for the database layer.
- **Positive:** Prisma schema serves as the single source of truth for relational data models, shared across Next.js and FastAPI.
- **Negative:** Neon's serverless cold starts can add latency to the first query after idle periods (typically 100–500ms). Mitigated by keepalive connections in production.
- **Negative:** `prisma-client-py` is less mature than the Node.js Prisma client. Edge cases may require raw SQL.

---

## ADR-004: Campaign Data Store — MongoDB

**Status:** Accepted
**Date:** April 12, 2026

### Context

Campaign data is deeply nested and variable in shape. A single campaign contains multiple loop cycles, and each cycle contains research findings (variable count), content variants (variable count and structure), deployment records, and feedback reports. This data is written once per stage, read as a whole document, and evolves in schema as the product matures.

### Options Considered

1. **MongoDB** — document database, stores each campaign as a single nested document.
2. **Postgres JSONB columns** — store campaign data as JSON within the existing Neon Postgres database.

### Decision

MongoDB.

### Rationale

- The campaign document model is a natural fit. A single `findOne` retrieves an entire campaign with all its loops, variants, and feedback — no joins, no N+1 queries.
- MongoDB's query language handles nested field queries natively (e.g., "find campaigns where any loop's feedback contains a winning hypothesis on LinkedIn"). The equivalent Postgres JSONB query syntax is significantly more verbose and error-prone.
- Schema flexibility is important during early product development. Adding a new field to a ResearchFinding or ContentVariant requires no migration — old documents simply lack the field.
- MongoDB supports in-place updates to specific nested fields (`$set`, `$push`), whereas Postgres rewrites the entire JSONB value on any update. For a campaign document that grows as loops are added, in-place updates are more efficient.

### Trade-offs Accepted

- **Additional operational complexity.** MongoDB is another database service to run on Railway (deployment, monitoring, backups). This is the primary cost of this decision.
- **No cross-database transactions.** If a workflow needs to atomically update both a Postgres record (e.g., user preferences) and a MongoDB document (e.g., campaign status), there's no distributed transaction. The application must handle this via eventual consistency or compensating actions.
- **Additional dependency surface.** Motor (async MongoDB driver for Python) is added to the backend dependencies alongside Prisma.

### Why Not Postgres JSONB

Postgres JSONB was a strong contender and would have eliminated the operational overhead of a second database. The deciding factors against it were:

- JSONB query syntax for deeply nested data is awkward and hard to maintain. Querying "the third loop's feedback report where a specific hypothesis outcome has confidence above 0.8" requires chained `->`, `->>`, and `jsonb_path_query` operators that are difficult to read and debug.
- Postgres rewrites the entire JSONB value on any update. A campaign document that grows over weeks (new loops appended, feedback added) would trigger increasingly large writes. MongoDB's `$push` appends to an array in-place.
- At MVP stage, the schema for campaign data will change frequently. JSONB requires no migration, but Postgres tooling (Prisma, pgAdmin) doesn't provide schema validation or autocompletion for JSONB contents. MongoDB Compass and the MongoDB VS Code extension provide this natively.

### Revisit Trigger

If operational complexity becomes a bottleneck (monitoring, backups, connection management for two databases), revisit this decision and consider migrating campaign data to Postgres JSONB. The Pydantic models that define campaign document structure make migration straightforward — serialize to JSONB instead of BSON.

---

## ADR-005: Vector Store — Self-Hosted Qdrant on Railway

**Status:** Accepted
**Date:** April 12, 2026

### Context

The platform accumulates intelligence across loop cycles — research findings, content performance data, and audience insights. Semantic search over this accumulated knowledge is core to the "each cycle starts sharper" value proposition. The Research Agent and Content Agent both need to retrieve relevant past findings and content by meaning, not just by keyword.

### Options Considered

1. **Qdrant (self-hosted on Railway)** — open-source vector database, deployed as a Docker container.
2. **Qdrant Cloud (managed)** — hosted Qdrant service.
3. **Pinecone** — fully managed vector database.
4. **pgvector (Postgres extension)** — vector search within Neon Postgres.

### Decision

Self-hosted Qdrant on Railway.

### Rationale

- Full control over the deployment, no vendor lock-in, no usage-based pricing surprises.
- Railway makes deploying a Docker image (`qdrant/qdrant`) trivial — single click, persistent volume, private network access.
- Qdrant's Python SDK is mature and well-documented, with good async support.
- Qdrant supports payload filtering alongside vector search, which is essential for scoping queries (e.g., "find research findings similar to X, but only from the last 30 days, and only for this user").
- pgvector was considered but Neon's serverless architecture adds cold-start latency to vector queries, and pgvector's indexing options (IVFFlat, HNSW) are less tunable than Qdrant's native HNSW implementation.
- Pinecone was considered but introduces vendor lock-in and usage-based costs that are hard to predict at early stage.

### Consequences

- **Positive:** No external vendor dependency. Data stays within Railway's network.
- **Positive:** Qdrant Cloud is a direct migration path if self-hosting becomes burdensome.
- **Negative:** Self-hosting means managing the Qdrant container (restarts, persistent storage, version upgrades). Railway handles most of this, but it's still a service to monitor.
- **Negative:** No managed backups. Must configure snapshot exports manually or via a cron job.

---

## ADR-006: Authentication — BetterAuth Scoped to Next.js

**Status:** Accepted
**Date:** April 12, 2026

### Context

The platform needs user authentication (email/password, social OAuth) and session management. The architecture has two application layers: Next.js (frontend + server-side) and FastAPI (backend API + agent orchestration). A decision was needed on where auth logic should live.

### Options Considered

1. **BetterAuth in both Next.js and FastAPI** — BetterAuth server runs in Next.js, FastAPI validates sessions via BetterAuth's session table in Postgres.
2. **BetterAuth scoped to Next.js only** — BetterAuth runs entirely in Next.js. FastAPI trusts authenticated user context passed via headers over a private network.
3. **Clerk or Supabase Auth** — fully managed auth service, SDK in both layers.

### Decision

Option 2 — BetterAuth scoped to Next.js. FastAPI trusts `X-User-Id` headers from Next.js over Railway's private network.

### Rationale

- BetterAuth's Python/FastAPI adapter ecosystem is thin and less mature than its Node.js SDK. Running BetterAuth session validation in FastAPI would require either a community-maintained adapter or custom middleware that directly queries the session table — both are maintenance risks for a solo founder.
- Next.js is the auth gateway. Every request to FastAPI originates from a Server Action or server-side fetch that has already authenticated the user via BetterAuth. FastAPI is not publicly exposed — it listens only on Railway's private network (`api.railway.internal:8000`). External clients cannot reach FastAPI, so they cannot forge the `X-User-Id` header.
- This keeps auth logic in BetterAuth's strongest environment (Node.js/Next.js) and keeps FastAPI focused purely on business logic and agent orchestration.

### Consequences

- **Positive:** Zero BetterAuth dependency in the Python codebase. No Python adapter to maintain.
- **Positive:** FastAPI middleware is trivially simple — read a header, reject if missing.
- **Positive:** Auth upgrades (adding OAuth providers, MFA, etc.) only touch the Next.js codebase.
- **Negative:** FastAPI cannot independently verify that a user is authenticated. It trusts Next.js entirely. This is acceptable because FastAPI is not publicly accessible, but it means the private network boundary is a security-critical assumption.
- **Negative:** If FastAPI ever needs to be exposed publicly (e.g., for a public API or mobile app), this pattern breaks and auth must be re-introduced at the FastAPI layer.

### Revisit Trigger

If a public API or mobile client needs to call FastAPI directly (bypassing Next.js), introduce token-based auth (e.g., JWT issued by BetterAuth, verified by FastAPI middleware) at that point.

---

## ADR-007: Frontend State Management — Zustand

**Status:** Accepted
**Date:** April 12, 2026

### Context

The chat interface requires managing several categories of client-side state: the SSE stream buffer (tokens accumulating into a message), chat input drafts, agent status indicators, ephemeral UI interaction state, and general UI toggles (sidebar, panels). A decision was needed on how to manage this state.

### Options Considered

1. **Zustand** — lightweight, minimal-boilerplate state management with named stores.
2. **TanStack Query** — server state management with caching, refetching, and stale-while-revalidate.
3. **React built-ins (useState, useRef)** — no external library.
4. **Redux Toolkit** — full-featured state management with actions and reducers.

### Decision

Zustand for client-side state. Server state managed by Next.js native features (Server Components, Server Actions, `revalidatePath`/`revalidateTag`).

### Rationale

The key insight is that "state management" actually covers two distinct categories, each best served by different tools:

**Server state** — data fetched from the API (conversations list, campaign history, integrations, user preferences). Next.js App Router handles this natively: Server Components fetch at render time, Server Actions handle mutations, and `revalidatePath`/`revalidateTag` handle cache invalidation. Adding TanStack Query on top of this would duplicate what Next.js already provides. TanStack Query's strengths (client-side polling, optimistic updates, infinite scroll) are more relevant in SPA architectures where there's no server rendering layer.

**Client state** — data that exists only in the browser (SSE stream buffer, input drafts, agent status, UI toggles). This is what Zustand handles. Named stores keep related state organised (a `chatStore`, a `uiStore`) without the scattered `useState` calls that become hard to trace in a complex component tree.

Redux was rejected as overkill — the boilerplate-to-value ratio is poor for a solo founder building an MVP. React built-ins (`useState`, `useRef`) were rejected because they scatter state across components, making it difficult to share state between the chat input, the stream renderer, and the agent status indicator without prop drilling or context providers.

### Consequences

- **Positive:** Minimal API surface. Zustand stores are plain functions — easy to test, easy to debug.
- **Positive:** SSR-compatible. Zustand works with Next.js App Router without hydration issues.
- **Positive:** No TanStack Query dependency. Server state is handled by the framework, reducing bundle size and dependency count.
- **Negative:** No built-in data fetching patterns (stale-while-revalidate, background refetch). If the app later needs heavy client-side data fetching (e.g., real-time dashboards with polling), TanStack Query may need to be introduced for that specific use case.

---

## ADR-008: Real-Time Communication — Server-Sent Events (SSE)

**Status:** Accepted
**Date:** April 12, 2026

### Context

Agent responses stream incrementally — tokens, tool calls, status updates, and ephemeral UI components arrive over time as the LangGraph graph executes. The frontend needs to receive these events in real-time and render them progressively.

### Options Considered

1. **Server-Sent Events (SSE)** — unidirectional server-to-client streaming over HTTP.
2. **WebSockets** — bidirectional persistent connection.
3. **Polling + webhooks** — periodic client requests for new data.

### Decision

SSE.

### Rationale

- The streaming pattern is fundamentally unidirectional: the server streams agent output to the client. The client sends user messages via standard HTTP requests (Server Actions or POST), not over the stream. WebSockets' bidirectional capability is unused overhead.
- SSE uses standard HTTP, which means it works through all proxies, load balancers, and CDNs without special configuration. WebSockets require sticky sessions for horizontal scaling — an unnecessary constraint at this stage.
- The browser's native `EventSource` API handles reconnection automatically with exponential backoff. WebSocket reconnection must be implemented manually.
- Railway's infrastructure handles SSE without additional configuration. WebSocket support on Railway requires ensuring connections aren't terminated by proxy timeouts.

### Consequences

- **Positive:** Simpler protocol, fewer failure modes, automatic reconnection.
- **Positive:** No sticky sessions needed — FastAPI can be horizontally scaled without session affinity.
- **Negative:** SSE is unidirectional. If the platform later needs server-initiated pushes that aren't part of a response stream (e.g., "a teammate just approved your campaign"), a separate notification mechanism will be needed.
- **Negative:** SSE connections count against browser connection limits (6 per domain in HTTP/1.1). Mitigated by HTTP/2 multiplexing, which Railway supports.

### Revisit Trigger

If real-time bidirectional communication becomes a requirement (e.g., collaborative editing, live team notifications), introduce WebSockets alongside SSE for that specific use case.

---

## ADR-009: Task Queue — ARQ with Redis

**Status:** Accepted
**Date:** April 12, 2026

### Context

Several operations must run outside the request-response cycle: polling channel analytics after a deployment, refreshing OAuth tokens before expiry, processing inbound webhook events, and executing scheduled deployments. A background job system is needed.

### Options Considered

1. **ARQ** — async-native Python task queue backed by Redis.
2. **Celery** — the most widely adopted Python task queue.
3. **Dramatiq** — lightweight alternative to Celery.
4. **BullMQ (Node.js)** — Redis-backed queue for the Node.js ecosystem.

### Decision

ARQ with Redis.

### Rationale

- ARQ is built on `asyncio`, matching FastAPI's async-native architecture. Celery uses a synchronous execution model by default (with optional `gevent`/`eventlet` workers), which creates friction in an async codebase.
- ARQ has minimal dependencies — it requires only Redis and the `arq` package. Celery pulls in a larger dependency tree and requires more configuration (broker, result backend, serialisation format).
- Redis is already in the stack for caching and rate limiting. ARQ adds no new infrastructure.
- BullMQ was rejected because the task workers need access to Python agent code, LLM clients, and the MongoDB/Qdrant services. Running workers in Node.js would mean duplicating business logic across languages.

### Consequences

- **Positive:** Async-native, minimal setup, no new infrastructure.
- **Positive:** Single Redis instance serves caching, rate limiting, and job queuing.
- **Negative:** ARQ is less feature-rich than Celery. No built-in task chaining, priority queues, or canvas workflows. Acceptable for the current job types (all independent, no complex dependencies).
- **Negative:** Smaller community than Celery. Fewer tutorials, fewer Stack Overflow answers. Mitigated by ARQ's simplicity — the entire library is small enough to read in an afternoon.

---

## ADR-010: Multi-LLM Provider Strategy

**Status:** Accepted
**Date:** April 12, 2026

### Context

Different agents in the growth loop have different requirements. The Research Agent needs strong synthesis and large context handling. The Content Agent needs creative writing quality. The Outreach Agent needs reliable structured tool calling. The platform also needs image generation for ad creatives and social media visuals. A single LLM provider may not be optimal for all tasks.

### Options Considered

1. **Single provider (OpenAI only)** — simplest integration, one API key, one billing relationship.
2. **Single provider (Anthropic only)** — same simplicity, different strengths.
3. **Multi-provider** — route each agent to the LLM best suited for its task.

### Decision

Multi-provider: OpenAI (GPT-4o), Anthropic (Claude Sonnet), and Google (Nano Banana 2 / Gemini 3.1 Flash Image).

### Agent-to-LLM Mapping

| Agent | LLM | Rationale |
|---|---|---|
| Supervisor | Claude Sonnet | Reliable instruction following, strong at routing decisions |
| Research | GPT-4o | Strong synthesis across large context windows, structured extraction |
| Content | Claude Sonnet | Superior creative writing quality, nuanced tone control |
| Outreach | GPT-4o | Reliable structured tool calling for API integrations |
| Feedback | GPT-4o | Data analysis, structured output generation |
| UI Agent | Claude Sonnet | Precise schema generation for ephemeral UI components |
| Image Gen | Nano Banana 2 | Fast, cost-effective, strong text rendering for ad creatives |

### Consequences

- **Positive:** Each agent uses the model best suited for its task. The Content Agent produces higher-quality creative writing with Claude; the Outreach Agent makes more reliable tool calls with GPT-4o.
- **Positive:** No single-provider dependency. If one provider has an outage, agents on other providers continue working.
- **Positive:** Nano Banana 2 provides image generation at roughly half the cost of comparable models, with strong text rendering for marketing assets.
- **Negative:** Three API keys, three billing relationships, three sets of rate limits to manage.
- **Negative:** Debugging is harder — a single conversation may invoke three different providers. Mitigated by LangSmith tracing, which captures every LLM call regardless of provider.
- **Negative:** LLM routing logic adds complexity. The `llm_router` service must be maintained as models are updated or deprecated.

### Revisit Trigger

If model capabilities converge (e.g., a future GPT or Claude model excels at both creative writing and tool calling), simplify to a single provider to reduce operational complexity.

---

## ADR-011: Deployment Platform — Railway with Railpack

**Status:** Accepted
**Date:** April 12, 2026

### Context

The platform consists of multiple services (Next.js, FastAPI, ARQ worker, Redis, Qdrant, MongoDB) that need to communicate over a private network. As a solo founder, operational simplicity is paramount — the deployment platform should handle networking, scaling, health checks, and secret management without requiring Kubernetes, Terraform, or cloud-provider expertise.

### Options Considered

1. **Railway with Railpack** — platform-as-a-service with auto-detection builds, private networking, and monorepo support.
2. **Vercel (Next.js) + Fly.io (FastAPI)** — split deployment across two platforms.
3. **AWS (ECS/Fargate)** — container orchestration on AWS.
4. **Render** — PaaS alternative to Railway.

### Decision

Railway with Railpack for all services.

### Rationale

- Railway supports monorepo deployments — each service points to a subdirectory in the same repo. Railpack auto-detects Next.js and Python builds without custom Dockerfiles.
- Private networking between services is built-in. FastAPI, Redis, Qdrant, and MongoDB communicate over `*.railway.internal` hostnames without exposing ports publicly.
- The Vercel + Fly.io split was rejected because it puts the frontend and backend on different platforms with different networking, billing, and deployment workflows. Coordinating deploys across two platforms adds friction for a solo founder.
- AWS was rejected as overkill. ECS/Fargate requires IAM configuration, VPC setup, security groups, and load balancer management — all solvable but disproportionate for an MVP.
- Render was considered but Railway's private networking and monorepo support are more mature.

### Consequences

- **Positive:** Single platform, single billing, single deployment workflow for all services.
- **Positive:** Railpack eliminates Dockerfile maintenance for the primary services.
- **Positive:** Private networking keeps FastAPI, Redis, Qdrant, and MongoDB off the public internet.
- **Negative:** Railway is a smaller platform than AWS or Vercel. Fewer regions, fewer integrations, smaller community. Acceptable at current scale.
- **Negative:** Vendor lock-in to Railway's deployment model. Mitigated by the fact that all services are standard containers — migrating to Fly.io, Render, or AWS ECS requires writing Dockerfiles but no code changes.

---

## ADR-012: Web Search for Research Agent — Tavily

**Status:** Accepted
**Date:** April 12, 2026

### Context

The Research Agent needs to search the web for competitive intelligence, market signals, audience discussions, and trending topics. It needs a search API that returns structured results with content extraction, not just links.

### Options Considered

1. **Tavily** — search API purpose-built for AI agents, returns extracted content alongside results.
2. **SerpAPI / Serper** — Google search result scrapers, return SERP data.
3. **Brave Search API** — privacy-focused search API.

### Decision

Tavily.

### Rationale

- Tavily is designed specifically for LLM agent workflows. It returns pre-extracted content from search results, reducing the need for a separate scraping/extraction step.
- Tavily's `search` and `extract` tools integrate natively with LangChain/LangGraph.
- SerpAPI returns raw SERP data (titles, snippets, links) but requires a separate step to fetch and extract content from each result page. This adds latency and complexity.
- Brave Search API was considered but its content extraction capabilities are less mature than Tavily's.

### Consequences

- **Positive:** Fewer tool calls per research query — Tavily handles search + extraction in one call.
- **Positive:** Native LangChain integration reduces boilerplate.
- **Negative:** Tavily is a smaller, newer company than Google (SerpAPI) or Brave. Availability and long-term viability are less certain.
- **Negative:** Tavily's pricing is usage-based, which can be unpredictable if the Research Agent makes many queries per loop cycle.

---

## ADR-013: Image Generation — Nano Banana 2 (Gemini 3.1 Flash Image)

**Status:** Accepted
**Date:** April 12, 2026

### Context

The Content Agent needs to generate visual assets for ad creatives, social media posts, and campaign materials. Generated images need accurate text rendering (headlines, CTAs), support for multiple aspect ratios (social post, banner, story), and fast iteration.

### Options Considered

1. **Nano Banana 2 (Gemini 3.1 Flash Image)** — Google's latest image model, fast generation, strong text rendering.
2. **DALL-E 3 (OpenAI)** — integrated with the OpenAI ecosystem.
3. **Flux** — open-source diffusion model.
4. **Midjourney API** — high-quality artistic generation.

### Decision

Nano Banana 2.

### Rationale

- Text rendering is critical for marketing assets (headlines on ads, CTAs on social images). Nano Banana 2 uses a multimodal LLM architecture rather than diffusion, which gives it character-level text understanding and accurate rendering — a known weakness of diffusion-based models like DALL-E 3 and Flux.
- Cost is approximately $0.067 per image, roughly half the price of comparable models.
- Supports 14 aspect ratios and resolutions from 512px to 4K, covering all common marketing asset dimensions without separate generation passes.
- Up to 14 reference images per prompt enables maintaining visual consistency across a campaign.
- Available via the Google Generative AI API, which is straightforward to integrate.

### Consequences

- **Positive:** Accurate text in generated images, critical for ad creatives and social cards.
- **Positive:** Cost-effective, fast generation (Flash-tier latency).
- **Positive:** Multiple aspect ratios in a single model reduces the need for post-processing.
- **Negative:** Google's content safety filters can be aggressive, sometimes blocking legitimate marketing images. May require prompt engineering to work around false positives.
- **Negative:** Adds Google as a third API provider alongside OpenAI and Anthropic.

---

## ADR-014: LangGraph Checkpointing — Neon Postgres

**Status:** Accepted
**Date:** April 12, 2026

### Context

LangGraph graphs can be interrupted (e.g., waiting for user approval before deploying content) and must resume exactly where they left off. State must persist across server restarts and session disconnects. LangGraph supports multiple checkpoint backends.

### Options Considered

1. **Postgres (Neon)** — LangGraph's `AsyncPostgresSaver`, using the existing Neon database.
2. **SQLite** — LangGraph's default file-based checkpointer.
3. **Redis** — custom checkpoint backend.

### Decision

Neon Postgres via `AsyncPostgresSaver`.

### Rationale

- Neon Postgres is already in the stack. No new service required.
- Postgres checkpoints survive server restarts, container redeployments, and Railway service updates. SQLite on a container filesystem would be lost on redeploy.
- LangGraph's Postgres checkpointer is officially supported and well-tested.
- Redis could work but checkpoint data is not ephemeral — losing it means losing in-progress conversations. Postgres provides stronger durability guarantees.

### Consequences

- **Positive:** Zero additional infrastructure. Checkpoints share the Neon database.
- **Positive:** Checkpoints are queryable SQL — useful for debugging stuck conversations.
- **Negative:** Adds load to Neon. Each graph step writes a checkpoint. Mitigated by Neon's serverless autoscaling.

---

## ADR-015: Channel Integration Pattern — Adapter Abstraction

**Status:** Accepted
**Date:** April 12, 2026

### Context

The platform integrates with multiple channels (LinkedIn, SendGrid, Meta, Google Ads, X) for outreach deployment and feedback ingestion. Each channel has a different API, different authentication flow, different data formats, and different rate limits. The Outreach and Feedback agents need to interact with these channels without being coupled to specific API implementations.

### Decision

All channel integrations implement a common `ChannelAdapter` interface with four methods: `authenticate`, `publish`, `get_analytics`, and `health_check`. Each channel has a concrete implementation. The agent tools call the adapter interface, not the channel API directly.

### Rationale

- Adding a new channel means implementing one interface — no changes to agent code, tool definitions, or graph logic.
- Channel-specific quirks (rate limits, pagination, error codes) are encapsulated within the adapter, not scattered across agent implementations.
- Testing is simplified — adapters can be mocked for agent testing without hitting live APIs.

### Consequences

- **Positive:** Clean separation between agent logic and channel API details.
- **Positive:** New channels are additive — implement the adapter, register it, and the agents can use it immediately.
- **Negative:** The adapter interface must be general enough to accommodate all channels. Some channels may have capabilities (e.g., Meta's ad targeting options) that don't fit cleanly into a generic `publish` method. These are handled via channel-specific `metadata` parameters.

---

## ADR-016: Node.js Package Manager — pnpm

**Status:** Accepted
**Date:** April 12, 2026

### Context

The Next.js application and any shared TypeScript packages need a Node.js package manager for dependency installation, script execution, and lockfile management.

### Options Considered

1. **pnpm** — fast, disk-efficient package manager using a content-addressable store and symlinks.
2. **npm** — the default Node.js package manager.
3. **yarn (v4 / Berry)** — alternative package manager with Plug'n'Play support.

### Decision

pnpm.

### Rationale

- pnpm is the fastest Node.js package manager for both install and CI. Its content-addressable store means packages are stored once on disk and symlinked into each project, significantly reducing disk usage and install times compared to npm's flat `node_modules`.
- Strict dependency resolution by default — pnpm does not hoist packages to the root `node_modules` the way npm does, which prevents "phantom dependency" bugs where code accidentally imports a transitive dependency that isn't declared in `package.json`.
- Native workspace support if the monorepo later adopts a workspace structure for shared packages.
- Railway's Railpack auto-detects `pnpm-lock.yaml` and uses pnpm for builds without additional configuration.

### Consequences

- **Positive:** Faster installs, smaller `node_modules`, stricter dependency resolution.
- **Positive:** Railway and most CI platforms support pnpm natively.
- **Negative:** Slightly less ubiquitous than npm. Some tutorials and tools assume npm. Symlinked `node_modules` can occasionally cause issues with tools that don't follow symlinks correctly — rare with modern tooling but worth noting.

---

## ADR-017: Python Package Manager — uv

**Status:** Accepted
**Date:** April 12, 2026

### Context

The FastAPI application and ARQ worker need a Python package manager for dependency installation, virtual environment management, and lockfile generation. The Python dependency ecosystem is notoriously slow — `pip install` on a moderately complex project can take minutes.

### Options Considered

1. **uv** — Rust-based Python package manager and project tool. Drop-in replacement for pip, pip-tools, and virtualenv.
2. **pip + pip-tools** — traditional Python dependency management with manual lockfile generation.
3. **Poetry** — all-in-one Python dependency management and packaging.
4. **PDM** — PEP 621-compliant Python package manager.

### Decision

uv.

### Rationale

- uv is 10–100x faster than pip for dependency resolution and installation. For a solo founder iterating quickly, the difference between a 2-second and a 60-second install cycle is significant.
- uv replaces multiple tools: it handles virtual environment creation (`uv venv`), dependency installation (`uv pip install`), lockfile generation (`uv lock`), and project management (`uv run`) — all in one binary.
- uv uses `pyproject.toml` as the single configuration file, aligning with modern Python packaging standards (PEP 621). No separate `requirements.txt`, `setup.py`, or `setup.cfg`.
- uv generates a cross-platform lockfile (`uv.lock`) that ensures deterministic builds across development, CI, and Railway deployment.
- Poetry was considered but its dependency resolver is slower than uv's, and its custom `pyproject.toml` format predates PEP 621 compliance (though recent versions have improved this).

### Consequences

- **Positive:** Dramatically faster installs — both locally and in Railway CI/CD builds.
- **Positive:** Single tool replaces pip, pip-tools, virtualenv, and pyenv.
- **Positive:** Deterministic lockfile for reproducible deployments.
- **Negative:** uv is newer than pip and Poetry. Some edge cases with legacy packages or non-standard build systems may require workarounds.
- **Negative:** Railway's Railpack may need a custom build command to use uv instead of pip. This is a one-line configuration: `uv sync` in the build step.

---

## ADR-018: No Docker — Cloud Free Tiers for Local Development

**Status:** Accepted
**Date:** April 12, 2026

### Context

Local development requires access to Redis, MongoDB, and Qdrant. The conventional approach is a `docker-compose.yml` that runs all three services as containers. However, the solo founder has limited Docker experience, and Docker adds setup friction (installing Docker Desktop, understanding volumes, managing container lifecycles, debugging networking issues between containers).

### Options Considered

1. **Docker Compose** — run Redis, MongoDB, and Qdrant as local containers.
2. **Cloud free tiers** — use managed free tiers (Upstash Redis, MongoDB Atlas M0, Qdrant Cloud 1GB) for local development, connected via URL.
3. **Native local installs** — install Redis, MongoDB, and Qdrant directly on the development machine via package managers (brew, apt).

### Decision

Option 2 — cloud free tiers as the primary local development approach, with native installs documented as an offline fallback.

### Rationale

- Zero local infrastructure management. No Docker installation, no container lifecycle, no volume mounts, no port conflicts. Signing up for three free tiers takes 15 minutes and produces three connection strings.
- The local dev environment mirrors production more closely — both use managed services accessed via URLs, rather than locally-running containers that may behave differently (version skew, configuration differences, networking).
- Free tier limits are generous enough for solo development: Upstash allows 10,000 Redis commands/day, MongoDB Atlas M0 provides 512MB storage, Qdrant Cloud provides 1GB. A solo founder in development will not hit these limits.
- Native installs (brew, apt) are documented as a fallback for offline development — no Docker needed for that path either.

### Trade-offs Accepted

- **Internet dependency.** Local development requires a network connection to reach cloud services. Mitigated by the native install fallback for offline work.
- **Shared dev data.** If the free-tier instances are used by multiple environments (e.g., dev laptop + CI), data can collide. Mitigated by using separate database names or prefixed keys per environment.
- **Latency.** Cloud services add network round-trip latency to every database call during development (typically 20–100ms). Acceptable for development — not noticeable in practice since the LLM API calls dominate latency.

### Production Impact

None. Production services on Railway are unaffected. Docker was never part of the production deployment — Railpack handles builds, and Railway templates handle Redis/MongoDB/Qdrant. This decision only affects the local development workflow.

---

## Summary Table

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Monorepo (no workspace tooling) | Accepted |
| ADR-002 | LangGraph for agent orchestration | Accepted |
| ADR-003 | Neon Postgres + Prisma for primary DB | Accepted |
| ADR-004 | MongoDB for campaign data | Accepted |
| ADR-005 | Self-hosted Qdrant on Railway | Accepted |
| ADR-006 | BetterAuth scoped to Next.js | Accepted |
| ADR-007 | Zustand for client state, Next.js native for server state | Accepted |
| ADR-008 | SSE for real-time streaming | Accepted |
| ADR-009 | ARQ + Redis for background jobs | Accepted |
| ADR-010 | Multi-LLM provider (OpenAI + Anthropic + Google) | Accepted |
| ADR-011 | Railway + Railpack for deployment | Accepted |
| ADR-012 | Tavily for web search | Accepted |
| ADR-013 | Nano Banana 2 for image generation | Accepted |
| ADR-014 | LangGraph checkpointing to Neon Postgres | Accepted |
| ADR-015 | Adapter pattern for channel integrations | Accepted |
| ADR-016 | pnpm for Node.js package management | Accepted |
| ADR-017 | uv for Python package management | Accepted |
| ADR-018 | No Docker — cloud free tiers for local dev | Accepted |

---

*This is a living document. New ADRs will be appended as architectural decisions are made during implementation.*
