"""Chat request/response payloads and LangGraph-internal decision types."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(..., max_length=4000)
    reconnect: bool = False


class ClarificationResponse(BaseModel):
    selected_option_index: int = Field(..., ge=0)


class EphemeralResponseRequest(BaseModel):
    conversation_id: str
    research_request_id: str
    component_type: Literal["clarification_poll"]
    response: ClarificationResponse


ProgressPhase = Literal["planning", "searching", "synthesizing", "validating"]


class ProgressEvent(BaseModel):
    at: datetime
    phase: ProgressPhase
    message: str
    detail: dict[str, Any] | None = None


SupervisorRoute = Literal[
    "research",
    "clarification_needed",
    "out_of_scope",
    "followup_on_existing_brief",
]


class SupervisorDecision(BaseModel):
    route: SupervisorRoute
    scoped_question: str | None = None
    clarification_options: list[str] | None = None
    target_finding_id: str | None = None
    explanation: str
