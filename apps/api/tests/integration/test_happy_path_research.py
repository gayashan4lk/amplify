"""T053: full graph end-to-end, fixture-driven, no live APIs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agents.graph import build_graph
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
        "title": "HubSpot pricing — official page",
        "url": "https://www.hubspot.com/pricing",
        "content": "Starter $20/mo, Professional $890/mo.",
    },
    {
        "title": "Salesforce pricing — official page",
        "url": "https://www.salesforce.com/editions-pricing/",
        "content": "Essentials $25/user/mo, Enterprise $165/user/mo.",
    },
    {
        "title": "Zoho CRM pricing breakdown",
        "url": "https://www.zoho.com/crm/zohocrm-pricing.html",
        "content": "Standard $14/user/mo up to Ultimate $52/user/mo.",
    },
    {
        "title": "TechCrunch — CRM pricing is diverging",
        "url": "https://techcrunch.com/2025/03/15/crm-pricing-split",
        "content": "Seat-based vs usage-based models are widening.",
    },
]


def _fixture_brief(user_id: str, conversation_id: str, research_request_id: str) -> IntelligenceBrief:
    def src(title, url, source_type):
        return SourceAttribution(
            title=title, url=url, source_type=source_type, consulted_at=NOW  # type: ignore[arg-type]
        )

    findings = [
        Finding(
            id="f1",
            rank=1,
            claim="HubSpot uses tiered flat pricing with Starter at $20/mo.",
            evidence="HubSpot's public pricing page lists Starter at $20/mo and Professional at $890/mo.",
            confidence="high",
            sources=[
                src(
                    "HubSpot pricing",
                    "https://www.hubspot.com/pricing",
                    "official",
                )
            ],
        ),
        Finding(
            id="f2",
            rank=2,
            claim="Salesforce and Zoho remain per-user subscription.",
            evidence="Both vendors publish per-user-per-month pricing on their official pages.",
            confidence="high",
            sources=[
                src(
                    "Salesforce pricing",
                    "https://www.salesforce.com/editions-pricing/",
                    "official",
                ),
                src(
                    "Zoho CRM pricing",
                    "https://www.zoho.com/crm/zohocrm-pricing.html",
                    "official",
                ),
            ],
        ),
        Finding(
            id="f3",
            rank=3,
            claim="Coverage of pricing divergence suggests a shift toward usage models.",
            evidence="TechCrunch reports seat-based vs usage-based CRM pricing is widening.",
            confidence="medium",
            sources=[
                src(
                    "TechCrunch CRM pricing",
                    "https://techcrunch.com/2025/03/15/crm-pricing-split",
                    "news",
                )
            ],
        ),
    ]
    return IntelligenceBrief(
        id="brief_temp",
        user_id=user_id,
        conversation_id=conversation_id,
        research_request_id=research_request_id,
        scoped_question="What pricing models are top CRM competitors using?",
        status="complete",
        findings=findings,
        generated_at=NOW,
        model_used="openai/gpt-4o",
    )


@pytest.mark.asyncio
async def test_happy_path_full_graph(monkeypatch):
    install_fake_tavily(monkeypatch, TAVILY_FIXTURE)
    install_fake_llms(
        monkeypatch,
        {
            "supervisor": SupervisorDecision(
                route="research",
                scoped_question="What pricing models are top CRM competitors using?",
                explanation="clear research question",
            ),
            "research_plan": ResearchPlan(
                sub_queries=[
                    SubQuery(angle="competitive", query="HubSpot pricing model"),
                    SubQuery(angle="competitive", query="Salesforce pricing model"),
                    SubQuery(angle="competitive", query="Zoho CRM pricing"),
                ],
                rationale="cover top 3 CRM vendors",
            ),
            "research_synthesize": _fixture_brief("u1", "c1", "rq1"),
        },
    )

    graph = build_graph()
    state = {
        "messages": [
            {"role": "user", "content": "What pricing models are top 5 CRM competitors using?"}
        ],
        "user_id": "u1",
        "conversation_id": "c1",
        "current_request": {
            "id": "rq1",
            "raw_question": "What pricing models are top 5 CRM competitors using?",
        },
        "brief": None,
    }
    final = await graph.ainvoke(state, config={"configurable": {"thread_id": "c1"}})

    brief = final["brief"]
    assert brief is not None
    assert brief["status"] == "complete"
    assert len(brief["findings"]) >= 3
    assert any(f["confidence"] == "high" for f in brief["findings"])

    # Every cited source URL must appear in the Tavily fixture.
    fixture_urls = {r["url"] for r in TAVILY_FIXTURE}
    for f in brief["findings"]:
        for s in f["sources"]:
            assert str(s["url"]).rstrip("/") in {u.rstrip("/") for u in fixture_urls}
