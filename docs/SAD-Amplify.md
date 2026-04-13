# Solution Architecture Document: Amplify

**Version:** 1.1
**Date:** April 12, 2026
**Author:** Gayashan
**Status:** Draft — Revised (auth scoped to Next.js, MongoDB confirmed)

---

## 1. Document Purpose

This document defines the technical architecture for the Amplify — a conversational, AI-powered system that executes the full marketing growth loop (Research → Content → Outreach → Feedback) within a single interface. It covers system topology, service boundaries, data flows, agent orchestration, integration patterns, and deployment strategy.

---

## 2. Architecture Principles

The following principles guide every architectural decision:

**Conversation-first, not dashboard-first.** The chat interface is the primary workspace. The web shell supports it — not the other way around.

**Agents are specialists, not generalists.** Each stage of the growth loop is handled by a dedicated agent with its own tools, prompts, and output schemas. The supervisor routes; agents execute.

**Structured state over freeform text.** All agent outputs — research findings, content variants, campaign records, feedback — are typed, versioned, and queryable. Nothing important lives as unstructured chat history alone.

**Stream everything.** Agent reasoning, tool calls, and partial results stream to the frontend via SSE. Users never stare at a spinner wondering what is happening.

**Fail visibly.** When an agent fails, a tool errors, or an API is down, the system surfaces the failure clearly in the conversation with a suggested next step — never silently drops context.

**Solo-founder viable.** Every infrastructure choice favours managed services, minimal ops burden, and a single monorepo. Complexity is pushed into LangGraph's graph definition, not into deployment topology.

---

