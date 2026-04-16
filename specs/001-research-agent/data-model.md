# Phase 1: Data Model — Research Agent

**Feature**: 001-research-agent
**Date**: 2026-04-13

Defines the typed entities backing this slice, their persistence home, and
their validation rules. Relational data lives in Neon Postgres (managed by
Prisma). Document data lives in MongoDB (managed by Motor + Pydantic). The
link between the two is a single foreign reference (`brief_id`) on the
`Message` row.

**Prisma ownership.** The canonical schema and the migration history live in
`apps/web/prisma/` (Node Prisma, used by BetterAuth and Next.js Server
Actions). `apps/api/db/prisma/schema.prisma` is a hand-kept mirror whose only
diff is `generator client { provider = "prisma-client-py" }`. FastAPI reads
and writes Postgres via `prisma-client-py` but NEVER runs `migrate dev` —
migrations flow one way, from web. This keeps BetterAuth and research models
in a single schema without introducing a shared package.

**Runtime validation on the web side.** Entities leaving the FastAPI boundary
are validated on the Next.js side with Zod schemas generated from the Pydantic
models — see plan.md §Technical Context and tasks.md T018 / T047. This catches
contract drift at the edge before bad data reaches the UI.

## Storage map

| Entity | Store | Owner |
|---|---|---|
| User | Postgres | Prisma (BetterAuth-compatible schema) |
| Session | Postgres | BetterAuth |
| Conversation | Postgres | Prisma |
| Message | Postgres | Prisma |
| ResearchRequest | Postgres | Prisma |
| FailureRecord | Postgres | Prisma |
| ProgressEvent | Postgres (denormalized on Message) | Prisma |
| LangGraphCheckpoint | Postgres | LangGraph (its own schema) |
| IntelligenceBrief | MongoDB (`intelligence_briefs`) | Motor + Pydantic |
| Finding | MongoDB (nested in IntelligenceBrief) | Pydantic |
| SourceAttribution | MongoDB (nested in Finding) | Pydantic |

---

## Postgres entities (Prisma)

### User

| Field | Type | Notes |
|---|---|---|
| `id` | `String @id @default(cuid())` | BetterAuth user id |
| `email` | `String @unique` | Required |
| `name` | `String?` | Optional display name |
| `createdAt` | `DateTime @default(now())` | |
| `updatedAt` | `DateTime @updatedAt` | |

Relations: `conversations: Conversation[]`

### Session

BetterAuth-managed. Fields per BetterAuth's Prisma adapter (id, userId, expiresAt, token, ipAddress, userAgent). Not detailed here — this slice does not modify them.

### Conversation

| Field | Type | Notes |
|---|---|---|
| `id` | `String @id @default(cuid())` | |
| `userId` | `String` | FK → User.id (onDelete: Cascade) |
| `title` | `String` | Derived from first research question; max 140 chars |
| `createdAt` | `DateTime @default(now())` | |
| `updatedAt` | `DateTime @updatedAt` | |
| `archivedAt` | `DateTime?` | Soft-delete marker |

Relations: `user: User`, `messages: Message[]`, `researchRequests: ResearchRequest[]`

Indexes: `@@index([userId, updatedAt(sort: Desc)])` for the conversation list query.

**Validation rules**
- `title` is set from the first user message, truncated to 140 chars.
- `userId` must match `request.state.user_id` on every query (row-level isolation enforced in `conversation_store.py`).

### Message

| Field | Type | Notes |
|---|---|---|
| `id` | `String @id @default(cuid())` | |
| `conversationId` | `String` | FK → Conversation.id (onDelete: Cascade) |
| `role` | `MessageRole` | enum: `user`, `system`, `assistant` |
| `content` | `String` | Plaintext. For brief messages, a short summary. |
| `briefId` | `String?` | MongoDB ObjectId (as string) when this message represents a rendered IntelligenceBrief |
| `progressEvents` | `Json` | Array of ProgressEvent objects captured while producing this message (for replay) |
| `failureRecordId` | `String?` | FK → FailureRecord.id when this message represents a failure |
| `createdAt` | `DateTime @default(now())` | |

Relations: `conversation: Conversation`, `failureRecord: FailureRecord?`

Indexes: `@@index([conversationId, createdAt])`

