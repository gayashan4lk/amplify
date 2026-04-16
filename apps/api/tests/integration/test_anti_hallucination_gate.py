"""T054: the synthesis LLM emits a fabricated URL; the gate drops it.

Crucial enforcement of SC-004 (zero fabricated source attributions).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agents.research import research_node
from models.chat import SupervisorDecision
from models.research import (
    Finding,
    IntelligenceBrief,
    ResearchPlan,
    SourceAttribution,
    SubQuery,
)
from tests.integration._fakes import install_fake_llms, install_fake_tavily

NOW = datetime.now(UTC)

TAVILY_FIXTURE = [
    {
        "title": "Real page",
        "url": "https://real.example.com/one",
        "content": "Something real.",
    },
    {
        "title": "Another real page",
        "url": "https://real.example.com/two",
        "content": "More real content.",
    },
    {
        "title": "Third real page",
        "url": "https://real.example.com/three",
        "content": "Even more real content.",
    },
]


def _finding(fid: str, url: str, confidence: str = "high", rank: int = 1) -> Finding:
    return Finding(
        id=fid,
        rank=rank,
        claim=f"Claim {fid}.",
        evidence=f"Evidence {fid} drawn from a real page on real.example.com.",
        confidence=confidence,  # type: ignore[arg-type]
        sources=[
            SourceAttribution(
                title="Src",
                url=url,  # type: ignore[arg-type]
                source_type="news",
                consulted_at=NOW,
            )
        ],
    )


def _brief_with_fabricated() -> IntelligenceBrief:
    # f_bad points at a URL not present in the Tavily fixture.
    findings = [
        _finding("f_good_1", "https://real.example.com/one", "high", 1),
        _finding("f_good_2", "https://real.example.com/two", "high", 2),
        _finding("f_good_3", "https://real.example.com/three", "high", 3),
        _finding("f_bad", "https://fabricated.example.com/ghost", "high", 4),
    ]
    return IntelligenceBrief(
        id="brief_temp",
        user_id="u1",
        conversation_id="c1",
        research_request_id="rq1",
        scoped_question="What's new?",
        status="complete",
        findings=findings,
        generated_at=NOW,
        model_used="openai/gpt-4o",
    )


@pytest.mark.asyncio
async def test_fabricated_urls_are_stripped(monkeypatch):
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
            "research_synthesize": _brief_with_fabricated(),
        },
    )

    state = {
        "messages": [{"role": "user", "content": "What's new?"}],
        "user_id": "u1",
        "conversation_id": "c1",
        "current_request": {"id": "rq1", "raw_question": "What's new?"},
    }
    out = await research_node(state)
    brief = out["brief"]

    fixture_urls = {r["url"] for r in TAVILY_FIXTURE}
    fabricated = "https://fabricated.example.com/ghost"
    for f in brief["findings"]:
        for s in f["sources"]:
            url = str(s["url"]).rstrip("/")
            assert url != fabricated.rstrip("/")
            assert url in {u.rstrip("/") for u in fixture_urls}
    # The three real findings must survive.
    assert len(brief["findings"]) == 3
