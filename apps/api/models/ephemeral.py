"""Pydantic schemas for inline ephemeral UI components rendered in the chat."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from models.research import IntelligenceBrief


class IntelligenceBriefComponent(BaseModel):
    component_type: Literal["intelligence_brief"] = "intelligence_brief"
    component: IntelligenceBrief


class ClarificationPollPayload(BaseModel):
    research_request_id: str
    prompt: str
    options: list[str] = Field(..., min_length=3, max_length=4)


class ClarificationPollComponent(BaseModel):
    component_type: Literal["clarification_poll"] = "clarification_poll"
    component: ClarificationPollPayload


EphemeralComponent = Annotated[
    IntelligenceBriefComponent | ClarificationPollComponent,
    Field(discriminator="component_type"),
]
