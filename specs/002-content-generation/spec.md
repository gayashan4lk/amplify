# Feature Specification: Content Generation (Facebook Post Variants)

**Feature Branch**: `002-content-generation`
**Created**: 2026-04-19
**Status**: Draft
**Input**: User description: "Stage 2 — Content Generation. Facebook posts only. Two variants of a single post (description + image) created from the intelligence brief produced in Stage 1. Content Generation Agent orchestrates the flow; image generation uses Google Nano Banana 2, text generation uses Anthropic Haiku. After the brief is rendered, the user clicks a button in chat to start generation. Before generating, the AI suggests what to create based on the brief and asks the user to describe what they want. Final output: two Facebook post variants (description with emojis + image)."

## Summary

This spec extends Amplify from "signal" (intelligence brief) to "action" (publishable
content) by adding a **Content Generation Agent** that turns a brief into two
ready-to-publish Facebook post variants — each variant being a post description
(with emojis) paired with a generated image. The flow is conversational: once the
brief is rendered, the user clicks a "Generate content" button inline in the chat;
the agent responds with a short list of suggested post angles grounded in the
brief's findings, then asks the user what they want. The user's reply (plus the
brief) becomes the creative brief for the agent, which then produces two distinct
variants the user can compare side-by-side.

Scope is intentionally narrow: one platform (Facebook), one format (single post, no
carousels / video / reels), one output (two variants), one chance to re-prompt by
regenerating. Publishing, scheduling, and multi-platform support are out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate two Facebook post variants from a brief (Priority: P1)

After an intelligence brief is rendered in chat (from Stage 1), the user clicks a
"Generate Facebook content" button attached to the brief. The agent replies with
2–4 suggested post angles grounded in specific findings from the brief (each
suggestion names the finding it draws from), then asks the user to describe what
they want the post to say, who it is for, and the tone. The user replies in plain
language. The agent then produces **two variants** of a single Facebook post,
each containing a post description (written with emojis, sized for Facebook) and
an accompanying image. Both variants are rendered inline in chat, side-by-side,
clearly labeled "Variant A" and "Variant B".

**Why this priority**: This is the whole feature. Without it, Stage 2 does not
exist. It is also the first time the product produces an artifact the user can
publish, closing the gap from "interesting insight" to "thing I can ship today".

**Independent Test**: Starting from a chat with a completed intelligence brief,
the user clicks the generate button, sees suggestions tied to the brief,
answers the follow-up question, and within a bounded time receives two distinct
variants (different descriptions AND different images), each rendered in chat.

**Acceptance Scenarios**:

1. **Given** an intelligence brief is rendered in the chat, **When** the user
   clicks the "Generate Facebook content" button on the brief, **Then** the
   agent replies in-thread with 2–4 suggested post angles, each referencing at
   least one specific finding from the brief.
2. **Given** the agent has presented suggestions, **When** the agent asks the
   user to describe what they want and the user replies, **Then** the agent
   acknowledges the input and begins generation with visible progress.
3. **Given** the agent has started generation, **When** generation completes,
   **Then** two variants are rendered side-by-side, each with a post
   description containing emojis and an image, both clearly labeled Variant A
   and Variant B.
4. **Given** two variants are rendered, **When** the user compares them, **Then**
   the descriptions differ meaningfully (not cosmetic rewording) and the images
   are visually distinct.
