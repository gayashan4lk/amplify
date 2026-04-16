"""T068: reconnecting to an existing conversation replays stored state.

With `reconnect=true` the /chat/stream endpoint must NOT append a new
user message, must NOT rate-limit, and must re-emit the last stored
brief as an `ephemeral_ui` event so the SSE client renders the same
view the user saw before the drop.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from deps import get_brief_store, get_conversation_store, get_rate_limiter
from main import app
from models.research import Finding, IntelligenceBrief, SourceAttribution

NOW = datetime.now(UTC)


class _Row(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError(name) from err


class FakeConvStore:
    def __init__(self, rows: dict[str, _Row]) -> None:
        self._rows = rows
        self.append_calls: list[dict[str, Any]] = []

    async def get_conversation(self, *, conversation_id: str, user_id: str):
        row = self._rows.get(conversation_id)
        if row and row["userId"] == user_id and row.get("archivedAt") is None:
            return row
        return None

    async def create_conversation(self, *, user_id: str, title: str):
        raise AssertionError("reconnect must not create a conversation")

    async def append_message(self, **kwargs):  # pragma: no cover
        self.append_calls.append(kwargs)
        raise AssertionError("reconnect must not append messages")

    async def create_research_request(self, **kwargs):  # pragma: no cover
        raise AssertionError("reconnect must not create a research request")


class FakeBriefStore:
    def __init__(self, brief: IntelligenceBrief | None) -> None:
        self._brief = brief

    async def latest_for_conversation(
        self, *, conversation_id: str, user_id: str
    ) -> IntelligenceBrief | None:
        if (
            self._brief
            and self._brief.conversation_id == conversation_id
            and self._brief.user_id == user_id
        ):
            return self._brief
        return None

    async def create(self, *, brief):  # pragma: no cover
        raise AssertionError("reconnect must not write a brief")

    async def get(self, *, brief_id: str, user_id: str):  # pragma: no cover
        return None


class FakeLimiter:
    async def check_and_incr(self, *, user_id: str) -> None:  # pragma: no cover
        raise AssertionError("reconnect must not consume rate limit")


def _build_brief() -> IntelligenceBrief:
    return IntelligenceBrief(
        id="brief_inflight",
        user_id="u1",
        conversation_id="c_inflight",
        research_request_id="rq_inflight",
        scoped_question="What does the market look like?",
        status="complete",
        findings=[
            Finding(
                id=f"f{i}",
                rank=i,
                claim=f"Claim {i}",
                evidence=f"Evidence drawn from the canonical source for finding {i}.",
                confidence="high" if i == 1 else "medium",
                sources=[
                    SourceAttribution(
                        title=f"Source {i}",
                        url="https://example.com/pricing",  # type: ignore[arg-type]
                        source_type="official",
                        consulted_at=NOW,
                    )
                ],
            )
            for i in (1, 2, 3)
        ],
        generated_at=NOW,
        model_used="openai/gpt-4o",
    )


@pytest.fixture
def reconnect_deps():
    rows = {
        "c_inflight": _Row(
            id="c_inflight",
            userId="u1",
            title="in-flight",
            createdAt=NOW,
            updatedAt=NOW,
            archivedAt=None,
        )
    }
    conv = FakeConvStore(rows)
    briefs = FakeBriefStore(_build_brief())
    limiter = FakeLimiter()
    app.dependency_overrides[get_conversation_store] = lambda: conv
    app.dependency_overrides[get_brief_store] = lambda: briefs
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        yield conv
    finally:
        app.dependency_overrides.clear()


def _parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in body.split("\n\n"):
        for line in frame.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
                break
    return events


def test_reconnect_replays_stored_brief(reconnect_deps):
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/v1/chat/stream",
        headers={"X-User-Id": "u1"},
        json={
            "conversation_id": "c_inflight",
            "message": "",
            "reconnect": True,
        },
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types[0] == "conversation_ready"
    assert "ephemeral_ui" in types
    assert types[-1] == "done"
    ui = next(e for e in events if e["type"] == "ephemeral_ui")
    assert ui["component_type"] == "intelligence_brief"
    assert ui["component"]["id"] == "brief_inflight"
    assert reconnect_deps.append_calls == []


def test_reconnect_404_for_unknown_conversation(reconnect_deps):
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/v1/chat/stream",
        headers={"X-User-Id": "u1"},
        json={
            "conversation_id": "does-not-exist",
            "message": "",
            "reconnect": True,
        },
    )
    assert resp.status_code == 404
