"""T056: vague question → clarification_poll emitted → resume → brief.

Exercises the LangGraph interrupt/resume path end-to-end at the graph level.
The HTTP /chat/ephemeral endpoint is a thin shim over this — the graph is
where the real state machine lives, so testing here is the tightest loop.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from langgraph.types import Command
from pydantic import BaseModel

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

TAVILY = [
    {"title": "A", "url": "https://a.example.com/1", "content": "one"},
    {"title": "B", "url": "https://b.example.com/2", "content": "two"},
    {"title": "C", "url": "https://c.example.com/3", "content": "three"},
]


class _Options(BaseModel):
    options: list[str]


def _brief_for(user_id: str, conversation_id: str, research_request_id: str) -> IntelligenceBrief:
    srcs = [
        SourceAttribution(
            title=r["title"],
            url=r["url"],  # type: ignore[arg-type]
            source_type="news",
            consulted_at=NOW,
        )
        for r in TAVILY
    ]
    findings = [
        Finding(
            id=f"f{i}",
            rank=i,
            claim=f"Claim {i}.",
            evidence=f"Evidence {i} grounded in the fixture snippet {i}.",
            confidence="high",
            sources=[srcs[i - 1]],
        )
        for i in range(1, 4)
    ]
    return IntelligenceBrief(
        id="brief_temp",
        user_id=user_id,
        conversation_id=conversation_id,
        research_request_id=research_request_id,
        scoped_question="narrowed question",
        status="complete",
        findings=findings,
        generated_at=NOW,
        model_used="openai/gpt-4o",
    )


@pytest.mark.asyncio
async def test_clarification_emits_poll_then_resumes(monkeypatch):
    install_fake_tavily(monkeypatch, TAVILY)
    install_fake_llms(
        monkeypatch,
        {
            "supervisor": SupervisorDecision(
                route="clarification_needed",
                explanation="too vague",
            ),
            "ui_schema": _Options(
                options=[
                    "Focus on competitors",
                    "Focus on audience",
                    "Focus on pricing",
                ]
            ),
            "research_plan": ResearchPlan(
                sub_queries=[
                    SubQuery(angle="competitive", query="a"),
                    SubQuery(angle="competitive", query="b"),
                    SubQuery(angle="competitive", query="c"),
                ],
                rationale="r",
            ),
            "research_synthesize": _brief_for("u1", "c_clar", "rq_clar"),
        },
    )

    graph = build_graph()
    config = {"configurable": {"thread_id": "c_clar"}}

    # --- first pass: should interrupt at clarification ---
    initial: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Help me with my competitors"}],
        "user_id": "u1",
        "conversation_id": "c_clar",
        "current_request": {"id": "rq_clar", "raw_question": "Help me with my competitors"},
        "brief": None,
    }

    emitted_ephemeral: list[dict[str, Any]] = []
    async for ev in graph.astream_events(initial, config=config, version="v2"):
        if ev.get("event") == "on_custom_event" and ev.get("name") == "ephemeral_ui":
            emitted_ephemeral.append(ev.get("data") or {})

    assert len(emitted_ephemeral) == 1
    poll = emitted_ephemeral[0]
    assert poll["component_type"] == "clarification_poll"
    assert len(poll["component"]["options"]) == 3

    snap = await graph.aget_state(config)
    assert snap.next  # graph is paused on interrupt

    # --- resume with a selection ---
    async for _ in graph.astream_events(
        Command(resume={"selected_option_index": 1}),
        config=config,
        version="v2",
    ):
        pass

    final = (await graph.aget_state(config)).values
    assert final.get("brief") is not None
    assert final["brief"]["findings"]
    assert len(final["brief"]["findings"]) == 3