5. **Given** generation is in progress, **When** the user looks at the chat,
   **Then** they see which step is running (e.g., "drafting copy", "generating
   image") and roughly how long it is taking.

---

### User Story 2 - Regenerate or refine a variant (Priority: P2)

The user likes the direction of one variant but wants to try again — either to
regenerate that single variant with the same brief + intent, or to give
additional guidance ("make it punchier", "less formal", "use the pricing
finding instead"). The agent regenerates just that variant while leaving the
other untouched.

**Why this priority**: Creative output is rarely right on the first try. Without
a cheap path to iterate, users will abandon generated content and write it
themselves. This keeps them in the flow without making them restart the whole
chain.

**Independent Test**: With two variants rendered, the user requests a regenerate
(with or without extra guidance) on Variant A; Variant A is replaced with new
content; Variant B is unchanged.

**Acceptance Scenarios**:

1. **Given** two variants are rendered, **When** the user requests regeneration
   of Variant A without additional guidance, **Then** Variant A's description
   and image are both replaced with newly generated content and Variant B is
   unchanged.
2. **Given** two variants are rendered, **When** the user requests regeneration
   of Variant A with additional guidance in plain language, **Then** the new
   Variant A visibly reflects that guidance.

---

### User Story 3 - Copy a variant out of the app (Priority: P3)

The user has chosen a variant and wants to take it to Facebook. They need a
frictionless way to copy the post description to their clipboard and download
the image file, so they can paste and upload into Facebook's composer.

**Why this priority**: Without a clean export path, the user has to awkwardly
select and right-click — friction right at the moment of value capture. This
isn't critical for proving the concept (they could still copy manually) but it
materially affects perceived quality.

**Independent Test**: For a rendered variant, one action copies the description
to the clipboard; another action downloads the image as a file suitable for
Facebook upload.

**Acceptance Scenarios**:

1. **Given** a rendered variant, **When** the user triggers "copy description",
   **Then** the full description (including emojis) is placed on the clipboard.
2. **Given** a rendered variant, **When** the user triggers "download image",
   **Then** the image is saved locally in a format Facebook accepts.

---

### Edge Cases

- **Brief is thin or missing findings**: The suggestion step has little to
  ground on. The agent should still produce suggestions but must clearly flag
  low-confidence and invite the user to provide stronger direction.
- **User's follow-up reply is empty or off-topic**: The agent re-asks once; if
  still unusable, it proceeds using only the brief and flags that it did so.
- **User clicks generate twice in quick succession**: The second click is a
  no-op while a generation is in flight; the in-flight one is not duplicated.
- **Image generation fails but text succeeds (or vice versa)**: The variant is
  rendered as partial with a clear "image failed, retry" (or "description
  failed, retry") affordance rather than silently dropping the whole variant.
- **Both variants come back too similar**: The agent detects low diversity
  between Variant A and Variant B and retries once before rendering, so the
  user is not shown two near-duplicates.
- **Generated content contains emojis that render inconsistently**: Emojis are
  chosen from a conservative set known to render correctly in Facebook's
  composer and across mainstream devices.
- **User navigates away mid-generation**: On return, the in-progress generation
  is either still running and visible, or has completed and its result is
  attached to the brief it was started from (not lost).
- **Offensive / unsafe generated imagery or copy**: Content that trips safety
  policy is not rendered; the agent shows a brief explanation and asks the
  user to adjust their direction.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST render a "Generate Facebook content" action on
  every completed intelligence brief that appears in chat.
- **FR-002**: When the user activates that action, the Content Generation Agent
  MUST respond in the same chat thread with 2–4 suggested post angles, each
  citing at least one specific finding from the brief it was launched from.
- **FR-003**: After presenting suggestions, the agent MUST ask the user a single
  consolidated question for creative direction (what to say, who it's for,
  tone) and MUST wait for the user's reply before generating.
- **FR-004**: The agent MUST generate exactly two variants of a single Facebook
  post per run, each consisting of (a) a post description with emojis and (b)
  a generated image.
- **FR-005**: The two variants in a single run MUST be meaningfully different
  from each other — different angle, hook, or framing in the description and
  a visually distinct image.
- **FR-006**: Post descriptions MUST fit within Facebook's supported post
  length for the composer and MUST include at least one emoji used in a way
  that reads as natural (not emoji spam).
- **FR-007**: Images MUST be produced at a resolution and aspect ratio suitable
  for a Facebook feed post upload.
- **FR-008**: The system MUST show streaming progress during generation,
  indicating at minimum which sub-step is running (e.g., drafting copy,
  generating image) and which variant it applies to.
- **FR-009**: Users MUST be able to regenerate a single variant (A or B)
  independently, with the option to provide additional plain-language guidance,
  without affecting the other variant.
- **FR-010**: Users MUST be able to copy a variant's description to the
  clipboard and download its image as a file.
- **FR-011**: Each generated variant MUST retain a traceable link back to the
  brief it was generated from and to the user's creative-direction reply, so
  the user can see what input produced it.
- **FR-012**: If image generation fails but description succeeds (or vice
  versa) for a variant, the system MUST render the partial result and offer a
  targeted retry for just the failing half.
- **FR-013**: The system MUST prevent duplicate concurrent generation runs for
  the same brief triggered within a short window.
- **FR-014**: Content flagged by safety policy (unsafe imagery, prohibited
  claims) MUST NOT be rendered to the user; the agent MUST explain briefly why
  and invite the user to adjust direction.
- **FR-015**: Generation runs MUST complete (success or surfaced failure)
  within a bounded time budget, with a visible failure state if exceeded,
  rather than hanging indefinitely.

### Key Entities

- **Content Generation Request**: A single invocation tied to one intelligence
  brief and one user creative-direction reply. Contains: source brief
  reference, user's direction text, timestamp, status (suggesting / awaiting
  input / generating / complete / failed).
- **Post Variant**: One of two outputs per request. Contains: variant label (A
  or B), post description text (with emojis), image reference, partial-failure
  flags per half (description / image), link back to its Content Generation
  Request.
- **Post Suggestion**: A single suggested angle presented to the user before
  generation. Contains: suggestion text, the finding(s) from the brief it
  draws from.
- **Intelligence Brief (external, from Stage 1)**: The input. This feature
  reads it but does not own or modify it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From clicking "Generate Facebook content" to seeing both variants
  rendered, the median run completes in under 60 seconds, and 95% complete in
  under 120 seconds.
- **SC-002**: In at least 90% of runs, users rate the two variants as
  "meaningfully different from each other" (not cosmetic rewording) on a
  post-run check.
- **SC-003**: At least 70% of users who reach a rendered pair of variants
  either copy a description or download an image for at least one variant
  (i.e., perceive the output as usable, not just viewable).
- **SC-004**: Fewer than 5% of runs end in an unrendered failure state
  (complete timeout or both halves of both variants failing).
- **SC-005**: For users who regenerate a variant, fewer than 20% regenerate the
  same variant more than twice in a single session — indicating the second try
  is usually good enough.
- **SC-006**: At least 80% of users who start a generation run (click the
  button) reach a rendered pair of variants in that same session (i.e., don't
  abandon during the suggestions or creative-direction step).

## Assumptions

- Stage 1 (Research Agent + intelligence brief) is the upstream dependency and
  is already present in the chat when this feature is triggered. This feature
  does not invoke the research agent or modify briefs.
- Facebook is the only platform covered in this spec. Instagram, LinkedIn, X,
  TikTok, and multi-platform variants are out of scope.
- Only a single post format is supported: one description + one image per
  variant. Carousels, videos, reels, link previews, and albums are out of
  scope.
- Exactly two variants per run. One variant, three variants, or user-configurable
  variant count are out of scope.
- The user is the content creator / growth operator from Stage 1; no
  multi-user review, approval, or team workflow is assumed.
- Publishing, scheduling, cross-posting, and direct Facebook integration are
  out of scope. The feature ends at "user has a copied description and a
  downloaded image".
- Generated images are produced fresh per run; no user-uploaded source images
  or brand asset libraries are in scope for v1.
- Conservative safety defaults apply: the agent declines to generate political,
  adult, medical-claim, or otherwise policy-flagged content rather than
  attempting edge-case rewrites.
- The conversation-first, streaming-progress, and ephemeral-inline-UI
  primitives established in Stage 1 are reused here; this spec does not
  redefine them.
