"""Pydantic schemas for inline ephemeral UI components rendered in the chat."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from models.content import PostSuggestion, PostVariant
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


class ContentSuggestionsListPayload(BaseModel):
    request_id: str
    suggestions: list[PostSuggestion] = Field(..., max_length=4)
    question: str


class ContentSuggestionsListComponent(BaseModel):
    component_type: Literal["content_suggestions"] = "content_suggestions"
    component: ContentSuggestionsListPayload


class ContentVariantGridPayload(BaseModel):
    request_id: str
    variants: list[PostVariant] = Field(..., max_length=2)
    diversity_warning: bool = False
    regeneration_caps: dict[Literal["A", "B"], int] = Field(default_factory=dict)


class ContentVariantGridComponent(BaseModel):
    component_type: Literal["content_variant_grid"] = "content_variant_grid"
    component: ContentVariantGridPayload


EphemeralComponent = Annotated[
    IntelligenceBriefComponent
    | ClarificationPollComponent
    | ContentSuggestionsListComponent
    | ContentVariantGridComponent,
    Field(discriminator="component_type"),
]
