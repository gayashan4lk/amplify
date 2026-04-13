# Contract: IntelligenceBrief Schema

**Feature**: 001-research-agent
**Scope**: The canonical Pydantic schema for the `IntelligenceBrief`,
`Finding`, and `SourceAttribution` types. This is the structured output of the
Research Agent and the payload of the `intelligence_brief` ephemeral UI
component.

This contract is the source of truth. Both the backend (`apps/api/models/research.py`)
and the frontend (`apps/web/lib/types/sse-events.ts`, generated) MUST conform.

---

## Schema (Pydantic, authoritative)

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl

Confidence = Literal["high", "medium", "low"]

SourceType = Literal[
    "news",
    "blog",
    "forum",
    "competitor_site",
    "official",
    "ad_library",
    "analytics",
    "other",
]

BriefStatus = Literal["complete", "low_confidence"]


class SourceAttribution(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    url: HttpUrl
    source_type: SourceType
    consulted_at: datetime
    accessible: bool = True
    snippet: str | None = Field(default=None, max_length=500)


class Finding(BaseModel):
    id: str                              # uuid4, stable within a brief
    rank: int = Field(..., ge=1)
    claim: str = Field(..., min_length=1, max_length=280)
    evidence: str = Field(..., min_length=1, max_length=1200)
    confidence: Confidence
    sources: list[SourceAttribution] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)   # finding ids
    unsourced: bool = False
    notes: str | None = Field(default=None, max_length=500)


class IntelligenceBrief(BaseModel):
    id: str                              # MongoDB ObjectId as string
    v: int = 1
    user_id: str
    conversation_id: str
    research_request_id: str
    scoped_question: str = Field(..., min_length=1, max_length=1000)
    status: BriefStatus
    findings: list[Finding] = Field(..., min_length=1)
    generated_at: datetime
    model_used: str
    trace_id: str | None = None
```

---

## Invariants (enforced beyond Pydantic type checks)

These are enforced in `apps/api/agents/research.py` before the brief is
persisted or emitted.

1. **Source existence (anti-hallucination).** Every `SourceAttribution.url` in
   every `Finding.sources` MUST match a URL returned by Tavily for this
   research request. Any finding whose sources fail this check is dropped or
   rewritten before the brief is finalized. This is the primary enforcement
   of SC-004.

2. **Unsourced findings.** A finding with `unsourced == True` MUST have
   `notes` set explaining why (e.g., "no public source available; interpretive
   synthesis") and is always rendered with a visible "unsourced" label in the
   UI.

3. **High-confidence threshold.** `confidence == "high"` requires either:
   - `len(sources) >= 2`, OR
   - `len(sources) == 1` AND that source's `source_type in {"news",
     "official", "competitor_site"}`.

4. **Status derivation.**
   ```
   status = "complete" if (
       len(findings) >= 3
       and any(f.confidence == "high" for f in findings)
   ) else "low_confidence"
   ```
   A brief with `status == "low_confidence"` is still rendered but the UI
   explicitly labels it as such; the Supervisor may proactively suggest
   narrowing.

5. **Contradictions are explicit.** If two findings disagree, BOTH must carry
   the other's id in their `contradicts` list, and the UI must render the
   disagreement visibly (per FR-017).

6. **Accessibility disclosure.** When a `SourceAttribution.accessible ==
   False`, the parent Finding's `notes` MUST mention it (FR-028).

7. **Row-level isolation.** `IntelligenceBrief.user_id` MUST equal the
   authenticated user at every read; `brief_store.py` enforces this by
   construction and tests assert cross-user isolation.

---

## Example brief

```json
{
  "id": "6628f2a1c0a9b2f4d1e37a99",
  "v": 1,
  "user_id": "user_01H…",
  "conversation_id": "conv_01H…",
  "research_request_id": "req_01H…",
  "scoped_question": "What is Acme Corp doing on LinkedIn this month?",
  "status": "complete",
  "findings": [
    {
      "id": "fnd_01",
      "rank": 1,
      "claim": "Acme shifted messaging from cost savings to AI-powered forecasting in April 2026.",
      "evidence": "Four of Acme's last six LinkedIn posts (2026-04-02 through 2026-04-11) lead with AI-forecasting language; prior posts emphasized cost reduction.",
      "confidence": "high",
      "sources": [
        {
          "title": "Acme Corp LinkedIn post — April 11",
          "url": "https://www.linkedin.com/posts/acme-corp-…",
          "source_type": "competitor_site",
          "consulted_at": "2026-04-13T14:22:03Z",
          "accessible": true,
          "snippet": "Forecast confidence you can act on. Our AI engine…"
        },
        {
          "title": "TechCrunch — Acme launches AI forecasting suite",
          "url": "https://techcrunch.com/2026/04/08/acme-ai-forecasting/",
          "source_type": "news",
          "consulted_at": "2026-04-13T14:22:05Z",
          "accessible": true
        }
      ],
      "contradicts": [],
      "unsourced": false,
      "notes": null
    }
  ],
  "generated_at": "2026-04-13T14:22:42Z",
  "model_used": "openai/gpt-4o-2024-11",
  "trace_id": "ls_run_abc123"
}
```
