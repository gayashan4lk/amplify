# Schema Contract — ContentGenerationRequest

**Feature**: 002-content-generation
**Schema version**: 1
**Source of truth**: Pydantic v2 models in
`apps/api/models/content.py` (to be created). Zod mirrors are generated
into `apps/web/lib/schemas/content.ts`.

## Pydantic (authoritative)

```python
# apps/api/models/content.py
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, conint, constr

class RequestStatus(str, Enum):
    SUGGESTING = "suggesting"
    AWAITING_INPUT = "awaiting_input"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"

class HalfStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"

class PostSuggestion(BaseModel):
    id: str
    text: constr(min_length=1, max_length=140)
    finding_ids: list[str] = Field(min_length=1)
    low_confidence: bool = False

class PostVariant(BaseModel):
    label: Literal["A", "B"]
    description: constr(min_length=80, max_length=250)
    description_status: HalfStatus = HalfStatus.PENDING
    image_key: Optional[str] = None
    image_signed_url: Optional[str] = None
    image_width: Literal[1080] = 1080
    image_height: Literal[1080] = 1080
    image_status: HalfStatus = HalfStatus.PENDING
    regenerations_used: conint(ge=0, le=3) = 0
    source_suggestion_id: Optional[str] = None
    generation_trace_id: str
    updated_at: datetime

class ContentGenerationRequest(BaseModel):
    id: str
    brief_id: str
    conversation_id: str
    user_id: str
    status: RequestStatus
    suggestions: list[PostSuggestion] = Field(default_factory=list, max_length=4)
    user_direction: Optional[str] = None
    variants: list[PostVariant] = Field(default_factory=list, max_length=2)
    diversity_warning: bool = False
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_ref: Optional[str] = None
    schema_version: Literal[1] = 1
```

## Cross-field constraints

- `variants` length ∈ {0, 1, 2}; validator rejects > 2.
- `suggestions` length ∈ {0} ∪ {2, 3, 4}; never exactly 1.
- `completed_at` present iff `status ∈ {COMPLETE, FAILED}`.
- `user_direction` present iff `status ∈ {GENERATING, COMPLETE, FAILED}`.
- `error_ref` present iff `status == FAILED`.
- Each `PostVariant.description` MUST pass the emoji-safelist check
  (validated by a reusable `validate_description_emoji` helper).

## Zod (generated, illustrative)

```ts
// apps/web/lib/schemas/content.ts
import { z } from "zod";

export const PostSuggestion = z.object({
  id: z.string(),
  text: z.string().min(1).max(140),
  finding_ids: z.array(z.string()).min(1),
  low_confidence: z.boolean(),
});

export const PostVariant = z.object({
  label: z.enum(["A", "B"]),
  description: z.string().min(80).max(250),
  description_status: z.enum(["pending", "ready", "failed"]),
  image_key: z.string().nullable(),
  image_signed_url: z.string().nullable(),
  image_width: z.literal(1080),
  image_height: z.literal(1080),
  image_status: z.enum(["pending", "ready", "failed"]),
  regenerations_used: z.number().int().min(0).max(3),
  source_suggestion_id: z.string().nullable(),
  generation_trace_id: z.string(),
  updated_at: z.string().datetime(),
});

export const ContentGenerationRequest = z.object({
  id: z.string(),
  brief_id: z.string(),
  conversation_id: z.string(),
  user_id: z.string(),
  status: z.enum(["suggesting", "awaiting_input", "generating", "complete", "failed"]),
  suggestions: z.array(PostSuggestion).max(4),
  user_direction: z.string().nullable(),
  variants: z.array(PostVariant).max(2),
  diversity_warning: z.boolean(),
  started_at: z.string().datetime(),
  completed_at: z.string().datetime().nullable(),
  error_ref: z.string().nullable(),
  schema_version: z.literal(1),
});
```

## Contract tests (required)

- Pydantic round-trip for every terminal state.
- Zod `.safeParse` for each SSE event payload carrying this schema.
- Length-boundary tests: 79-char description (reject), 80 (accept), 250
  (accept), 251 (reject).
- Emoji safelist test: non-safelisted emoji rejected with a clear error.
- Regeneration cap: 4th increment rejected.
- Variants ≤ 2: adding a third variant rejected.
