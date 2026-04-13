# Product Requirements Document: Amplify

**Version:** 1.0
**Date:** April 11, 2026
**Author:** Gayashan
**Status:** Draft

---

## 1. Executive Summary

The Amplify is a conversational, AI-powered system that compresses the entire marketing growth loop — research, content generation, multi-channel outreach, and feedback analysis — into a single, continuous workflow. Instead of operating across fragmented tools with days or weeks between each step, growth teams and solo founders execute the full cycle inside one interface, going from market signal to live campaign without switching context.

The platform is built on a multi-agent architecture orchestrated via LangGraph, with specialised agents handling each stage of the loop. The conversational interface is embedded within a web application, and ephemeral UI components surface insights, variant comparisons, and action prompts inline — keeping users in flow.

**Target users:** Startup founders, solo marketers, and growth teams at SMBs.

**MVP scope:** Full loop — Research → Content → Outreach → Feedback — with direct API integrations for publishing and distribution.

---

## 2. Problem Statement

Marketing growth today is fragmented across disconnected tools and workflows:

- **Research** lives in spreadsheets, SEO tools, and analyst reports.
- **Content creation** happens in docs, design tools, and copywriting platforms.
- **Outreach** is managed through email platforms, social schedulers, and ad managers.
- **Performance data** sits in analytics dashboards, CRMs, and platform-native reporting.

Each handoff between stages introduces latency, context loss, and misalignment. By the time a market insight becomes a live campaign, the signal is stale. Teams spend more time coordinating across tools than acting on intelligence.

**The core gap:** the distance between signal and action. This platform closes it.

---

## 3. Vision

A growth team — or a solo founder — opens a single conversation and says: *"Our competitor just launched a new pricing page targeting mid-market. What should we do?"*

The system researches the competitor's positioning, identifies messaging gaps, generates tailored outreach content with A/B variants, deploys it across LinkedIn, email, and paid channels, and then monitors engagement — feeding results back into the next cycle. All without the user leaving the conversation.

Each loop gets sharper. The system learns what resonated, what fell flat, and why — building compounding intelligence over time.

---

## 4. Target Users

### 4.1 Primary Personas

**Solo Founder / Solo Marketer**
- Running growth single-handedly alongside product and operations
- Needs to move fast without a team to delegate to
- Values speed-to-action and automation over granular control
- Typical context: Early-stage startup, pre-Series A, 1–10 employees

**Growth Team at SMB (2–8 people)**
- Small marketing or growth team wearing multiple hats
- Needs a system that replaces 5–10 point solutions
- Values workflow consolidation, shared context, and compounding insights
- Typical context: Seed to Series B, 10–100 employees

### 4.2 Non-Target Users (for MVP)
- Enterprise marketing teams with established martech stacks
- Agencies managing dozens of client accounts simultaneously
- Non-technical users who need a fully no-code visual builder

---

## 5. The Growth Loop

