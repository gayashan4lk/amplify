"""§7 Failure paths: when the pre-stream bootstrap (conversation create / brief
lookup) raises — e.g. MongoDB Atlas unreachable (SSL handshake timeout) — the
client MUST still receive an SSE `error` frame followed by `done`, not a raw
HTTP 500. The frontend renders <FailureCard /> off the SSE error; a 500 gets
no card at all, which violates Constitution V (no silent failures).

Previously `briefs.latest_for_conversation(...)` ran at router scope, outside
the SSE generator's try/except, so any storage failure bubbled up as HTTP 500.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from deps import get_brief_store, get_conversation_store, get_rate_limiter
from main import app

NOW = datetime.now(UTC)


class _Row(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError(name) from err


class _FakePymongoServerSelectionTimeoutError(Exception):
    """Stand-in for pymongo.errors.ServerSelectionTimeoutError that matches
    the class-based module-path check in `_exception_to_failure_code` without
    requiring pymongo as a hard test dep."""

    pass


_FakePymongoServerSelectionTimeoutError.__module__ = "pymongo.errors"


class ConvStoreOK:
    """Minimal ConversationStore stub — conversation create/append succeed so
    the bootstrap only fails at the brief-store step."""

    def __init__(self) -> None:
        self.appended: list[dict[str, Any]] = []

    async def create_conversation(self, *, user_id: str, title: str):
        return _Row(
            id="c_new",
            userId=user_id,
            title=title,
            createdAt=NOW,
            updatedAt=NOW,
            archivedAt=None,
        )

    async def get_conversation(self, *, conversation_id: str, user_id: str):
        return None

    async def append_message(self, **kwargs):
        # Called by record_failure when persisting the failure message.
        self.appended.append(kwargs)
        return _Row(id=f"m_{len(self.appended)}")

    async def create_research_request(self, **kwargs):
        return _Row(id="rq_new")


class BriefStoreDown:
    """Raises a pymongo-shaped SSL handshake error, simulating the exact
    Atlas outage the user hit during §7 testing."""

    def __init__(self) -> None:
        self.latest_calls = 0

    async def latest_for_conversation(self, *, conversation_id: str, user_id: str):
        self.latest_calls += 1
        raise _FakePymongoServerSelectionTimeoutError(
            "SSL handshake failed: tlsv1 alert internal error"
        )

    async def create(self, *, brief):  # pragma: no cover
        raise AssertionError("create should not run when bootstrap fails")


class LimiterOK:
    async def check_and_incr(self, *, user_id: str) -> None:
        return None


@pytest.fixture
def bootstrap_failure_deps():
    conv = ConvStoreOK()
    briefs = BriefStoreDown()
    limiter = LimiterOK()
    app.dependency_overrides[get_conversation_store] = lambda: conv
    app.dependency_overrides[get_brief_store] = lambda: briefs
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        yield conv, briefs
    finally:
        app.dependency_overrides.clear()


def _parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in body.split("\n\n"):
        for line in frame.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
                break
    return events


def test_mongo_down_emits_sse_error_not_http_500(bootstrap_failure_deps):
    conv, briefs = bootstrap_failure_deps
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/v1/chat/stream",
        headers={"X-User-Id": "u1"},
        json={"message": "What is Notion's pricing for teams?"},
    )
    # Streaming endpoint always returns 200; failures ride on SSE.
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    # No conversation_ready: bootstrap failed before that step. `error` is
    # the terminal frame for a failed stream (no trailing `done`).
    assert "error" in types, f"expected error event, got {types}"
    assert types[-1] == "error"
    error = next(e for e in events if e["type"] == "error")
    # Storage failures map to llm_unavailable (recoverable, has retry suggestion).
    assert error["code"] == "llm_unavailable"
    assert error["recoverable"] is True
    assert error["suggested_action"]
    assert error["failure_record_id"]
    # FailureRecord append_message must have been called so reloading the
    # conversation shows the FailureCard in place.
    assert any(call.get("failure_record_id") for call in conv.appended)
    # Brief store was actually consulted (not short-circuited).
    assert briefs.latest_calls == 1
