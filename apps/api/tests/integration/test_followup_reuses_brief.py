"""T055: a followup on an existing brief does not re-run research.

Runs the graph with a prior brief in state and a supervisor decision that
returns followup_on_existing_brief. The graph must terminate without invoking
the research node, so no Tavily/plan/synth LLM calls happen.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agents.graph import build_graph
from models.chat import SupervisorDecision
from models.research import Finding, IntelligenceBrief, SourceAttribution
from tests.integration._fakes import install_fake_llms

NOW = datetime.now(UTC)


def _prior_brief() -> dict:
    brief = IntelligenceBrief(
        id="brief_old",
        user_id="u1",
        conversation_id="c1",
        research_request_id="rq_old",
        scoped_question="What CRM vendors are repricing?",
        status="complete",
        findings=[
            Finding(
                id="f1",
                rank=1,
                claim="HubSpot is moving to tiered flat pricing.",
                evidence="HubSpot's pricing page shows flat tiers.",
                confidence="high",
                sources=[
                    SourceAttribution(
                        title="HubSpot pricing",
                        url="https://www.hubspot.com/pricing",  # type: ignore[arg-type]
                        source_type="official",
                        consulted_at=NOW,
                    )
                ],
            ),
            Finding(
                id="f2",
                rank=2,
                claim="Salesforce keeps per-user pricing.",
                evidence="Salesforce official page lists per-user tiers.",
                confidence="high",
                sources=[
                    SourceAttribution(
                        title="Salesforce",
                        url="https://www.salesforce.com/editions-pricing/",  # type: ignore[arg-type]
                        source_type="official",
                        consulted_at=NOW,
                    )
                ],
            ),
            Finding(
                id="f3",
                rank=3,
                claim="Zoho CRM holds per-user pricing steady.",
                evidence="Zoho public pricing page shows stable per-user tiers.",
                confidence="medium",
                sources=[
                    SourceAttribution(
                        title="Zoho",
                        url="https://www.zoho.com/crm/zohocrm-pricing.html",  # type: ignore[arg-type]
                        source_type="official",
                        consulted_at=NOW,
                    )
                ],
            ),
        ],
        generated_at=NOW,
        model_used="openai/gpt-4o",
    )
    return brief.model_dump(mode="json")


@pytest.mark.asyncio
async def test_followup_does_not_run_research(monkeypatch):
    call_log: list[str] = []

    def _boom_tavily(*_args, **_kwargs):  # pragma: no cover — must not be called
        call_log.append("tavily")
        raise AssertionError("tavily must not be called on a followup")

    monkeypatch.setattr("tools.tavily_search._raw_search", _boom_tavily)

    install_fake_llms(
        monkeypatch,
        {
            "supervisor": SupervisorDecision(
                route="followup_on_existing_brief",
                target_finding_id="f2",
                explanation="referring to the prior brief",
            ),
        },
    )

    graph = build_graph()
    state = {
        "messages": [{"role": "user", "content": "Tell me more about the second finding"}],
        "user_id": "u1",
        "conversation_id": "c_followup",
        "current_request": {"id": "rq_new", "raw_question": "Tell me more about finding 2"},
        "brief": _prior_brief(),
    }
    final = await graph.ainvoke(state, config={"configurable": {"thread_id": "c_followup"}})

    # The graph must have ended after the supervisor chose followup.
    assert (final.get("supervisor_decision") or {}).get("route") == "followup_on_existing_brief"
    # Research node did not run, so brief is unchanged (still the prior one).
    assert final["brief"]["id"] == "brief_old"
    assert call_log == []
