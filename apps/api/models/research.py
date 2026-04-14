"""Authoritative Pydantic schema for the Research Agent output.

Mirrors specs/001-research-agent/contracts/intelligence-brief.md exactly.
Structural invariants that go beyond type checks (anti-hallucination gate,
status derivation, contradiction symmetry) are enforced in agents/research.py
before the brief is persisted — not here.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

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

SubQueryAngle = Literal[
    "competitive",
    "audience",
    "market",
    "channel",
    "temporal",
    "adjacent",
]


class SourceAttribution(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    url: HttpUrl
    source_type: SourceType
    consulted_at: datetime
    accessible: bool = True
    snippet: str | None = Field(default=None, max_length=500)


class Finding(BaseModel):
    id: str
    rank: int = Field(..., ge=1)
    claim: str = Field(..., min_length=1, max_length=280)
    evidence: str = Field(..., min_length=1, max_length=1200)
    confidence: Confidence
    sources: list[SourceAttribution] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    unsourced: bool = False
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _sources_or_unsourced(self) -> "Finding":
        # Invariant 2: unsourced findings must have notes explaining why.
        if self.unsourced:
            if not self.notes:
                raise ValueError("unsourced finding must set `notes`")
        else:
            if len(self.sources) < 1:
                raise ValueError("finding must have >= 1 source unless unsourced=True")
        return self

    @model_validator(mode="after")
    def _high_confidence_threshold(self) -> "Finding":
        # Invariant 3: high confidence requires 2+ sources OR 1 strong source.
        if self.confidence == "high" and not self.unsourced:
            strong = {"news", "official", "competitor_site"}
            if not (
                len(self.sources) >= 2
                or (len(self.sources) == 1 and self.sources[0].source_type in strong)
            ):
                raise ValueError("confidence=high requires 2+ sources or 1 strong source_type")
        return self


class IntelligenceBrief(BaseModel):
    id: str
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

    @field_validator("v")
    @classmethod
    def _version_is_one(cls, v: int) -> int:
        if v != 1:
            raise ValueError("IntelligenceBrief.v must be 1")
        return v


class SubQuery(BaseModel):
    angle: SubQueryAngle
    query: str = Field(..., max_length=200)


class ResearchPlan(BaseModel):
    sub_queries: list[SubQuery] = Field(..., min_length=3, max_length=5)
    rationale: str