**State transitions** (for assistant messages that wrap a research run):
```
pending ──► streaming ──► complete
                ├──────► failed
                └──────► cancelled
```
Status is derived, not stored: `status = failureRecordId ? "failed" : briefId ? "complete" : "pending"`.

**Validation rules**
- Exactly one of (`briefId`, `failureRecordId`, plain text) is set per assistant message.
- `progressEvents` is an append-only JSON array during streaming; finalized at `done`.

### ResearchRequest

| Field | Type | Notes |
|---|---|---|
| `id` | `String @id @default(cuid())` | |
| `conversationId` | `String` | FK → Conversation.id |
| `messageId` | `String` | FK → Message.id (the user message that initiated it) |
| `rawQuestion` | `String` | Original user text |
| `scopedQuestion` | `String` | After any clarification narrowing |
| `plan` | `Json` | Serialized `ResearchPlan` (sub-queries) |
| `status` | `ResearchStatus` | enum: `pending`, `running`, `complete`, `failed`, `cancelled` |
| `budgetQueries` | `Int` | Cap used for this request (default 8) |
| `budgetSeconds` | `Int` | Cap used for this request (default 60) |
| `startedAt` | `DateTime?` | |
| `completedAt` | `DateTime?` | |
| `briefId` | `String?` | MongoDB ObjectId on success |
| `failureRecordId` | `String?` | FK on failure |

Indexes: `@@index([conversationId, startedAt])`

**Validation rules**
- `scopedQuestion` defaults to `rawQuestion` when no clarification occurred.
- Transition from `pending → running` requires a `startedAt` timestamp.
- Terminal states (`complete | failed | cancelled`) require `completedAt`.

### FailureRecord

| Field | Type | Notes |
|---|---|---|
| `id` | `String @id @default(cuid())` | |
| `code` | `FailureCode` | enum per research.md R-011 |
| `recoverable` | `Boolean` | |
| `userMessage` | `String` | Human-readable, shown in the chat |
| `suggestedAction` | `String?` | e.g., "Try narrowing to a specific competitor" |
| `traceId` | `String?` | LangSmith run id for diagnosis |
| `createdAt` | `DateTime @default(now())` | |

**Validation rules**
- `userMessage` must be non-empty (no generic fallbacks — Constitution V).
- `recoverable = true` requires `suggestedAction` to be set with a concrete next step.

### Enums

```prisma
enum MessageRole { user system assistant }
enum ResearchStatus { pending running complete failed cancelled }
enum FailureCode {
  tavily_unavailable
  tavily_rate_limited
  llm_unavailable
  llm_invalid_output
  no_findings_above_threshold
  user_cancelled
  budget_exceeded
  rate_limited_user
}
```

---

## MongoDB entities (Pydantic + Motor)

Collection: `intelligence_briefs`. Each document is a full brief. Documents are
written once on research completion and updated only for administrative
operations (not mutated as part of user interactions in this slice).

### `IntelligenceBrief`

```python
class IntelligenceBrief(BaseModel):
    id: str                              # MongoDB ObjectId as string
    v: int = 1                           # schema version
    user_id: str                         # row-level isolation
    conversation_id: str
    research_request_id: str
    scoped_question: str
    status: Literal["complete", "low_confidence"]
    findings: list[Finding]              # at least 1; aim ≥3 for `complete`
    generated_at: datetime               # UTC
    model_used: str                      # e.g., "openai/gpt-4o-2024-11"
    trace_id: str | None                 # LangSmith run id
```

**Validation rules**
- `len(findings) >= 1` always.
- `status == "complete"` requires `len(findings) >= 3` AND at least one
  `confidence == "high"`. Otherwise `status = "low_confidence"`.
- `user_id` MUST match the request's authenticated user on every read.

Indexes:
- `{ conversation_id: 1, generated_at: -1 }`
- `{ user_id: 1, generated_at: -1 }`

### `Finding`

```python
class Finding(BaseModel):
    id: str                              # local uuid for follow-up referencing
    rank: int                            # 1-based display order
    claim: str                           # one-line factual statement (≤ 280 chars)
    evidence: str                        # 1–3 sentences of supporting context
    confidence: Literal["high", "medium", "low"]
    sources: list[SourceAttribution]     # at least 1
    contradicts: list[str] = []          # ids of other findings this conflicts with
    unsourced: bool = False              # True when deliberately kept without a source
    notes: str | None = None             # e.g., "primary source paywalled; summary from cached preview"
```

