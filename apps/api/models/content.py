"""Pydantic models for content generation (Stage 2).

Source of truth for `ContentGenerationRequest`, `PostVariant`,
`PostSuggestion`. The Zod mirror in `apps/web/lib/schemas/content.ts` is
generated from this module (T015).

See specs/002-content-generation/contracts/content-generation-request.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Conservative Facebook-safe emoji safelist. Every description must contain
# at least one character from this set and must NOT contain any emoji outside
# of it. Kept intentionally small to minimise cross-platform render drift.
ALLOWED_EMOJI: frozenset[str] = frozenset(
    [
        "✨",
        "🎯",
        "🚀",
        "💡",
        "🔥",
        "⭐",
        "✅",
        "📣",
        "📈",
        "🙌",
        "👀",
        "💬",
        "❤️",
        "🎉",
        "⚡",
        "🛠️",
        "🧠",
        "🤝",
    ]
)

# Broad emoji-codepoint detector (pictographic ranges). Anything detected as
# an emoji but not in ALLOWED_EMOJI is rejected.
_EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F300, 0x1FAFF),  # Misc symbols, pictographs, supplementals
    (0x2600, 0x27BF),  # Misc symbols + Dingbats
    (0x1F000, 0x1F2FF),  # Mahjong/domino/playing cards/enclosed
)


def _is_emoji_codepoint(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def validate_description_emoji(text: str) -> str:
    """Raise ValueError if `text` lacks an allowed emoji or contains a
    disallowed one. Returns `text` unchanged on success. Exported for reuse
    in the variant-diversity / copy-length pipelines (FR-006)."""

    # First, scan for any emoji-looking codepoints and ensure each is in the
    # safelist. We iterate characters; compound emoji (e.g. "❤️") composed
    # of base + variation selector are accepted as long as the base is in
    # the safelist.
    found_allowed = False
    i = 0
    while i < len(text):
        ch = text[i]
        # Peek for a VS16 (U+FE0F) that forms "❤️".
        combined = ch
        if i + 1 < len(text) and text[i + 1] == "\ufe0f":
            combined = ch + "\ufe0f"
        if combined in ALLOWED_EMOJI or ch in ALLOWED_EMOJI:
            found_allowed = True
            i += len(combined)
            continue
        if _is_emoji_codepoint(ch):
            raise ValueError(
                f"description contains disallowed emoji {ch!r}; "
                f"only the conservative safelist is permitted"
            )
        i += 1
    if not found_allowed:
        raise ValueError("description must contain at least one allowed emoji")
    return text


class RequestStatus(StrEnum):
    SUGGESTING = "suggesting"
    AWAITING_INPUT = "awaiting_input"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


class HalfStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


VariantLabel = Literal["A", "B"]


class PostSuggestion(BaseModel):
    id: str
    text: str = Field(..., min_length=1, max_length=140)
    finding_ids: list[str] = Field(..., min_length=1)
    low_confidence: bool = False


class PostVariant(BaseModel):
    label: VariantLabel
    description: str = Field(..., min_length=80, max_length=250)
    description_status: HalfStatus = HalfStatus.PENDING
    image_key: str | None = None
    image_signed_url: str | None = None
    image_width: Literal[1080] = 1080
    image_height: Literal[1080] = 1080
    image_status: HalfStatus = HalfStatus.PENDING
    regenerations_used: int = Field(0, ge=0, le=3)
    source_suggestion_id: str | None = None
    generation_trace_id: str
    updated_at: datetime

    @field_validator("description")
    @classmethod
    def _validate_description_emoji(cls, v: str) -> str:
        return validate_description_emoji(v)


class ContentGenerationRequest(BaseModel):
    id: str
    brief_id: str
    conversation_id: str
    user_id: str
    status: RequestStatus
    suggestions: list[PostSuggestion] = Field(default_factory=list, max_length=4)
    user_direction: str | None = None
    variants: list[PostVariant] = Field(default_factory=list, max_length=2)
    diversity_warning: bool = False
    started_at: datetime
    completed_at: datetime | None = None
    error_ref: str | None = None
    schema_version: Literal[1] = 1

    @field_validator("suggestions")
    @classmethod
    def _suggestions_not_exactly_one(
        cls, v: list[PostSuggestion]
    ) -> list[PostSuggestion]:
        if len(v) == 1:
            raise ValueError("suggestions length must be 0 or 2-4, never exactly 1")
        return v

    @model_validator(mode="after")
    def _cross_field(self) -> ContentGenerationRequest:
        terminal = {RequestStatus.COMPLETE, RequestStatus.FAILED}
        if (self.completed_at is not None) != (self.status in terminal):
            raise ValueError(
                "completed_at must be present iff status in {complete, failed}"
            )
        direction_required = {
            RequestStatus.GENERATING,
            RequestStatus.COMPLETE,
            RequestStatus.FAILED,
        }
        if self.status in direction_required and self.user_direction is None:
            raise ValueError(
                "user_direction is required once status advances past awaiting_input"
            )
        if (self.error_ref is not None) != (self.status == RequestStatus.FAILED):
            raise ValueError("error_ref must be present iff status == failed")
        return self


__all__ = [
    "ALLOWED_EMOJI",
    "ContentGenerationRequest",
    "HalfStatus",
    "PostSuggestion",
    "PostVariant",
    "RequestStatus",
    "VariantLabel",
    "validate_description_emoji",
]
