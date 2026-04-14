"""T067: conversation list & detail endpoints return persisted state.

Uses dependency overrides so the router talks to in-memory fake stores —
no Prisma/Motor needed. The goal is to prove the persistence surface
(list + detail) reconstructs what the user saw live, including embedded
briefs and failure records.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from deps import get_brief_store, get_conversation_store
from main import app
from models.research import Finding, IntelligenceBrief, SourceAttribution

NOW = datetime.now(UTC)


class _Row(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError(name) from err


class FakeConversationStore:
    def __init__(self) -> None:
        self.conversations: dict[str, _Row] = {}
        self.messages: dict[str, list[_Row]] = {}

    async def list_conversations(
        self, *, user_id: str, cursor: str | None = None, limit: int = 25
    ) -> list[_Row]:
        rows = [
            c for c in self.conversations.values()
            if c["userId"] == user_id and c.get("archivedAt") is None
        ]
        rows.sort(key=lambda r: r["updatedAt"], reverse=True)
        return rows[:limit]

    async def get_conversation(self, *, conversation_id: str, user_id: str) -> _Row | None:
        row = self.conversations.get(conversation_id)
        if row and row["userId"] == user_id and row.get("archivedAt") is None:
            return row
        return None

    async def list_messages(self, *, conversation_id: str, user_id: str) -> list[_Row]:
        if not await self.get_conversation(
            conversation_id=conversation_id, user_id=user_id
        ):
            return []
        return list(self.messages.get(conversation_id, []))

    async def archive_conversation(self, *, conversation_id: str, user_id: str) -> None:
        row = await self.get_conversation(
            conversation_id=conversation_id, user_id=user_id
        )
        if row is not None:
            row["archivedAt"] = NOW


class FakeBriefStore:
    def __init__(self) -> None:
        self._by_id: dict[str, IntelligenceBrief] = {}

    def add(self, brief_id: str, brief: IntelligenceBrief) -> None:
        self._by_id[brief_id] = brief

    async def get(self, *, brief_id: str, user_id: str) -> IntelligenceBrief | None:
        brief = self._by_id.get(brief_id)
        if brief and brief.user_id == user_id:
            return brief
        return None

    async def latest_for_conversation(
        self, *, conversation_id: str, user_id: str
    ) -> IntelligenceBrief | None:
        for b in self._by_id.values():
            if b.conversation_id == conversation_id and b.user_id == user_id:
                return b
        return None


def _build_brief(user_id: str, conversation_id: str) -> IntelligenceBrief:
    return IntelligenceBrief(
        id="brief_stored",
        user_id=user_id,
        conversation_id=conversation_id,
        research_request_id="rq1",
        scoped_question="What CRM pricing looks like today?",
        status="complete",
        findings=[
            Finding(
                id="f1",
                rank=1,
                claim="HubSpot uses tiered flat pricing.",
                evidence="HubSpot's official pricing page shows tiered plans.",
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
                evidence="Salesforce official pricing is per seat.",
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
                claim="Zoho holds steady on per-user pricing.",
                evidence="Zoho CRM public pricing page shows stable tiers.",
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


@pytest.fixture
def fake_stores():
    conv = FakeConversationStore()
    briefs = FakeBriefStore()

    brief = _build_brief("u1", "c1")
    briefs.add("brief_stored", brief)

    conv.conversations["c1"] = _Row(
        id="c1",
        userId="u1",
        title="CRM pricing models",
        createdAt=NOW,
        updatedAt=NOW,
        archivedAt=None,
    )
    conv.messages["c1"] = [
        _Row(
            id="m1",
            role="user",
            content="What pricing models are top CRMs using?",
            briefId=None,
            failureRecordId=None,
            progressEvents=[],
            createdAt=NOW,
        ),
        _Row(
            id="m2",
            role="assistant",
            content="HubSpot uses tiered flat pricing.",
            briefId="brief_stored",
            failureRecordId=None,
            progressEvents=[
                {"phase": "planning", "message": "planning searches"},
                {"phase": "synthesizing", "message": "composing brief"},
            ],
            createdAt=NOW,
        ),
    ]

    app.dependency_overrides[get_conversation_store] = lambda: conv
    app.dependency_overrides[get_brief_store] = lambda: briefs
    try:
        yield conv, briefs
    finally:
        app.dependency_overrides.clear()


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_list_conversations_returns_owned_rows(fake_stores):
    client = _client()
    resp = client.get("/api/v1/conversations", headers={"X-User-Id": "u1"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["conversations"]) == 1
    row = body["conversations"][0]
    assert row["id"] == "c1"
    assert row["title"] == "CRM pricing models"
    assert row["latest_status"] == "complete"


def test_list_conversations_rejects_anonymous(fake_stores):
    client = _client()
    resp = client.get("/api/v1/conversations")
    assert resp.status_code == 401


def test_conversation_detail_embeds_brief(fake_stores):
    client = _client()
    resp = client.get("/api/v1/conversations/c1", headers={"X-User-Id": "u1"})
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == "c1"
    assert detail["latest_status"] == "complete"
    messages = detail["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assistant = messages[1]
    assert assistant["role"] == "assistant"
    assert assistant["brief"] is not None
    assert assistant["brief"]["id"] == "brief_stored"
    assert len(assistant["brief"]["findings"]) == 3
    # progress trail persisted live is rendered back on reload.
    assert len(assistant["progress_events"]) == 2


def test_conversation_detail_rejects_other_user(fake_stores):
    client = _client()
    resp = client.get("/api/v1/conversations/c1", headers={"X-User-Id": "intruder"})
    assert resp.status_code == 404


def test_archive_conversation_soft_deletes(fake_stores):
    conv, _ = fake_stores
    client = _client()
    resp = client.delete("/api/v1/conversations/c1", headers={"X-User-Id": "u1"})
    assert resp.status_code == 204
    assert conv.conversations["c1"]["archivedAt"] is not None
    # List no longer includes the archived row.
    listing = client.get("/api/v1/conversations", headers={"X-User-Id": "u1"}).json()
    assert listing["conversations"] == []
