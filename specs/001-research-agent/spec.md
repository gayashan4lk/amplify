# Feature Specification: Research Agent

**Feature Branch**: `main` (git extension not installed; no branch created)
**Created**: 2026-04-13
**Status**: Draft
**Input**: User description: "Understand the specification for the project using the docs in /Users/gayashan/source/amplify/docs. Scope decision: single loop stage (Research Agent + intelligence-brief ephemeral UI). No Outreach. Defaults for open questions."

## Summary

This spec covers the first shippable slice of Amplify: a conversational research
experience where a user asks a market question in chat and receives a structured
**intelligence brief** — a typed, sourced, confidence-rated synthesis — rendered
inline in the conversation. It is the "signal" half of the growth loop; Content,
Outreach, and Feedback are explicitly out of scope for this spec.

The slice exercises the core architectural primitives Amplify depends on:
conversation-first interaction, the Supervisor → specialist agent routing pattern,
streaming progress visibility, structured agent outputs, and ephemeral inline UI.
Everything built here is intended to be directly reusable when later specs add the
Content, Outreach, and Feedback agents.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask a market question and get a structured intelligence brief (Priority: P1)

A growth-minded founder opens the chat and asks a question about their market,
competitor, or audience — for example, *"What is our biggest competitor doing on
LinkedIn this month?"* or *"What are mid-market SaaS buyers complaining about in
procurement right now?"*. The system acknowledges the question, streams its
research progress in real time (which sources it is checking, what it has found so
far), and finally renders an **intelligence brief** inline in the conversation: a
structured card containing prioritized findings, each with a one-line claim,
supporting evidence, a confidence level, and links to the sources the claim is
based on. The user can read the brief, ask follow-up questions, and trust that
every claim is traceable back to where it came from.

**Why this priority**: This is the minimum user-visible product. Without it, there
is no "signal" in the signal-to-action loop. It validates the conversation-first
interface, the Supervisor→Research routing, the streaming model, structured agent
outputs, and ephemeral UI — the five foundations the rest of the product depends
on. If only this ships, a solo founder can already use Amplify as a research
assistant that is faster and more structured than ad-hoc ChatGPT use.

**Independent Test**: A new user signs in, opens the chat, asks a well-defined
research question, observes streamed progress, and receives an intelligence brief
with at least three findings, each with a confidence level and at least one
attributable source URL. The user can click a source and reach the original page.

**Acceptance Scenarios**:

1. **Given** the user is signed in and on an empty chat, **When** they send a
   research question with clear scope (e.g., "What pricing models are top 5 CRM
   competitors using?"), **Then** the system acknowledges receipt within 2 seconds,
   streams progress events showing which sources or angles are being investigated,
   and within 30 seconds renders an intelligence brief containing at least three
   findings.
2. **Given** a research question is being processed, **When** the user watches the
   conversation, **Then** they can see live status updates indicating the research
   is in progress and roughly what stage it is at, rather than a bare spinner.
3. **Given** an intelligence brief has been rendered, **When** the user inspects
   any finding, **Then** each finding shows a confidence level (high / medium /
   low), at least one source attribution with a clickable link, and a timestamp
   indicating when the source was consulted.
4. **Given** an intelligence brief exists in the conversation, **When** the user
   asks a follow-up question referring to it (e.g., "Tell me more about the
   second finding"), **Then** the system answers with reference to the prior
   brief, without re-doing the full research from scratch.
5. **Given** a research question is too vague to answer well (e.g., "What should
   we do?"), **When** the user sends it, **Then** the system surfaces a
   clarification affordance asking the user to narrow scope before investing
   research effort.

---

### User Story 2 - Conversation and brief persistence across sessions (Priority: P2)

A user returns to Amplify a day later and expects to find the chat they had
yesterday, including the intelligence brief that was generated. They can reopen
the conversation, re-read the brief, and continue asking follow-ups as if they had
never left.

**Why this priority**: Without persistence, the research slice is demo-ware —
valuable in the moment but not compounding. Persistence is what turns a one-shot
research tool into the foundation of "each cycle starts sharper." It is P2 only
because Story 1 is testable with in-memory state; persistence is the second
thing to ship, not the first.

**Independent Test**: A user runs a full research session, closes the browser,
signs back in on a new session, opens their conversation list, selects the prior
conversation, and sees the full message history including the rendered
intelligence brief with all findings, confidence levels, and sources intact.

**Acceptance Scenarios**:

1. **Given** a user has completed a research interaction, **When** they sign out
   and sign back in, **Then** the prior conversation appears in their conversation
   list with its original question as a recognisable title.
2. **Given** the user reopens a prior conversation, **When** the conversation
   loads, **Then** all messages, streamed progress summaries, and the intelligence
   brief render in the same order and with the same content as before.
3. **Given** the user asks a follow-up in a reopened conversation, **When** the
   system responds, **Then** it treats prior findings as available context rather
   than starting fresh.

---

### User Story 3 - Visible failure when research cannot be completed (Priority: P2)

When the research process fails — a source is unreachable, the query hits a rate
limit, an internal model errors, or no sources yield useful information — the
system tells the user exactly what happened, distinguishes whether it is worth
retrying, and suggests a concrete next step. It never returns a silent empty
result or a generic "something went wrong".

**Why this priority**: This is a safety property, not a feature. The constitution
requires it (Principle V: Fail Visibly). P2 because it's only observable once the
happy path exists.

**Independent Test**: Inject a failure at each documented failure point (source
unavailable, model error, no findings above minimum confidence, user-cancelled)
and verify that in every case the user sees a specific, actionable in-conversation
message.

**Acceptance Scenarios**:

1. **Given** an external source required for a research question is unavailable,
   **When** the system attempts to use it, **Then** the conversation surfaces a
   recoverable failure message naming what was unreachable and offering retry.
2. **Given** research completes but no finding meets the minimum confidence
   threshold, **When** the system finishes, **Then** the user sees a
   "low-confidence result" notice explaining why and suggesting how to narrow or
   rephrase the question — not a fabricated brief.
3. **Given** the user navigates away or cancels mid-research, **When** they
   return, **Then** the conversation shows the cancelled state clearly and allows
   re-running.

---

### Edge Cases

- **Ambiguous question** — The question is too broad to answer meaningfully (e.g.,
  "tell me about marketing"). The system must ask a narrowing question rather
  than produce a low-value brief.
- **Out-of-scope question** — The user asks something unrelated to market
  research (e.g., "write me a poem"). The system must politely decline or
  redirect without silently pretending to research.
- **Very recent event** — The user asks about something that happened today.
  Sources may not yet have indexed it. The brief must distinguish "not yet
  found" from "does not exist".
- **Conflicting findings** — Two sources contradict each other. Both must appear
  in the brief with their disagreement surfaced, not silently reconciled.
- **Source paywalled or blocked** — The system encountered a relevant source but
  could not access its contents. This must be disclosed in the brief rather than
  dropped.
- **Long-running research** — The research exceeds the target time window.
  The user must see a progress indication and be offered the option to wait,
  cancel, or accept partial findings.
- **Session disconnect mid-research** — The user's browser disconnects while
  research is running. On reconnect, the user must see either the final result
  (if completed) or current progress (if still running) — not a lost state.
- **Duplicate question** — The user asks essentially the same question twice in
  one conversation. The system should recognise this and reuse prior findings
  rather than re-running the whole research.
- **Follow-up asking for a source not in the brief** — The user asks about a
  claim that isn't supported. The system must say so, not fabricate attribution.

## Requirements *(mandatory)*

### Functional Requirements

**Conversation surface**

- **FR-001**: Users MUST be able to sign in, land on a chat surface, and send a
  text message as a research question without any additional configuration.
- **FR-002**: The chat surface MUST display messages from the user and from the
  system in chronological order within a single conversation thread.
- **FR-003**: Users MUST be able to view a list of their prior conversations and
  reopen any of them.
- **FR-004**: Users MUST be able to start a new conversation at any time without
  affecting prior ones.

**Research execution**

- **FR-005**: The system MUST detect when a user message is a research request and
  route it to the Research capability. For non-research messages (small talk,
  out-of-scope requests), the system MUST respond appropriately without invoking
  research.
- **FR-006**: The system MUST acknowledge receipt of a research request within 2
  seconds of the user sending the message.
- **FR-007**: The system MUST stream progress events to the user while research is
  in flight, indicating what the research is currently doing (e.g., which angle
  or source type is being investigated) in human-readable terms.
- **FR-008**: The system MUST produce an initial intelligence brief within 30
  seconds of the user's research request under normal conditions.
- **FR-009**: The system MUST investigate multiple angles of a research question
  in parallel where the question permits it, rather than strictly sequentially.
- **FR-010**: The system MUST enforce a bounded research effort per request so
  that a single question cannot consume unbounded time or cost.

**Intelligence brief structure**

- **FR-011**: Every intelligence brief MUST contain a minimum of one finding and
  aim for at least three findings when the question supports it.
- **FR-012**: Every finding MUST carry a confidence level expressed on a defined
  scale (at minimum high / medium / low).
- **FR-013**: Every finding MUST carry at least one source attribution identifying
  where the claim came from, with a link the user can open.
- **FR-014**: Every finding MUST carry a timestamp indicating when the source was
  consulted.
- **FR-015**: The intelligence brief MUST be rendered as a structured inline
  component within the conversation, not as freeform text, such that individual
  findings can be addressed by follow-up questions.
- **FR-016**: The system MUST NOT fabricate source attributions. If a finding
  cannot be sourced, the finding MUST either be omitted or marked as unsourced
  and explicitly flagged as such.
- **FR-017**: When two sources contradict each other on a finding, the brief MUST
  surface the disagreement rather than silently choosing one side.

**Clarification and scoping**

- **FR-018**: When a user's research question is too vague to produce a useful
  brief, the system MUST request clarification via a structured inline
  affordance before investing significant research effort.
- **FR-019**: The clarification affordance MUST let the user respond with a
  single interaction (e.g., selecting from suggested narrowings) rather than
  requiring them to retype their question.

**Follow-up and conversational context**

- **FR-020**: After an intelligence brief has been produced, the system MUST be
  able to answer follow-up questions that reference it without re-running the
  full research from scratch.
- **FR-021**: The system MUST be able to identify when a follow-up is asking
  about a specific finding in the brief and answer in reference to that finding.

**Persistence**

- **FR-022**: Conversations, messages, and intelligence briefs MUST persist across
  user sessions and survive application restarts.
- **FR-023**: On reopening a prior conversation, the full message history and all
  previously rendered intelligence briefs MUST render with the same content and
  structure as when originally created.
- **FR-024**: If a research run is in progress when the user disconnects, the
  system MUST either complete the run in the background or preserve its state so
  that the user can reconnect and see current progress or final results.

**Visible failure handling**

- **FR-025**: When a research run fails, the conversation MUST surface a specific,
  human-readable failure message that identifies the cause in user-meaningful
  terms.
- **FR-026**: Each surfaced failure MUST indicate whether it is recoverable
  (retryable) or terminal, and when recoverable MUST offer the user a clear next
  action.
- **FR-027**: The system MUST NOT return an empty or placeholder intelligence
  brief to mask a failure. No-finding outcomes MUST be explicitly labelled.
- **FR-028**: If a source is inaccessible (paywalled, rate-limited, blocked),
  this MUST be disclosed in the brief rather than silently dropped.

**Out of scope guardrails**

- **FR-029**: The system MUST NOT publish, send, or deploy any content to any
  external channel as part of this feature. No outreach actions are performed.
- **FR-030**: The system MUST NOT generate marketing content (posts, ads,
  emails) as part of this feature. Content generation is the responsibility of a
  later agent and is out of scope here.

### Key Entities

- **Conversation** — A persistent thread of messages belonging to a single user.
  Has a title (derived from the first research question), a creation time, and
  an ordered list of messages and briefs.
- **Message** — A single turn in a conversation, authored by either the user or
  the system. System messages may carry streamed progress metadata.
- **Research Request** — An interpreted, scoped version of a user's research
  question including any narrowings from clarification. A single conversation
  may contain many research requests over its lifetime.
- **Intelligence Brief** — The structured output of a research request. Contains
  an ordered list of findings, a status (complete / low-confidence / failed /
  cancelled), a timestamp, and a reference to the originating research request.
- **Finding** — A single claim inside an intelligence brief. Has a short claim
  statement, a confidence level, one or more source attributions, a
  consulted-at timestamp, and optional notes (e.g., "contradicts finding 2").
- **Source Attribution** — A reference to where a finding's evidence came from.
  Has a title, a URL, a source type (e.g., news, forum, competitor site,
  ad-library, analytics), and the timestamp when it was consulted.
- **Progress Event** — A streamed status update emitted while research is in
  flight, human-readable, attached to the research request so it can be replayed
  from history.
- **Failure Record** — A structured description of a research failure, including
  cause, whether it is recoverable, and a suggested next action.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can sign in, send their first research question, and
  see a rendered intelligence brief in under 60 seconds end to end under normal
  conditions.
- **SC-002**: For at least 90% of well-scoped research questions, the system
  returns an initial intelligence brief within 30 seconds of submission.
- **SC-003**: For at least 95% of rendered findings, every claim has at least
  one verifiable source link that resolves to a real, relevant page.
- **SC-004**: Zero percent of rendered findings contain fabricated or
  hallucinated source attributions, measured on a sampled audit of briefs.
- **SC-005**: At least 80% of users who run their first research interaction
  rate the resulting brief as "useful" or better.
- **SC-006**: 100% of research runs that fail surface a specific, actionable
  in-conversation message to the user. Zero silent failures.
- **SC-007**: 100% of persisted conversations reopened in a new session render
  with all prior messages and briefs intact and unchanged.
- **SC-008**: Users can identify the confidence level and at least one source
  for any finding in a rendered brief within 5 seconds of looking at it (no
  extra clicks required to see them).
- **SC-009**: At least 70% of users who receive a brief ask at least one
  follow-up question in the same conversation, indicating the brief invites
  further engagement.

## Assumptions

- **Single-brand context.** Each user operates in the context of one brand or
  company at a time. Multi-brand management is out of scope for this slice.
- **Single-user context.** Team collaboration, shared conversations, and
  multi-user permissions are out of scope. Each conversation belongs to one user.
- **English-language questions only.** The research surface targets English
  content and sources for this slice.
- **Authenticated users only.** There is no anonymous / unauthenticated research
  flow. All usage happens after sign-in.
- **Web-sourced research only.** Research draws from publicly available web
  sources accessible via standard search and content retrieval. User-provided
  private sources (uploads, internal docs, CRM exports) are out of scope for
  this slice.
- **No outreach, no content generation.** This slice explicitly stops at
  producing the intelligence brief. The user gets signal; they do not get
  generated marketing content or any deployed action.
- **Conservative defaults on the PRD open questions.** Research depth is system-
  determined with a bounded budget (user-configurable depth is deferred).
  Approval granularity is not relevant here because nothing is published.
  Compliance automation is not relevant here because nothing is sent. Multi-
  brand support is deferred. Pricing is not addressed by this spec.
- **Graceful handling of rate-limited or paywalled sources.** The system will
  encounter sources it cannot fully access; this must be disclosed, not hidden.
- **Conversation history is the user's, not shared.** Per-user isolation of
  conversations and briefs is assumed.

## Out of Scope

The following are intentionally NOT part of this spec and will be addressed in
later specs:

- Content generation (posts, emails, ads, variants, hypotheses).
- Outreach and deployment to LinkedIn, email, Meta, Google Ads, X, or any other
  channel.
- Feedback ingestion, engagement metrics, or resonance analysis.
- Intelligence accumulation across cycles (retrieval of past findings for new
  queries). The brief from one cycle is not yet used to sharpen the next.
- A/B test generation or hypothesis tracking.
- Performance dashboards and aggregated analytics views.
- Team collaboration, sharing, permissions, and multi-user workspaces.
- Channel integration management and OAuth connection flows.
- Paid plan gating, usage metering, billing, or pricing.
- Multi-brand / multi-workspace support.
- Export of briefs as PDF, docs, or formatted reports.

## Dependencies

- **User authentication** — A working sign-in path is required before any of
  this is usable. Provided by the broader platform, not by this spec.
- **External research sources** — The research experience depends on public web
  sources being reachable. Availability of any specific source is not
  guaranteed, and the system must tolerate individual source failures.
