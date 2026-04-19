# Quickstart — Content Generation (Stage 2)

**Feature**: 002-content-generation
**Audience**: An engineer picking up implementation of this spec from
Phase 2 onward.

## What you get

From the user's side: an intelligence brief is rendered in chat, a
"Generate Facebook content" button appears on it, one click produces two
distinct Facebook post variants (description + 1080×1080 image) inline in
the chat, each with copy / download / regenerate affordances. Per-brief
persistence means the same variants reappear on page refresh and in future
sessions.

## Prerequisites

- Stage 1 (`001-research-agent`) merged and running end-to-end.
- Anthropic API key wired into the `llm_router` (`ANTHROPIC_API_KEY`).
- Google AI Studio / Vertex credentials for Nano Banana 2
  (`GOOGLE_API_KEY` or service-account creds).
- Object storage bucket + credentials (per the pending backend-hosting
  ADR). Env vars expected: `IMAGE_STORE_BUCKET`, `IMAGE_STORE_REGION`,
  and either access-key pair or workload identity per host.
- Redis reachable (already required by ARQ in Stage 1).

## Local dev walkthrough

1. `pnpm --filter web dev` and `uv run --package api uvicorn main:app --reload`
   as in Stage 1.
2. Sign in, start a chat, ask a research question to produce an
   intelligence brief (Stage 1 path — unchanged).
3. On the rendered brief, click **Generate Facebook content**.
4. Observe the SSE stream: a `content_suggestions` event should arrive,
   followed by the agent's consolidated creative-direction question.
5. Reply in chat with your direction (e.g., "upbeat, for small-business
   owners, call out the onboarding-speed finding").
6. Watch `content_variant_progress` events interleave for Variants A and B;
   then `content_variant_ready` for each.
7. Use **Copy description** / **Download image** / **Regenerate** on
   either variant.

## Happy-path smoke test (E2E)

Playwright spec: `apps/web/e2e/content-generation.spec.ts`

1. Log in as a seeded user with a pre-generated brief.
2. Click **Generate Facebook content**.
3. Assert suggestions render within 10s and reference a finding id.
4. Submit a direction; assert two variants render within 120s.
5. Assert each description length ∈ [80, 250] and includes an emoji.
6. Assert each image is 1080×1080.
7. Click regenerate on Variant A once; assert `regenerations_used == 1`
   and Variant B is untouched.

## Key failure paths to verify manually

- Kill the Nano Banana 2 call mid-run (mock 500) → expect a
  `content_variant_partial` with `retry_target: "image"` and a visible
  retry button.
- Trigger safety block on copy → expect a visible `error` event with the
  explanation, no variant rendered.
- Click **Generate** twice quickly → second click is a no-op
  (`202 already_running`).
- Hit the regeneration cap (3 times on Variant A) → fourth click is
  disabled and shows "no regenerations left".

## Where the code lives

- Agent: `apps/api/agents/content_generation.py` (LangGraph node, prompts).
- Router: `apps/api/routers/content.py` (REST endpoints).
- Tools: `apps/api/tools/generate_copy.py`, `apps/api/tools/generate_image.py`.
- Services: `apps/api/services/content_store.py`,
  `apps/api/services/image_store.py`,
  `apps/api/services/inflight_lock.py`.
- Schemas: `apps/api/models/content.py`,
  `apps/web/lib/schemas/content.ts` (generated).
- UI: `apps/web/components/ephemeral/content-variant-grid.tsx` +
  `content-suggestions.tsx` + `variant-card.tsx`.

## Rollout notes

- The feature is additive; no Stage 1 surfaces change. The only visible
  diff on an existing brief is the new inline button.
- Feature-flag via env: `CONTENT_GEN_ENABLED=true`. Off by default in
  production until the object-storage ADR is resolved.
- Observability: every run has a LangSmith trace rooted at the Supervisor
  → Content transition; variant regenerations inherit the request trace id.
