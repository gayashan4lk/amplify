"""Failure taxonomy — mirrors the Prisma FailureCode enum and SSE error contract."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class FailureCode(StrEnum):
    tavily_unavailable = "tavily_unavailable"
    tavily_rate_limited = "tavily_rate_limited"
    llm_unavailable = "llm_unavailable"
    llm_invalid_output = "llm_invalid_output"
    no_findings_above_threshold = "no_findings_above_threshold"
    user_cancelled = "user_cancelled"
    budget_exceeded = "budget_exceeded"
    rate_limited_user = "rate_limited_user"


class FailureRecord(BaseModel):
    id: str
    code: FailureCode
    recoverable: bool
    user_message: str = Field(..., min_length=1)
    suggested_action: str | None = None
    trace_id: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _recoverable_requires_action(self) -> "FailureRecord":
        if self.recoverable and not self.suggested_action:
            raise ValueError("recoverable failure must carry a suggested_action")
        generic = {"", "something went wrong", "an error occurred", "unknown error"}
        if self.user_message.strip().lower() in generic:
            raise ValueError("user_message must be specific — no generic fallbacks")
        return self


class ApiError(BaseModel):
    code: str
    message: str
    recoverable: bool = False


class ApiErrorEnvelope(BaseModel):
    error: ApiError
