"""Typed SSE event protocol. Version 1.

Every event emitted by POST /api/v1/chat/stream is one of these Pydantic
models. The discriminator is the `type` field; clients validate the
`v: 1` version tag and reject mismatches.

Source of truth: specs/001-research-agent/contracts/sse-events.md.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from models.content import HalfStatus, PostSuggestion, PostVariant, VariantLabel
from models.ephemeral import EphemeralComponent


class _EventBase(BaseModel):
    v: Literal[1] = 1
    conversation_id: str
    at: datetime


class ConversationReady(_EventBase):
    type: Literal["conversation_ready"] = "conversation_ready"
    is_new: bool


AgentName = Literal["supervisor", "research", "clarification"]


class AgentStart(_EventBase):
    type: Literal["agent_start"] = "agent_start"
    agent: AgentName
    description: str


class AgentEnd(_EventBase):
    type: Literal["agent_end"] = "agent_end"
    agent: AgentName


class ToolCall(_EventBase):
    type: Literal["tool_call"] = "tool_call"
    tool: str
    input: dict[str, Any]


class ToolResult(_EventBase):
    type: Literal["tool_result"] = "tool_result"
    tool: str
    result_count: int
    duration_ms: int


ProgressPhase = Literal["planning", "searching", "synthesizing", "validating"]


class Progress(_EventBase):
    type: Literal["progress"] = "progress"
    phase: ProgressPhase
    message: str
    detail: dict[str, Any] | None = None


class TextDelta(_EventBase):
    type: Literal["text_delta"] = "text_delta"
    message_id: str
    delta: str


class EphemeralUI(_EventBase):
    type: Literal["ephemeral_ui"] = "ephemeral_ui"
    message_id: str
    component_type: Literal[
        "intelligence_brief",
        "clarification_poll",
        "content_suggestions",
        "content_variant_grid",
    ]
    component: Any  # Validated via EphemeralComponent in callers.

    def with_component(self, ephemeral: EphemeralComponent) -> "EphemeralUI":
        return self.model_copy(
            update={
                "component_type": ephemeral.component_type,
                "component": ephemeral.component.model_dump(mode="json"),
            }
        )


ErrorCode = Literal[
    "tavily_unavailable",
    "tavily_rate_limited",
    "llm_unavailable",
    "llm_invalid_output",
    "no_findings_above_threshold",
    "user_cancelled",
    "budget_exceeded",
    "rate_limited_user",
    "content_gen_blocked",
    "content_gen_timeout",
    "content_safety_blocked",
]


class ContentSuggestionsEvent(_EventBase):
    type: Literal["content_suggestions"] = "content_suggestions"
    message_id: str
    request_id: str
    suggestions: list[PostSuggestion]
    question: str


class ContentVariantProgress(_EventBase):
    type: Literal["content_variant_progress"] = "content_variant_progress"
    request_id: str
    variant_label: VariantLabel
    step: str
    progress_hint: float | None = None


class ContentVariantReady(_EventBase):
    type: Literal["content_variant_ready"] = "content_variant_ready"
    request_id: str
    variant: PostVariant


class ContentVariantPartial(_EventBase):
    type: Literal["content_variant_partial"] = "content_variant_partial"
    request_id: str
    variant_label: VariantLabel
    description_status: HalfStatus
    image_status: HalfStatus
    description: str | None = None
    image_signed_url: str | None = None
    retry_target: Literal["description", "image"]


class ErrorEvent(_EventBase):
    type: Literal["error"] = "error"
    code: ErrorCode
    message: str = Field(..., min_length=1)
    recoverable: bool
    suggested_action: str | None = None
    failure_record_id: str
    trace_id: str | None = None


class Done(_EventBase):
    type: Literal["done"] = "done"
    final_status: Literal["brief_ready", "text_only", "awaiting_clarification"]
    summary: str | None = None


SseEvent = Annotated[
    ConversationReady
    | AgentStart
    | AgentEnd
    | ToolCall
    | ToolResult
    | Progress
    | TextDelta
    | EphemeralUI
    | ContentSuggestionsEvent
    | ContentVariantProgress
    | ContentVariantReady
    | ContentVariantPartial
    | ErrorEvent
    | Done,
    Field(discriminator="type"),
]