The platform operationalises a four-stage loop where each cycle feeds the next:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │ Research  │───▶│ Content  │───▶│ Outreach │  │
│   └──────────┘    └──────────┘    └──────────┘  │
│        ▲                               │        │
│        │          ┌──────────┐         │        │
│        └──────────│ Feedback │◀────────┘        │
│                   └──────────┘                  │
│                                                 │
│            Each cycle starts sharper             │
└─────────────────────────────────────────────────┘
```

### Stage 1 — Market Research & Intelligence
Gather and synthesise signals from multiple dimensions to build an actionable picture of the market.

**Signal categories:**
- Market and category signals — narratives gaining or losing traction, PESTEL factors
- Competitive intelligence — positioning, messaging, campaigns, channel activity, content output
- Target customer insights — pain points, motivations, preferences, behavioural patterns
- Audience and intent signals — who is in-market, what they care about, in their own words
- Channel and campaign intelligence — what is working where, how to allocate effort
- Win/loss and conversion signals — why outreach converts or does not, and what to change
- Adjacent threats and opportunities — forces outside the current frame that affect growth
- Contextual and temporal signals — seasons, buying cycles, events, disruptions

**Outputs:** Structured intelligence briefs with confidence levels per claim, sourced and timestamped.

### Stage 2 — Content Generation
Transform intelligence into deployable content, grounded in the signals from Stage 1.

**Content types:**
- Social media posts — LinkedIn, Facebook/Meta, X (Twitter), Instagram, Google Business Profile
- Outreach copy — emails, LinkedIn messages, cold call scripts, ad copy, website copy
- Ad campaigns — creative concepts and copy for Facebook, Instagram, LinkedIn, Google Ads
- Campaign briefs — actionable briefs for creative and execution teams
- Personalisation and variants — segment-tailored content, A/B variants with testable hypotheses

**Key principle:** Every piece of content traces back to a specific signal or insight. No content is generated in a vacuum.

### Stage 3 — Multi-Channel Outreach
Deploy content across channels via direct API integrations.

**Capabilities:**
- Content deployment — publish and distribute across connected channels
- A/B testing — run experiments with variant content, track which angle wins
- Channel management — optimise presence based on performance data
- Campaign execution — coordinate timing and delivery across channels
- Personalisation at scale — adapt outreach per segment using intelligence layer

**MVP integrations (direct API):**
- LinkedIn (posts, messages)
- Email (via SendGrid, Mailgun, or similar)
- Facebook/Meta (posts, ads)
- Google Ads
- X (Twitter) — posts

### Stage 4 — Feedback & Refinement
Capture real-world engagement data and feed it back into Stage 1.

**Data captured:**
- Engagement metrics — likes, shares, comments, click-through rates
- Response rates — email replies, ad interactions, social engagement
- Resonance analysis — which messages, channels, and content types performed best, and why
- Performance data — conversion rates, ROI, cost-per-action
- Feedback loops — structured insights routed back to the intelligence layer

**Key principle:** Each cycle starts sharper than the last. The system accumulates campaign history and learns from real-world results.

---

## 6. User Experience & Interface

### 6.1 Interface Model
A chat-first conversational interface embedded within a web application. The chat is the primary workspace; the surrounding app provides navigation, campaign history, settings, and integrations management.

### 6.2 Conversational Interaction
The system detects intent and mode-switches naturally between research, content, outreach, and feedback within a single conversation thread. Users can direct the system explicitly ("Research competitor X") or let it infer the next step in the loop.

### 6.3 Ephemeral Interfaces
Purpose-built UI components materialise inline within the conversation when structured interaction is needed:

**Output → User (system presents findings):**
- Variant comparison grids — side-by-side A/B content with diff highlighting
- Channel performance maps — visual breakdown of results by channel
- Prospect and audience lists — filterable, sortable tables
- Intelligence briefs — structured cards with confidence indicators

**User → Output (user provides input):**
- Campaign brief forms — guided input for campaign parameters
- Audience definition panels — interactive segment builders
- Content approval flows — approve, edit, or reject generated content before deployment

**Clarification → User (system narrows scope):**
- Quick polls — single-click selection (e.g., "Which channel first?")
- Checklists — multi-select from relevant options (e.g., "Which competitors to track?")
- Sliders and toggles — set parameters like budget, aggressiveness, tone

### 6.4 Conversation-to-Dashboard Bridge
While the chat is primary, the web app shell provides:
- Campaign history and timeline view
- Aggregated performance dashboards
- Integration and API key management
- Team settings (for SMB multi-user)
- Saved intelligence briefs and templates

---

## 7. System Architecture

### 7.1 Multi-Agent Architecture (LangGraph)
The system is composed of specialised agents orchestrated via LangGraph, with a supervisor agent routing tasks and managing state across the loop.

```
┌──────────────────────────────────────────────┐
│              Supervisor Agent                │
│   (Intent detection, routing, state mgmt)    │
├──────────────────────────────────────────────┤
│                                              │
│  ┌────────────┐  ┌────────────┐              │
│  │  Research   │  │  Content   │              │
│  │   Agent     │  │   Agent    │              │
│  └────────────┘  └────────────┘              │
│                                              │
│  ┌────────────┐  ┌────────────┐              │
│  │  Outreach   │  │  Feedback  │              │
│  │   Agent     │  │   Agent    │              │
│  └────────────┘  └────────────┘              │
│                                              │
│  ┌────────────┐  ┌────────────┐              │
│  │  Ephemeral  │  │  Memory &  │              │
│  │  UI Agent   │  │  State     │              │
│  └────────────┘  └────────────┘              │
└──────────────────────────────────────────────┘
```

**Supervisor Agent** — Parses user intent, routes to the appropriate specialist agent, manages loop state, handles handoffs, and triggers ephemeral UI when structured interaction is needed.

**Research Agent** — Executes multi-hop research across signal sources. Supports parallelism (multiple dimensions investigated simultaneously) with bounded depth budgets. Produces structured, typed findings with confidence levels.

**Content Agent** — Generates content grounded in research outputs. Produces variants with testable hypotheses. Handles personalisation per segment.

**Outreach Agent** — Manages channel integrations, deploys content, sets up A/B tests, and handles scheduling and sequencing.

**Feedback Agent** — Ingests engagement and performance data from connected channels. Interprets signals against the hypotheses from A/B tests. Produces structured feedback that routes back to the Research Agent.

**Ephemeral UI Agent** — Generates purpose-built interface components within the conversation. Renders comparison grids, polls, forms, and data visualisations.

**Memory & State Module** — Maintains structured campaign history, accumulated intelligence, and loop state across sessions. Not freeform text — typed findings, confidence levels, and versioned campaign records.

### 7.2 State Management
LangGraph's state graph manages transitions between loop stages:
- Each node represents an agent or sub-task
- Edges define valid transitions and conditional routing
- State is typed and persistent across the conversation
- Graceful degradation — if an agent fails, the system surfaces the failure clearly and suggests alternatives rather than silently dropping context

### 7.3 Data Layer
- **Campaign store** — versioned records of every loop cycle: research inputs, content generated, outreach deployed, results captured
- **Intelligence accumulator** — compounding knowledge base that grows sharper with each cycle
- **User preferences and context** — tone, brand voice, target segments, channel priorities
- **Integration credentials** — securely stored API keys and OAuth tokens for connected channels

### 7.4 Integration Layer
Direct API integrations for MVP:

| Channel | Capability | API |
|---|---|---|
| LinkedIn | Posts, messages | LinkedIn Marketing API |
| Email | Send, track opens/clicks | SendGrid / Mailgun |
| Facebook/Meta | Posts, ad campaigns | Meta Graph API |
| Google Ads | Campaign creation, management | Google Ads API |
| X (Twitter) | Posts | X API v2 |

Future integrations (post-MVP): HubSpot, Salesforce, Google Analytics, Slack, Notion.

---

## 8. Technical Concepts

### 8.1 Signal Source Diversity
The Research Agent draws from multiple signal types: competitor ads (Meta Ad Library, Google Ads Transparency), audience forums (Reddit, community discussions), job postings (hiring patterns as strategy signals), funding activity (Crunchbase, press), search trends (Google Trends), and campaign engagement data from previous cycles.

### 8.2 Parallelism & Deep Research
Different signal dimensions are investigated simultaneously. Multi-hop research allows following chains of evidence (e.g., competitor launched product → check their ad spend → review audience reaction). Bounded depth budgets prevent runaway research — each query has a defined scope and time limit.

### 8.3 Intent Detection & Mode Switching
The conversation moves naturally between stages. The Supervisor Agent detects whether the user is asking for research, requesting content, directing outreach, or reviewing feedback — and routes accordingly. Explicit commands ("Research X") and implicit transitions ("OK, now let's write something for LinkedIn") are both supported.

### 8.4 Structured Outputs & Memory
All agent outputs are typed and structured — not freeform text:
- Research findings carry confidence levels, source attribution, and timestamps
- Content outputs include variant metadata, target segment, and testable hypotheses
- Campaign records are versioned and linkable
- Memory accumulates across sessions, so the 10th cycle is informed by the first nine

### 8.5 A/B Logic & Feedback Ingestion
Content variants are generated with explicit, testable hypotheses (e.g., "Pain-point framing will outperform benefit framing for mid-market CTOs"). Engagement signals are interpreted against those hypotheses, not just as raw metrics. The Feedback Agent translates results into actionable intelligence for the next cycle.

---

## 9. MVP Feature Set

### P0 — Must Have for Launch
- Conversational interface with intent detection across all four loop stages
- Research Agent with web search and competitive signal gathering
- Content Agent generating social posts, outreach emails, and ad copy with A/B variants
- Outreach Agent with at least two direct channel integrations (LinkedIn posts + email)
- Feedback Agent ingesting engagement data from connected channels
- Ephemeral UI for variant comparison, quick polls, and content approval
- Persistent campaign history across sessions
- Structured intelligence accumulation (findings carry forward between cycles)

### P1 — Should Have for Launch
- Additional channel integrations (Facebook, Google Ads, X)
- Ad campaign creation and management
- Segment-based personalisation for content variants
- Performance dashboards in the web app shell
- Export functionality (campaign briefs as PDF, content as formatted docs)

### P2 — Nice to Have / Fast Follow
- Team collaboration (multiple users, shared campaigns)
- Slack and Notion integrations for workflow embedding
- CRM integration (HubSpot, Salesforce) for lead-level feedback
- Scheduled campaigns and automated loop triggers
- Custom signal sources (user-defined RSS, API endpoints)
- White-label / API access for agencies

---

## 10. Non-Functional Requirements

### 10.1 Performance
- Research queries should return initial findings within 15–30 seconds
- Content generation should complete within 10–20 seconds per variant
- Outreach deployment should confirm within 5 seconds of user approval
- Ephemeral UI components should render within 1 second

### 10.2 Reliability
- 99.5% uptime target for the core platform
- Graceful degradation when third-party APIs are unavailable — surface the failure, do not silently skip
- State persistence — no data loss if a session disconnects

### 10.3 Security
- OAuth 2.0 for all channel integrations
- API keys encrypted at rest
- No storage of user credentials in plaintext
- SOC 2 Type I compliance as a target within 12 months of launch

### 10.4 Scalability
- Architecture should support horizontal scaling of individual agents
- LangGraph state should be externalisable to a persistent store (Redis, Postgres) for multi-instance deployment
- Rate limiting and queuing for outbound API calls to respect channel API limits

---

## 11. User Flows

### 11.1 First-Time Setup
1. User signs up and lands on onboarding
2. System asks: What channels do you want to connect? (LinkedIn, email, etc.)
3. User authenticates via OAuth for each channel
4. System asks: What is your product/company? Who is your target audience?
5. User provides context (conversationally or via a guided form)
6. System stores preferences and context — ready for the first loop

### 11.2 Running a Full Loop
1. User starts a conversation: "Our competitor just dropped prices by 20%. What should we do?"
2. **Research Agent** activates — gathers competitive signals, checks ad activity, scans audience reactions
3. System surfaces an intelligence brief via ephemeral UI — key findings with confidence levels
4. User reviews, asks follow-ups, narrows scope
5. **Content Agent** activates — generates LinkedIn post variants, email sequences, and ad copy, each grounded in specific findings
6. System presents a variant comparison grid — user selects, edits, or requests more options
7. User approves content and selects channels
8. **Outreach Agent** deploys — posts to LinkedIn, sends email sequence, launches ad
9. Over the next 24–72 hours, **Feedback Agent** ingests engagement data
10. System surfaces a performance summary — what resonated, what did not, and why
11. Intelligence is fed back into the accumulator — the next loop starts sharper

### 11.3 Mid-Cycle Intervention
At any point, the user can:
- Pause and redirect ("Actually, let's focus on email only")
- Inject new context ("I just heard from a customer that pricing is their top concern")
- Skip a stage ("Skip research, I already know what to say — just help me write it")
- Review past cycles ("What worked best in our last three campaigns?")

---

## 12. Metrics & Success Criteria

### Product Metrics
- **Loop completion rate** — % of users who complete a full Research → Content → Outreach → Feedback cycle
- **Time-to-action** — elapsed time from first message to content deployed
- **Cycle frequency** — how often users run the loop (target: weekly for active users)
- **Retention** — 30-day and 90-day retention rates

### Business Metrics
- **Activation rate** — % of signups who connect at least one channel and complete one loop
- **MRR growth** — monthly recurring revenue trajectory
- **Expansion revenue** — upgrades from solo plans to team plans

### Quality Metrics
- **Research accuracy** — user ratings of intelligence brief relevance and correctness
- **Content acceptance rate** — % of generated content approved without major edits
- **Feedback utility** — do users act on feedback insights in subsequent cycles?

---

## 13. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Third-party API changes or rate limits | Outreach breaks | High | Abstract integrations behind an adapter layer; queue outbound calls; monitor API changelogs |
| LLM hallucination in research | Bad intelligence leads to bad campaigns | Medium | Confidence levels on all claims; source attribution; user review gate before action |
| Solo founder bandwidth | Slow iteration, burnout | High | Ruthless MVP scoping; automate testing; use managed services over self-hosted |
| Channel API approval delays | LinkedIn/Meta API access can take weeks | High | Apply early; start with channels that have easier API access (email, X); use official partner programmes |
| User trust in autonomous outreach | Users hesitant to let AI post/send on their behalf | Medium | Always require explicit approval before deployment; show exactly what will be sent and where; start with draft-and-approve, not fire-and-forget |
| Data privacy and compliance | GDPR, CAN-SPAM, platform ToS | High | Build compliance checks into the Outreach Agent; opt-out handling; data retention policies |

---

## 14. Monetisation (Initial Thinking)

**Freemium model:**
- **Free tier** — limited loops per month (e.g., 5), one channel integration, basic research
- **Pro tier ($49–99/mo)** — unlimited loops, all channel integrations, full intelligence accumulation, campaign history
- **Team tier ($149–299/mo)** — multi-user, shared campaigns, priority support

Pricing to be validated through early user interviews and willingness-to-pay testing.

---

## 15. Development Roadmap

### Phase 1 — Foundation (Weeks 1–6)
- Set up LangGraph orchestration with Supervisor and Research agents
- Build the conversational interface (chat UI embedded in web app)
- Implement structured state management and memory
- Research Agent: web search, basic competitive signal gathering
- Ephemeral UI: simple text cards and quick polls

### Phase 2 — Content & Outreach (Weeks 7–12)
- Content Agent: social posts, emails, ad copy with A/B variants
- Outreach Agent: LinkedIn post integration + email (SendGrid)
- Ephemeral UI: variant comparison grids, content approval flow
- Campaign history persistence

### Phase 3 — Feedback & Loop Closure (Weeks 13–18)
- Feedback Agent: ingest engagement data from LinkedIn and email
- Intelligence accumulation: findings carry forward between cycles
- Performance summaries with resonance analysis
- Full loop operational end-to-end

### Phase 4 — Expansion (Weeks 19–24)
- Additional channels: Facebook, Google Ads, X
- Segment-based personalisation
- Performance dashboards in web app
- User onboarding and guided setup flow
- Beta launch

---

## 16. Open Questions

1. **Research depth vs. speed** — How deep should the Research Agent go before surfacing findings? Should depth be user-configurable, or should the system decide based on query complexity?
2. **Approval granularity** — Should every outreach action require explicit approval, or should users be able to set "auto-deploy" rules for certain channels/content types?
3. **Multi-brand support** — Should the MVP support users managing multiple brands or products, or is single-brand sufficient for launch?
4. **Compliance automation** — How much compliance checking (GDPR, CAN-SPAM, platform-specific rules) should be built into the Outreach Agent at launch vs. left to the user?
5. **Pricing validation** — What is the willingness-to-pay threshold for solo founders vs. SMB teams? Should pricing be usage-based (per loop) or seat-based?

---

## Appendix A: Glossary

- **Growth loop** — The continuous cycle of research, content creation, outreach, and feedback that drives marketing growth
- **Ephemeral interface** — A purpose-built UI component that appears inline within the conversation to present structured data or gather user input, then disappears when no longer needed
- **Signal** — Any data point from the market, competitors, customers, or campaign performance that informs strategy
- **Variant** — An alternative version of content created for A/B testing, with a specific hypothesis attached
- **Intelligence accumulator** — The persistent knowledge base that compounds findings across loop cycles
- **Bounded depth budget** — A limit on how deep or long the Research Agent will investigate a particular signal dimension before surfacing findings

---

*This is a living document. It will be updated as the product evolves through validation, user feedback, and development.*
