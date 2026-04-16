# Amplify

Conversational, AI-powered system that compresses the marketing growth loop
(Research → Content → Outreach → Feedback) into a single continuous workflow.

## Structure

```
amplify/
├── apps/
│   ├── api/          # FastAPI backend (LangGraph agents, SSE streaming)
│   └── web/          # Next.js 16 frontend (chat + ephemeral UI)
├── docs/             # PRD, SAD, ADR
├── specs/            # Spec-driven development artifacts
└── .specify/         # Speckit memory + templates
```

## Current slice

**001-research-agent** — the first shippable slice: conversational research with
inline structured intelligence briefs. See
[`specs/001-research-agent/quickstart.md`](specs/001-research-agent/quickstart.md)
for local setup and verification.

## Governing documents

- Constitution: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- PRD: [`docs/PRD-Amplify.md`](docs/PRD-Amplify.md)
- SAD: [`docs/SAD-Amplify.md`](docs/SAD-Amplify.md)
- ADR: [`docs/ADR-Amplify.md`](docs/ADR-Amplify.md)