**Validation rules**
- `len(sources) >= 1` UNLESS `unsourced == True`, in which case `notes` MUST
  explain why (FR-016).
- When `unsourced == True`, the finding MUST be flagged as unsourced in the UI.
- `confidence == "high"` requires at least 2 sources OR 1 source with
  source_type in (`news`, `official`, `competitor_site`).

### `SourceAttribution`

```python
class SourceAttribution(BaseModel):
    title: str
    url: HttpUrl
    source_type: Literal[
      "news", "blog", "forum", "competitor_site", "official",
      "ad_library", "analytics", "other"
    ]
    consulted_at: datetime               # UTC
    accessible: bool = True              # False when paywalled/blocked but still cited
    snippet: str | None = None           # short excerpt from the source
```

**Validation rules**
- `url` must parse as a valid HTTP/HTTPS URL.
- `consulted_at` must be within the last 24 hours of `IntelligenceBrief.generated_at`.
- If `accessible == False`, `notes` in the parent finding MUST mention it
  (FR-028).
- **Anti-hallucination gate (research.md R-003):** every `url` in every
  `SourceAttribution` MUST appear in the Tavily result set collected for this
  request. Enforced in `apps/api/agents/research.py` before the brief is
  persisted.

---

## Derived/transient entities

### `ResearchPlan` (in-memory Pydantic, persisted as JSON on ResearchRequest)

```python
class ResearchPlan(BaseModel):
    sub_queries: list[SubQuery]          # 3–5 items
    rationale: str                       # short explanation of the decomposition

class SubQuery(BaseModel):
    angle: Literal[
      "competitive", "audience", "market", "channel",
      "temporal", "adjacent"
    ]
    query: str                           # the actual search string
```

**Validation rules**
- `3 <= len(sub_queries) <= 5`.
- Each sub-query's `query` is ≤ 200 chars.

### `ProgressEvent` (Pydantic; serialized into `Message.progressEvents`)

```python
class ProgressEvent(BaseModel):
    at: datetime
    phase: Literal["planning", "searching", "synthesizing", "validating"]
    message: str                         # human-readable ("Searching competitor ads…")
    detail: dict[str, Any] | None = None # e.g., {"sub_query": "…"}
```

### `SupervisorDecision` (structured LLM output; not persisted directly)

```python
class SupervisorDecision(BaseModel):
    route: Literal[
      "research",
      "clarification_needed",
      "out_of_scope",
      "followup_on_existing_brief"
    ]
    scoped_question: str | None          # set when route == "research"
    clarification_options: list[str] | None  # set when route == "clarification_needed"
    target_finding_id: str | None        # set when route == "followup_on_existing_brief"
    explanation: str                     # for trace readability
```

---

## Access patterns

| Query | Store | Index |
|---|---|---|
| List conversations for a user, newest first | Postgres | `Conversation(userId, updatedAt desc)` |
| Load full conversation (messages in order) | Postgres | `Message(conversationId, createdAt)` |
| Load brief referenced by a message | MongoDB | `_id` (ObjectId) |
| Load full user history of briefs (future) | MongoDB | `(user_id, generated_at desc)` |
| Resume an in-flight research run | Postgres | LangGraph checkpoint by `thread_id = conversationId` |

---

## Row-level isolation

Every query against `Conversation`, `Message`, `ResearchRequest`, and
`intelligence_briefs` MUST filter by `user_id` from `request.state.user_id`.
This is enforced in the store services (`conversation_store.py`,
`brief_store.py`) — callers cannot bypass it because the services don't expose
an unfiltered API. Tests assert that a User A cannot read User B's
conversations or briefs.

---

## Retention

- Conversations, messages, briefs, and failure records are retained
  indefinitely in this slice (MVP validation phase).
- Redis cache entries expire per their TTLs (5 min for Tavily cache, 1 hour
  for rate-limit counters).
- LangGraph checkpoints older than 30 days for `complete`/`failed`/`cancelled`
  threads can be pruned by a future background job — out of scope for this
  slice.
