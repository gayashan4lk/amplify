"""T080: anti-hallucination gate leaves zero findings → no_findings_above_threshold.

Crucially, NO IntelligenceBrief is persisted to Mongo — the research_node
raises before any persistence happens. This test asserts the raise and the
failure-code wiring; the persistence side is covered by inspection of
chat.py — the brief-persist path is only reached on a successful return.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agents.research import (
    EXCEPTION_TO_FAILURE_CODE,
    NoFindingsAboveThreshold,
    research_node,
)
from models.chat import SupervisorDecision
from models.errors import FailureCode
from models.research import (
    Finding,
    IntelligenceBrief,
    ResearchPlan,
    SourceAttribution,
    SubQuery,
)
from tests.integration._fakes import install_fake_llms, install_fake_tavily

NOW = datetime.now(UTC)

# Tavily fixture returns URLs the synthesis brief will never cite — so the
# filter step drops every finding and the gate raises.
TAVILY_FIXTURE = [
    {"title": "Irrelevant A", "url": "https://irrelevant.example/a", "content": "noise"},
    {"title": "Irrelevant B", "url": "https://irrelevant.example/b", "content": "noise"},
]


def _brief_with_fabricated_sources() -> IntelligenceBrief:
    return IntelligenceBrief(
        id="brief_temp",
        user_id="u1",
        conversation_id="c1",
        research_request_id="rq1",
        scoped_question="What's new?",
        status="complete",
        findings=[
            Finding(
                id=f"f{i}",
                rank=i,
                claim=f"Claim {i}.",
                evidence=f"Evidence {i}.",
                confidence="high",
                sources=[
                    SourceAttribution(
                        title="Ghost",
                        url=f"https://fabricated.example/{i}",  # type: ignore[arg-type]
                        source_type="news",
                        consulted_at=NOW,
                    )
                ],
            )
            for i in range(1, 4)
        ],
        generated_at=NOW,
        model_used="openai/gpt-4o",
    )


@pytest.mark.asyncio
async def test_no_findings_above_threshold_raises_and_is_mapped(monkeypatch):
    install_fake_tavily(monkeypatch, TAVILY_FIXTURE)
    install_fake_llms(
        monkeypatch,
        {
            "supervisor": SupervisorDecision(route="research", explanation="ok"),
            "research_plan": ResearchPlan(
                sub_queries=[
                    SubQuery(angle="market", query="q1"),
                    SubQuery(angle="market", query="q2"),
                    SubQuery(angle="market", query="q3"),
                ],
                rationale="cover the space",
            ),
            "research_synthesize": _brief_with_fabricated_sources(),
        },
    )

    state = {
        "messages": [{"role": "user", "content": "What's new?"}],
        "user_id": "u1",
        "conversation_id": "c1",
        "current_request": {"id": "rq1", "raw_question": "What's new?"},
    }

    with pytest.raises(NoFindingsAboveThreshold):
        await research_node(state)

    assert (
        EXCEPTION_TO_FAILURE_CODE[NoFindingsAboveThreshold]
        is FailureCode.no_findings_above_threshold
    )