## 3. High-Level System Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                          RAILWAY CLOUD                             │
│                                                                    │
│  ┌──────────────────────┐      ┌──────────────────────────────┐    │
│  │    Next.js App        │      │       FastAPI Backend         │    │
│  │    (Railpack)         │      │       (Railpack)              │    │
│  │                       │      │                               │    │
│  │  - SSR Pages          │ SSE  │  - REST API (/api/v1/*)       │    │
│  │  - Server Actions     │◀────▶│  - SSE Endpoint (/stream)     │    │
│  │  - Chat UI            │      │  - Webhook Receivers          │    │
│  │  - Ephemeral UI       │      │                               │    │
│  │  - Shadcn Components  │      │  (Auth: trusts X-User-Id      │    │
│  │  - BetterAuth (auth   │      │   from Next.js over private   │    │
│  │    gateway)            │      │   network)                    │    │
│  └──────────────────────┘      │  ┌───────────────────────┐    │    │
│                                 │  │   LangGraph Runtime    │    │    │
│                                 │  │                        │    │    │
│                                 │  │  Supervisor Agent      │    │    │
│                                 │  │  ├─ Research Agent     │    │    │
│                                 │  │  ├─ Content Agent      │    │    │
│                                 │  │  ├─ Outreach Agent     │    │    │
│                                 │  │  ├─ Feedback Agent     │    │    │
│                                 │  │  └─ UI Agent           │    │    │
│                                 │  └───────────────────────┘    │    │
│                                 └──────────────────────────────┘    │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │    Redis      │  │   Qdrant     │  │  MongoDB     │              │
│  │  (Queue +     │  │  (Vector     │  │  (Campaign   │              │
│  │   Cache)      │  │   Store)     │  │   History)   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                    │
│                    ┌──────────────┐                                 │
│                    │  Neon        │                                 │
│                    │  Postgres    │                                 │
│                    │  (Primary DB)│                                 │
│                    └──────────────┘                                 │
└─────────────────────────────────────────────────────────────────────┘
         │                    │                     │
         ▼                    ▼                     ▼
  ┌─────────────┐   ┌──────────────┐    ┌──────────────────┐
  │ LLM APIs    │   │ Channel APIs │    │ Signal Sources   │
  │             │   │              │    │                  │
  │ - OpenAI    │   │ - LinkedIn   │    │ - Tavily Search  │
  │ - Anthropic │   │ - SendGrid   │    │ - Meta Ad Library│
  │ - Gemini    │   │ - Meta Graph │    │ - Google Trends  │
  │ - Nano      │   │ - Google Ads │    │ - Reddit API     │
  │   Banana 2  │   │ - X API v2   │    │ - Crunchbase     │
  └─────────────┘   └──────────────┘    └──────────────────┘

                    ┌──────────────┐
                    │  LangSmith   │
                    │  (Tracing &  │
                    │   Evals)     │
                    └──────────────┘
```

---

## 4. Monorepo Structure

```
amplify/
├── apps/
│   ├── web/                          # Next.js application
│   │   ├── app/                      # App Router
│   │   │   ├── (auth)/               # Auth pages (login, signup)
│   │   │   ├── (dashboard)/          # Dashboard layout group
│   │   │   │   ├── chat/             # Chat interface (primary workspace)
│   │   │   │   ├── campaigns/        # Campaign history & timeline
│   │   │   │   ├── integrations/     # Channel connections & API keys
│   │   │   │   └── settings/         # User & team settings
│   │   │   ├── api/                  # Next.js API routes (BetterAuth, proxies)
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── chat/                 # Chat UI components
│   │   │   │   ├── message-list.tsx
│   │   │   │   ├── message-input.tsx
│   │   │   │   ├── agent-status.tsx  # Shows which agent is active
│   │   │   │   └── stream-renderer.tsx
│   │   │   ├── ephemeral/            # Ephemeral UI components
│   │   │   │   ├── variant-grid.tsx
│   │   │   │   ├── quick-poll.tsx
│   │   │   │   ├── performance-map.tsx
│   │   │   │   ├── approval-flow.tsx
│   │   │   │   └── intelligence-brief.tsx
│   │   │   ├── dashboard/            # Dashboard components
│   │   │   └── ui/                   # Shadcn base components
│   │   ├── lib/
│   │   │   ├── auth.ts               # BetterAuth client config
│   │   │   ├── auth-server.ts        # BetterAuth server config (sessions, adapters)
│   │   │   ├── sse-client.ts         # SSE connection manager
│   │   │   ├── api-client.ts         # Typed API client (calls FastAPI with X-User-Id)
│   │   │   └── stores/               # Zustand stores (chat, campaign state)
│   │   ├── tailwind.config.ts
│   │   ├── next.config.ts
│   │   ├── package.json
│   │   └── pnpm-lock.yaml
│   │
│   └── api/                          # FastAPI application
│       ├── main.py                   # FastAPI app entry point
│       ├── routers/
│       │   ├── chat.py               # Chat + SSE streaming endpoints
│       │   ├── campaigns.py          # Campaign CRUD
│       │   ├── integrations.py       # Channel integration management
│       │   └── webhooks.py           # Inbound webhooks from channels
│       ├── agents/
│       │   ├── graph.py              # LangGraph graph definition
│       │   ├── supervisor.py         # Supervisor agent (router)
│       │   ├── research.py           # Research agent
│       │   ├── content.py            # Content agent
│       │   ├── outreach.py           # Outreach agent
│       │   ├── feedback.py           # Feedback agent
│       │   └── ui_agent.py           # Ephemeral UI generation agent
│       ├── tools/                    # Agent tool definitions
│       │   ├── tavily_search.py
│       │   ├── linkedin.py
│       │   ├── email_sendgrid.py
│       │   ├── meta_ads.py
│       │   ├── google_ads.py
│       │   ├── twitter.py
│       │   └── image_gen.py          # Nano Banana 2 integration
│       ├── models/                   # Pydantic models (shared types)
│       │   ├── research.py           # ResearchFinding, IntelligenceBrief
│       │   ├── content.py            # ContentVariant, CampaignBrief
│       │   ├── outreach.py           # DeploymentRecord, ABTest
│       │   ├── feedback.py           # EngagementMetrics, ResonanceReport
│       │   └── ephemeral.py          # EphemeralUI component schemas
│       ├── services/
│       │   ├── llm_router.py         # Multi-provider LLM routing
│       │   ├── vector_store.py       # Qdrant operations
│       │   ├── campaign_store.py     # MongoDB campaign history
│       │   ├── queue.py              # Redis job queue (ARQ)
│       │   └── channel_manager.py    # Channel integration abstraction
│       ├── db/
│       │   └── prisma/
│       │       └── schema.prisma     # Prisma schema for Neon Postgres
│       ├── config.py                 # Settings (env vars, secrets)
│       ├── pyproject.toml            # uv project config + dependencies
│       └── uv.lock                   # uv lockfile (deterministic builds)
│
├── packages/
│   └── shared-types/                 # Shared TypeScript types (if needed)
│       └── index.ts
│
├── prisma/
│   └── schema.prisma                 # Symlinked or shared Prisma schema
│
├── railway.toml                      # Railway deployment config
├── .env.example
├── .env.local                        # Local dev env vars (git-ignored)
└── README.md
```

---

## 5. Frontend Architecture

### 5.1 Technology Stack

| Concern | Choice | Rationale |
|---|---|---|
| Framework | Next.js 15 (App Router) | SSR for initial load, Server Actions for mutations, streaming support |
| Styling | Tailwind CSS 4 | Utility-first, pairs with Shadcn |
| Components | Shadcn/ui | Accessible, composable, no vendor lock-in |
| State | Zustand | Lightweight, works with SSR, good for chat state |
| Auth | BetterAuth (client + server) | Full auth lifecycle in Next.js; FastAPI trusts user context via X-User-Id header |
| SSE | EventSource API + custom reconnect | Native browser support, auto-reconnect with backoff |

### 5.2 Chat Interface Architecture

The chat is the primary workspace. It handles three types of content:

**Text messages** — standard conversational turns between user and system.

**Agent status indicators** — real-time display of which agent is active and what it is doing (e.g., "Research Agent → Searching competitor ads...").

**Ephemeral UI blocks** — structured interactive components rendered inline within the message stream.

#### SSE Stream Protocol

The frontend opens a persistent SSE connection to `POST /api/v1/chat/stream`. The backend emits typed events:

```typescript
// Event types from the SSE stream
type StreamEvent =
  | { type: "agent_start"; agent: AgentName; description: string }
  | { type: "agent_end"; agent: AgentName }
  | { type: "text_delta"; content: string }           // Streamed text token
  | { type: "tool_call"; tool: string; input: object } // Agent calling a tool
  | { type: "tool_result"; tool: string; output: object }
  | { type: "ephemeral_ui"; component: EphemeralComponent } // Render inline UI
  | { type: "error"; message: string; recoverable: boolean }
  | { type: "done"; summary: string }
```

The `stream-renderer.tsx` component switches on `event.type` and renders the appropriate UI: text accumulation for `text_delta`, status badges for `agent_start/end`, and Shadcn-based components for `ephemeral_ui`.

### 5.3 Ephemeral UI Components

Ephemeral components are defined as typed schemas emitted by the UI Agent. The frontend maps each schema to a pre-built Shadcn component:

| Schema Type | Component | Use Case |
|---|---|---|
| `variant_grid` | `<VariantGrid />` | Side-by-side A/B content comparison |
| `quick_poll` | `<QuickPoll />` | Single-click selection (channel, tone, etc.) |
| `checklist` | `<Checklist />` | Multi-select (competitors, segments) |
| `approval_flow` | `<ApprovalFlow />` | Review and approve content before deployment |
| `intelligence_brief` | `<IntelligenceBrief />` | Structured research findings with confidence |
| `performance_map` | `<PerformanceMap />` | Channel-by-channel engagement breakdown |
| `campaign_timeline` | `<CampaignTimeline />` | Visual history of loop cycles |

When the user interacts with an ephemeral component (clicks approve, selects an option, edits content), the response is sent back to the backend via a Server Action, which injects it into the LangGraph state as a user input event.

### 5.4 Pages and Routing

| Route | Purpose | Rendering |
|---|---|---|
| `/` | Landing / marketing page | SSR (static) |
| `/login`, `/signup` | Auth flows | SSR |
| `/chat` | Primary chat workspace | SSR shell, client-side streaming |
| `/chat/[conversationId]` | Specific conversation thread | SSR shell, hydrate from API |
| `/campaigns` | Campaign history & timeline | SSR with data fetching |
| `/campaigns/[id]` | Campaign detail view | SSR |
| `/integrations` | Connected channels management | SSR |
| `/settings` | User preferences, API keys, team | SSR |

---

## 6. Backend Architecture

### 6.1 Technology Stack

| Concern | Choice | Rationale |
|---|---|---|
| Framework | FastAPI | Async-native, SSE support, Pydantic integration |
| ORM | Prisma (via prisma-client-py) | Type-safe queries, Neon Postgres compatibility |
| Agent Framework | LangGraph | Stateful graph orchestration, built-in checkpointing |
| Observability | LangSmith | Trace every agent run, tool call, and LLM invocation |
| Task Queue | ARQ (async Redis queue) | Lightweight, async-native, Redis-backed |
| Auth | None (delegated to Next.js) | BetterAuth runs in Next.js; FastAPI trusts X-User-Id header over private network |

### 6.2 API Design

The backend exposes three categories of endpoints:

**Chat & Streaming**

```
POST   /api/v1/chat/stream          # SSE endpoint — sends user message, streams agent response
POST   /api/v1/chat/ephemeral       # User response to an ephemeral UI component
GET    /api/v1/chat/conversations    # List conversations
GET    /api/v1/chat/conversations/{id}  # Get conversation with messages
DELETE /api/v1/chat/conversations/{id}  # Archive conversation
```

**Campaigns**

```
GET    /api/v1/campaigns             # List campaigns (paginated)
GET    /api/v1/campaigns/{id}        # Campaign detail with loop history
GET    /api/v1/campaigns/{id}/performance  # Aggregated metrics
```

**Integrations**

```
GET    /api/v1/integrations          # List connected channels
POST   /api/v1/integrations/{channel}/connect    # Start OAuth flow
DELETE /api/v1/integrations/{channel}/disconnect  # Revoke access
GET    /api/v1/integrations/{channel}/status      # Health check
```

**Webhooks (inbound)**

```
POST   /api/v1/webhooks/sendgrid     # Email engagement events
POST   /api/v1/webhooks/linkedin     # LinkedIn interaction events
POST   /api/v1/webhooks/meta         # Meta conversion events
```

### 6.3 Authentication Flow

BetterAuth lives entirely in Next.js. FastAPI has no direct auth logic — it trusts the authenticated context passed from Next.js over Railway's private network.

```
User → Next.js (BetterAuth React SDK)
         → Server Actions / API Routes (/api/auth/*)
              → BetterAuth server-side (Node.js)
                   → Neon Postgres (users, sessions via Prisma)

Next.js → FastAPI (server-to-server, private network):
  → Server Action authenticates user via BetterAuth
  → Calls FastAPI with X-User-Id header (trusted, not publicly reachable)
  → FastAPI reads X-User-Id, attaches to request context
```

**Why this works securely:** FastAPI is not publicly exposed. It listens only on Railway's private network (`api.railway.internal:8000`). External clients cannot reach FastAPI directly, so they cannot forge the `X-User-Id` header. Only Next.js — which has already authenticated the user — can make requests to FastAPI.

**FastAPI middleware (simplified):**
```python
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Webhook endpoints skip auth (validated by HMAC signature instead)
    if request.url.path.startswith("/api/v1/webhooks"):
        return await call_next(request)

    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return JSONResponse(status_code=401, content={"detail": "Missing user context"})

    request.state.user_id = user_id
    return await call_next(request)
```

This eliminates any dependency on BetterAuth in the Python ecosystem and keeps auth logic in BetterAuth's strongest environment (Node.js/Next.js).

### 6.4 SSE Streaming Implementation

```python
# Simplified SSE endpoint structure
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, user_id: str = Depends(get_user_id)):
    # user_id extracted from X-User-Id header by middleware
    async def event_generator():
        # Initialize LangGraph with user's conversation state
        config = {"configurable": {"thread_id": request.conversation_id}}

        async for event in graph.astream_events(
            {"messages": [HumanMessage(content=request.message)]},
            config=config,
            version="v2"
        ):
            # Transform LangGraph events into typed SSE events
            sse_event = transform_event(event)
            yield f"event: {sse_event.type}\ndata: {sse_event.json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Railway/nginx buffering
        }
    )
```

---

## 7. Agent Architecture (LangGraph)

### 7.1 Graph Definition

The LangGraph state graph defines the orchestration of all agents. The supervisor acts as the entry point and router.

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌─────│  Supervisor │─────┐
              │     └──────┬──────┘     │
              │            │            │
     ┌────────▼───┐ ┌──────▼──────┐ ┌──▼─────────┐
     │  Research   │ │  Content    │ │  Outreach   │
     │  Agent      │ │  Agent      │ │  Agent      │
     └────────┬───┘ └──────┬──────┘ └──┬─────────┘
              │            │            │
              │     ┌──────▼──────┐     │
              └────▶│  Feedback   │◀────┘
                    │  Agent      │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Supervisor │ (re-enters for next action or END)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    END      │
                    └─────────────┘

    * UI Agent is invoked as a sub-graph by any agent
      when structured user interaction is needed
```

### 7.2 Graph State Schema

```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AmplifyState(TypedDict):
    # Conversation messages (append-only via reducer)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Current stage of the growth loop
    current_stage: str  # "research" | "content" | "outreach" | "feedback" | "idle"

    # Structured outputs from each stage
    research_findings: list[ResearchFinding]      # Typed findings with confidence
    content_variants: list[ContentVariant]         # Generated content with hypotheses
    deployment_records: list[DeploymentRecord]     # What was sent, where, when
    feedback_reports: list[FeedbackReport]          # Engagement data + analysis

    # Campaign context
    campaign_id: str | None
    campaign_brief: CampaignBrief | None

    # User context (loaded at session start)
    user_context: UserContext                       # Brand, audience, preferences

    # Control flow
    pending_user_input: EphemeralUIRequest | None   # Waiting for ephemeral UI response
    next_agent: str | None                          # Supervisor's routing decision
    error_state: ErrorContext | None                # Current error, if any
```

### 7.3 Agent Specifications

#### Supervisor Agent

**Role:** Intent detection, routing, state management, loop orchestration.

**LLM:** Claude Sonnet (strong instruction following, reliable routing)

**Behaviour:**
- Parses each user message to determine intent: research request, content request, outreach directive, feedback query, general question, or continuation of current stage
- Routes to the appropriate specialist agent
- Manages transitions between loop stages
- Detects when to invoke the UI Agent for clarification or structured output
- Decides when the loop is complete (END) or should cycle back

**Routing logic (conditional edges):**
```python
def route_supervisor(state: AmplifyState) -> str:
    if state["pending_user_input"]:
        return "wait_for_input"     # Pause graph, wait for ephemeral UI response
    if state["error_state"]:
        return "handle_error"
    return state["next_agent"]       # "research" | "content" | "outreach" | "feedback" | "end"
```

#### Research Agent

**Role:** Multi-source intelligence gathering and synthesis.

**LLM:** GPT-4o (strong at synthesis and structured extraction)

**Tools:**
- `tavily_search` — Web search with query decomposition
- `tavily_extract` — Extract structured data from URLs
- `meta_ad_library` — Search competitor ad creatives
- `google_trends` — Trend data for topics and keywords
- `qdrant_search` — Query accumulated intelligence from past cycles

**Output schema:**
```python
class ResearchFinding(BaseModel):
    id: str
    category: str          # "competitive" | "market" | "audience" | "channel" | "temporal"
    claim: str             # The finding itself
    confidence: float      # 0.0 to 1.0
    sources: list[Source]  # Where this came from
    timestamp: datetime
    actionable: bool       # Can this directly inform content/outreach?
    suggested_action: str | None
```

**Behaviour:**
- Decomposes complex research queries into parallel sub-queries
- Bounded depth budget: max 3 hops per sub-query, 30-second timeout per tool call
- Synthesises findings into an `IntelligenceBrief` and surfaces via the UI Agent
- Stores findings in Qdrant (vectorised) and MongoDB (structured)

#### Content Agent

**Role:** Generate deployment-ready content grounded in research findings.

**LLM:** Claude Sonnet (strong at creative writing with constraints)

**Image generation:** Nano Banana 2 / Gemini 3.1 Flash Image (ad creatives, social media visuals)

**Tools:**
- `generate_variants` — Create A/B content variants with hypotheses
- `nano_banana_generate` — Generate ad creatives and visual assets
- `qdrant_search` — Pull relevant past content and performance data
- `brand_context` — Load user's brand voice, tone, and style guide

**Output schema:**
```python
class ContentVariant(BaseModel):
    id: str
    variant_label: str            # "A" | "B" | "C"
    channel: str                  # "linkedin" | "email" | "facebook" | "google_ads" | "twitter"
    content_type: str             # "post" | "email" | "ad_copy" | "script"
    headline: str | None
    body: str
    cta: str | None
    visual_asset_url: str | None  # Nano Banana 2 generated image URL
    hypothesis: str               # What this variant tests
    target_segment: str
    grounded_in: list[str]        # IDs of ResearchFindings this is based on
```

**Behaviour:**
- Always generates at least 2 variants per content request
- Each variant has an explicit, testable hypothesis
- Content traces back to specific research findings via `grounded_in`
- Surfaces variants via the UI Agent's `variant_grid` for user review and approval
- Generates visual assets via Nano Banana 2 when the content type warrants it (ad creatives, social posts with images)

#### Outreach Agent

**Role:** Deploy approved content across connected channels.

**LLM:** GPT-4o (reliable tool calling for API integrations)

**Tools:**
- `linkedin_post` — Publish to LinkedIn (posts, articles)
- `linkedin_message` — Send LinkedIn direct messages
- `sendgrid_send` — Send emails via SendGrid
- `meta_post` — Publish to Facebook/Instagram
- `meta_ads_create` — Create Meta ad campaigns
- `google_ads_create` — Create Google Ads campaigns
- `twitter_post` — Post to X

**Output schema:**
```python
class DeploymentRecord(BaseModel):
    id: str
    variant_id: str               # Which ContentVariant was deployed
    channel: str
    deployed_at: datetime
    external_id: str              # Platform-specific post/campaign ID
    status: str                   # "deployed" | "scheduled" | "failed"
    ab_test_group: str | None     # Which test group this belongs to
    error: str | None
```

**Behaviour:**
- Never deploys without explicit user approval (enforced at graph level)
- Sets up A/B tests by deploying variants to the same channel with tracking
- Records every deployment with external platform IDs for feedback tracking
- Handles rate limits and API errors with retry logic and clear error surfacing
- Queues scheduled deployments via Redis/ARQ

#### Feedback Agent

**Role:** Ingest engagement data, interpret results against hypotheses, and route intelligence back to the research layer.

**LLM:** GPT-4o (structured analysis and data interpretation)

**Tools:**
- `sendgrid_stats` — Email open rates, click rates, bounces
- `linkedin_analytics` — Post impressions, engagement, demographics
- `meta_insights` — Ad performance, reach, conversions
- `google_ads_report` — Campaign metrics, CPA, ROAS

**Output schema:**
```python
class FeedbackReport(BaseModel):
    id: str
    campaign_id: str
    period: str                          # "24h" | "48h" | "7d"
    channel_metrics: dict[str, ChannelMetrics]
    variant_comparison: list[VariantResult]
    hypothesis_outcomes: list[HypothesisOutcome]  # Did the hypothesis hold?
    recommendations: list[str]           # Actionable next steps
    refined_findings: list[ResearchFinding]  # New findings fed back to research
```

**Behaviour:**
- Polls engagement data on configurable intervals (background jobs via ARQ)
- Interprets variant performance against the original hypotheses
- Generates actionable recommendations for the next loop cycle
- Creates new `ResearchFinding` entries from feedback data and stores them in Qdrant, closing the loop

#### UI Agent

**Role:** Generate ephemeral interface specifications when structured user interaction is needed.

**LLM:** Claude Sonnet (precise schema generation)

**Behaviour:**
- Invoked as a sub-graph by any other agent
- Emits typed `EphemeralUIRequest` objects that the frontend renders
- Pauses the graph execution until the user responds
- User response is injected back into graph state, and execution resumes

### 7.4 LLM Router

The platform uses multiple LLM providers. The `llm_router` service abstracts provider selection:

| Agent | Primary LLM | Rationale |
|---|---|---|
| Supervisor | Claude Sonnet | Reliable routing, strong instruction following |
| Research | GPT-4o | Strong synthesis, handles large context windows well |
| Content | Claude Sonnet | Creative writing quality, tone control |
| Outreach | GPT-4o | Reliable structured tool calling |
| Feedback | GPT-4o | Data analysis, structured output |
| UI Agent | Claude Sonnet | Precise schema generation |
| Image Gen | Nano Banana 2 (Gemini 3.1 Flash Image) | Fast, high-quality ad creatives and visuals |

```python
# llm_router.py — simplified
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

LLM_REGISTRY = {
    "supervisor": ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0.1),
    "research":   ChatOpenAI(model="gpt-4o", temperature=0.2),
    "content":    ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0.7),
    "outreach":   ChatOpenAI(model="gpt-4o", temperature=0.1),
    "feedback":   ChatOpenAI(model="gpt-4o", temperature=0.2),
    "ui_agent":   ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0.1),
}

def get_llm(agent_name: str) -> BaseChatModel:
    return LLM_REGISTRY[agent_name]
```

Nano Banana 2 is called directly via the Google Generative AI API for image generation tasks within the Content Agent's tools, not as a chat LLM.

### 7.5 LangGraph Checkpointing

LangGraph's built-in checkpointer persists graph state to Neon Postgres, enabling:
- Conversation continuity across sessions
- Resume from interruption (e.g., waiting for user approval)
- Debugging and replay via LangSmith

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(NEON_DATABASE_URL)

graph = builder.compile(checkpointer=checkpointer)
```

---

## 8. Data Architecture

### 8.1 Database Allocation

Each database is chosen for its strengths. Data is not duplicated across stores unless explicitly needed for different access patterns.

| Store | Technology | Purpose | Data |
|---|---|---|---|
| Primary DB | Neon Postgres (Prisma) | Users, auth, settings, integrations | Users, sessions, OAuth tokens, preferences, team config |
| Campaign History | MongoDB | Flexible, nested campaign records | Campaigns, loop cycles, agent outputs, content variants |
| Vector Store | Qdrant (Railway) | Semantic search over accumulated intelligence | Research findings (vectorised), content embeddings, past campaign learnings |
| Queue + Cache | Redis (Railway) | Job scheduling, ephemeral cache | Outreach jobs, feedback polling jobs, rate limit counters, SSE connection state |
| Graph State | Neon Postgres | LangGraph checkpoints | Conversation state, agent progress, pending inputs |

### 8.2 Prisma Schema (Neon Postgres)

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-py"
}

model User {
  id            String    @id @default(cuid())
  email         String    @unique
  name          String?
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt

  sessions      Session[]
  integrations  Integration[]
  conversations Conversation[]
  preferences   UserPreference?
}

model Session {
  id        String   @id @default(cuid())
  userId    String
  token     String   @unique
  expiresAt DateTime
  user      User     @relation(fields: [userId], references: [id])
}

model UserPreference {
  id            String  @id @default(cuid())
  userId        String  @unique
  brandName     String?
  brandVoice    String? // JSON: tone, style, personality
  targetAudience String? // JSON: segments, personas
  defaultChannels String? // JSON: ordered channel preferences
  user          User    @relation(fields: [userId], references: [id])
}

model Integration {
  id            String   @id @default(cuid())
  userId        String
  channel       String   // "linkedin" | "sendgrid" | "meta" | "google_ads" | "twitter"
  accessToken   String   // Encrypted at rest
  refreshToken  String?  // Encrypted at rest
  expiresAt     DateTime?
  metadata      Json?    // Channel-specific config (e.g., LinkedIn org ID)
  status        String   @default("active") // "active" | "expired" | "revoked"
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt
  user          User     @relation(fields: [userId], references: [id])

  @@unique([userId, channel])
}

model Conversation {
  id        String   @id @default(cuid())
  userId    String
  title     String?
  campaignId String? // Links to MongoDB campaign record
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  user      User     @relation(fields: [userId], references: [id])
}
```

### 8.3 MongoDB Collections

MongoDB stores the rich, nested campaign data that benefits from flexible schemas:

```javascript
// campaigns collection
{
  _id: ObjectId,
  userId: "cuid_xxx",                    // References Postgres User
  conversationId: "cuid_xxx",            // References Postgres Conversation
  title: "Competitor pricing response campaign",
  status: "active",                       // "active" | "completed" | "paused"
  createdAt: ISODate,
  updatedAt: ISODate,

  loops: [                                // Each loop cycle
    {
      loopNumber: 1,
      startedAt: ISODate,
      completedAt: ISODate,

      research: {
        findings: [ResearchFinding],      // Full typed objects
        intelligenceBrief: IntelligenceBrief,
      },

      content: {
        variants: [ContentVariant],
        approvedVariants: ["variant_id_1", "variant_id_2"],
      },

      outreach: {
        deployments: [DeploymentRecord],
        abTests: [ABTestConfig],
      },

      feedback: {
        reports: [FeedbackReport],
        hypothesisOutcomes: [HypothesisOutcome],
        refinedFindings: [ResearchFinding],  // Fed back into next loop
      }
    }
  ]
}
```

### 8.4 Qdrant Collections

```python
# Collection: research_findings
# Stores vectorised research findings for semantic retrieval
{
    "collection_name": "research_findings",
    "vectors": {
        "size": 1536,          # text-embedding-3-small
        "distance": "Cosine"
    },
    "payload_schema": {
        "user_id": "keyword",
        "campaign_id": "keyword",
        "category": "keyword",   # competitive, market, audience, etc.
        "confidence": "float",
        "timestamp": "datetime",
        "claim": "text",
    }
}

# Collection: content_history
# Stores past content for similarity search and inspiration
{
    "collection_name": "content_history",
    "vectors": {
        "size": 1536,
        "distance": "Cosine"
    },
    "payload_schema": {
        "user_id": "keyword",
        "channel": "keyword",
        "content_type": "keyword",
        "performance_score": "float",  # Normalised engagement metric
        "body": "text",
    }
}
```

### 8.5 Data Flow Diagram

```
User Message
    │
    ▼
┌─────────────────┐
│  FastAPI /stream │──────────────────────────────────┐
└────────┬────────┘                                   │
         │                                            │
         ▼                                            ▼
┌─────────────────┐                          ┌────────────────┐
│  LangGraph       │                          │  Neon Postgres  │
│  (State Graph)   │◀─checkpoint/resume──────▶│  (Checkpoints)  │
└────────┬────────┘                          └────────────────┘
         │
    ┌────┴──────────────┬──────────────┬──────────────┐
    ▼                   ▼              ▼              ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Research  │    │ Content  │    │ Outreach │    │ Feedback │
│ Agent     │    │ Agent    │    │ Agent    │    │ Agent    │
└─────┬────┘    └─────┬────┘    └─────┬────┘    └─────┬────┘
      │               │              │               │
      ▼               ▼              ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Tavily   │    │ LLMs     │    │ Channel  │    │ Channel  │
│ Qdrant   │    │ Nano     │    │ APIs     │    │ Analytics│
│ Trends   │    │ Banana 2 │    │ (deploy) │    │ APIs     │
└─────┬────┘    └─────┬────┘    └─────┬────┘    └─────┬────┘
      │               │              │               │
      └───────────────┴──────┬───────┴───────────────┘
                             ▼
                    ┌─────────────────┐
                    │    MongoDB       │ (Campaign history)
                    │    Qdrant        │ (Vector embeddings)
                    │    Redis         │ (Job queue)
                    └─────────────────┘
```

---

## 9. Integration Architecture

### 9.1 Channel Integration Pattern

All channel integrations follow the same adapter pattern, abstracted behind a `ChannelAdapter` interface:

```python
class ChannelAdapter(ABC):
    """Base interface for all channel integrations."""

    @abstractmethod
    async def authenticate(self, user_id: str) -> OAuthResult:
        """Start OAuth flow, return redirect URL."""

    @abstractmethod
    async def publish(self, content: ContentVariant, credentials: Integration) -> DeploymentRecord:
        """Deploy content to this channel."""

    @abstractmethod
    async def get_analytics(self, deployment_id: str, credentials: Integration) -> ChannelMetrics:
        """Fetch engagement data for a deployed piece of content."""

    @abstractmethod
    async def health_check(self, credentials: Integration) -> bool:
        """Verify credentials are still valid."""
```

Each channel has a concrete implementation: `LinkedInAdapter`, `SendGridAdapter`, `MetaAdapter`, `GoogleAdsAdapter`, `TwitterAdapter`. Adding a new channel means implementing this interface — no changes to agent code.

### 9.2 OAuth Credential Management

```
User clicks "Connect LinkedIn"
    │
    ▼
Next.js Server Action → FastAPI /integrations/linkedin/connect
    │
    ▼
Redirect to LinkedIn OAuth consent screen
    │
    ▼
Callback → FastAPI /integrations/linkedin/callback
    │
    ▼
Store encrypted access_token + refresh_token in Neon Postgres (Integration table)
    │
    ▼
Redirect back to /integrations (success state)
```

Tokens are encrypted at rest using AES-256. Refresh logic runs as a background job (ARQ) to proactively renew tokens before expiry.

### 9.3 Webhook Ingestion

Inbound webhooks from channels (SendGrid engagement events, LinkedIn interaction notifications) are processed through a common pipeline:

```
Channel webhook → FastAPI /webhooks/{channel}
    │
    ▼
Validate signature (HMAC / shared secret per channel)
    │
    ▼
Normalize to internal EngagementEvent schema
    │
    ▼
Push to Redis queue (channel: "feedback_events")
    │
    ▼
ARQ worker picks up → updates MongoDB campaign record
    │
    ▼
If active feedback cycle → triggers Feedback Agent re-evaluation
```

---

## 10. Background Job Architecture (Redis + ARQ)

### 10.1 Job Types

| Job | Trigger | Frequency | Description |
|---|---|---|---|
| `poll_channel_analytics` | After deployment | Every 6h for 72h, then daily for 7d | Fetch engagement data from channel APIs |
| `refresh_oauth_tokens` | Cron | Every 30 minutes | Proactively refresh tokens nearing expiry |
| `process_webhook_event` | Webhook received | Real-time | Normalise and store engagement events |
| `scheduled_deployment` | User-scheduled | One-time | Deploy content at a scheduled time |
| `research_deep_dive` | Agent request | On-demand | Long-running research tasks (>30s) |

### 10.2 ARQ Configuration

```python
# queue.py
from arq import create_pool
from arq.connections import RedisSettings

redis_settings = RedisSettings(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
)

class WorkerSettings:
    functions = [
        poll_channel_analytics,
        refresh_oauth_tokens,
        process_webhook_event,
        scheduled_deployment,
        research_deep_dive,
    ]
    redis_settings = redis_settings
    max_jobs = 10
    job_timeout = 300  # 5 minutes max per job
```

---

## 11. Deployment Architecture (Railway)

### 11.1 Railway Services

| Service | Source | Railpack | Notes |
|---|---|---|---|
| `web` | `apps/web` | Next.js auto-detect | SSR, port 3000 |
| `api` | `apps/api` | Python auto-detect | FastAPI + Uvicorn, port 8000 |
| `worker` | `apps/api` | Python auto-detect | ARQ worker process (same codebase, different entrypoint) |
| `redis` | Railway template | — | Redis 7, persistent storage |
| `qdrant` | Docker image `qdrant/qdrant` | — | Port 6333/6334 |
| `mongodb` | Railway template | — | MongoDB 7, persistent volume |

Neon Postgres is external (managed by Neon), connected via connection string.

### 11.2 Railway Configuration

```toml
# railway.toml

[build]
builder = "railpack"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

### 11.3 Service Communication

All Railway services communicate over Railway's private network:

```
web (Next.js) ──private network──▶ api (FastAPI)     @ api.railway.internal:8000
api (FastAPI) ──private network──▶ redis             @ redis.railway.internal:6379
api (FastAPI) ──private network──▶ qdrant            @ qdrant.railway.internal:6333
api (FastAPI) ──private network──▶ mongodb            @ mongodb.railway.internal:27017
api (FastAPI) ──public internet──▶ Neon Postgres      @ *.neon.tech
api (FastAPI) ──public internet──▶ LLM APIs, Channel APIs
```

### 11.4 Environment Variables

```bash
# Neon Postgres
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/growthdb?sslmode=require

# MongoDB (Railway internal)
MONGODB_URL=mongodb://mongodb.railway.internal:27017/amplify

# Redis (Railway internal)
REDIS_URL=redis://redis.railway.internal:6379

# Qdrant (Railway internal)
QDRANT_URL=http://qdrant.railway.internal:6333

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...

# Search
TAVILY_API_KEY=tvly-...

# Channel Integrations
SENDGRID_API_KEY=SG...
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
META_APP_ID=...
META_APP_SECRET=...
GOOGLE_ADS_DEVELOPER_TOKEN=...
TWITTER_API_KEY=...
TWITTER_API_SECRET=...

# Auth
BETTER_AUTH_SECRET=...
BETTER_AUTH_URL=https://app.amplify.com

# Observability
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT=amplify

# Encryption
ENCRYPTION_KEY=... # AES-256 key for OAuth token encryption
```

---

## 12. Observability & Monitoring

### 12.1 LangSmith Integration

Every LangGraph run is traced in LangSmith, providing:
- Full trace of each agent invocation, tool call, and LLM request
- Token usage and cost tracking per agent and per conversation
- Latency breakdown by agent and tool
- Error tracking with full state context
- Evaluation datasets for regression testing agent quality

### 12.2 Application Monitoring

| Concern | Approach |
|---|---|
| API health | `/health` endpoint on FastAPI, Railway health checks |
| Error tracking | Structured logging (JSON) to Railway log drain |
| Uptime monitoring | Railway built-in monitoring + external ping (e.g., BetterStack) |
| LLM cost tracking | LangSmith usage dashboards, monthly budget alerts |
| Channel API health | Periodic health checks via ARQ job, alert on token expiry |

### 12.3 Logging Strategy

```python
import structlog

logger = structlog.get_logger()

# Every log entry includes:
# - user_id
# - conversation_id
# - agent_name (if within agent context)
# - campaign_id (if within campaign context)

logger.info("agent_completed",
    agent="research",
    findings_count=5,
    duration_ms=4200,
    tokens_used=3500,
    user_id=user.id,
    conversation_id=conv.id
)
```

---

## 13. Security Architecture

### 13.1 Authentication & Authorization

- BetterAuth handles user authentication entirely within Next.js (email/password, OAuth social login)
- Session tokens are HTTP-only, secure, SameSite cookies managed by BetterAuth
- Next.js is the auth gateway — all requests to FastAPI originate from authenticated Server Actions
- FastAPI is not publicly exposed; it trusts `X-User-Id` headers from Next.js over Railway's private network
- FastAPI middleware rejects any request without `X-User-Id` (except `/health` and webhook endpoints)
- Webhook endpoints validate signatures (HMAC per channel) instead of user auth

### 13.2 Data Security

- OAuth tokens encrypted at rest (AES-256) in Neon Postgres
- All inter-service communication over Railway's private network (no public exposure)
- Neon Postgres connection requires SSL (`sslmode=require`)
- Environment secrets managed via Railway's secret management
- No credentials in code or logs

### 13.3 API Security

- Rate limiting on chat endpoints (per user, via Redis)
- Input validation via Pydantic models on all endpoints
- CORS restricted to the web app domain
- Content Security Policy headers on the Next.js app

---

## 14. Scalability Considerations

For MVP with a solo founder, the architecture is intentionally simple. Here is how each component scales when the time comes:

| Component | Current | Scaling Path |
|---|---|---|
| FastAPI | Single instance on Railway | Horizontal scaling (multiple Railway replicas) |
| ARQ Worker | Single worker process | Multiple workers (increase `max_jobs`, add replicas) |
| Neon Postgres | Serverless (auto-scales) | Neon handles scaling, add read replicas if needed |
| MongoDB | Single Railway instance | Move to MongoDB Atlas for managed scaling |
| Qdrant | Single Railway instance | Move to Qdrant Cloud for managed scaling |
| Redis | Single Railway instance | Railway Redis scaling or move to Upstash |
| LangGraph | In-process | LangGraph Cloud for managed execution (when available) |

---

## 15. Development & Local Setup

### 15.1 Local Development Services

No Docker required. Local development uses cloud free tiers for backing services, keeping the setup to three terminal commands.

| Service | Local Dev Provider | Tier | Setup |
|---|---|---|---|
| Redis | Upstash | Free (10K commands/day) | Create database at upstash.com, copy connection URL |
| MongoDB | MongoDB Atlas | Free (M0, 512MB) | Create cluster at mongodb.com/atlas, copy connection string |
| Qdrant | Qdrant Cloud | Free (1GB) | Create cluster at cloud.qdrant.io, copy URL + API key |
| Postgres | Neon | Free (0.5GB) | Same instance for dev and prod (use separate databases) |

All connection strings go in `.env.local`:

```bash
# .env.local
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/growthdb_dev?sslmode=require
MONGODB_URL=mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/amplify_dev
REDIS_URL=rediss://default:xxxxx@xxx.upstash.io:6379
QDRANT_URL=https://xxx.cloud.qdrant.io:6333
QDRANT_API_KEY=xxxxx

# LLM + tool API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...
TAVILY_API_KEY=tvly-...

# Auth
BETTER_AUTH_SECRET=dev-secret
BETTER_AUTH_URL=http://localhost:3000
```

### 15.2 Running Locally

```bash
# Terminal 1: Next.js dev server
cd apps/web && pnpm dev

# Terminal 2: FastAPI dev server
cd apps/api && uv run uvicorn main:app --reload --port 8000

# Terminal 3: ARQ worker
cd apps/api && uv run arq app.worker.WorkerSettings
```

### 15.3 Offline Fallback

If you need to develop without an internet connection, the backing services can be installed natively (no Docker needed):

```bash
# macOS
brew install redis qdrant/tap/qdrant
brew tap mongodb/brew && brew install mongodb-community

# Start services
redis-server &
qdrant &
mongod --dbpath /tmp/mongodb &
```

Switch `.env.local` connection strings to `localhost` equivalents when working offline.

---

## 16. Decision Log

| Decision | Choice | Alternatives Considered | Rationale |
|---|---|---|---|
| Agent framework | LangGraph | CrewAI, AutoGen, custom | State graph model fits the loop; built-in checkpointing; LangSmith integration |
| Primary DB | Neon Postgres | Supabase, PlanetScale | Serverless Postgres, Prisma support, cost-effective for early stage |
| Campaign store | MongoDB | Postgres JSONB | Deeply nested campaign/loop data suits document model; avoids complex joins |
| Vector store | Qdrant (self-hosted) | Pinecone, Weaviate, pgvector | Full control, no vendor lock-in, runs on Railway, good Python SDK |
| Task queue | ARQ + Redis | Celery, Dramatiq, BullMQ | Async-native Python, lightweight, Redis-backed (already in stack) |
| Frontend state | Zustand | Redux, Jotai, React Context | Minimal boilerplate, SSR-compatible, good for chat streaming state |
| SSE over WebSockets | SSE | WebSocket | Simpler protocol, sufficient for one-way streaming, auto-reconnect, no sticky sessions needed |
| Image generation | Nano Banana 2 | DALL-E 3, Midjourney API, Flux | Fast, cost-effective, strong text rendering for ad creatives, API available |
| Deployment | Railway + Railpack | Vercel + Fly.io, AWS, Render | Monorepo-friendly, simple deployment, private networking between services |
| Auth | BetterAuth (Next.js only) | NextAuth, Clerk, Supabase Auth | Self-hosted, no vendor lock-in; scoped to Next.js to avoid Python adapter gaps; FastAPI trusts X-User-Id over private network |

---

*This is a living document. It will be updated as implementation progresses and architectural decisions are validated.*
