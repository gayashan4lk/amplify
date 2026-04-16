"""T078: Tavily unreachable → explicit, recoverable, persisted failure.

We exercise `_exception_to_failure_code` + `record_failure` end-to-end so the
same mapping chat.py uses is covered. Using a fake `ConversationStore` keeps
the test hermetic — no Prisma/Motor required.
"""

from __future__ import annotations

from typing import Any

import pytest

from models.errors import FailureCode
from routers.chat import _error_text, _exception_to_failure_code
from services.failures import record_failure
from tools.tavily_search import TavilyUnavailable


class _RecordingStore:
    def __init__(self) -> None:
        self.appended: list[dict[str, Any]] = []

    async def append_message(self, **kwargs: Any) -> None:
        self.appended.append(kwargs)


@pytest.mark.asyncio
async def test_tavily_unavailable_maps_and_persists():
    exc = RuntimeError("tavily 503 service unreachable")
    code = _exception_to_failure_code(exc)
    assert code is FailureCode.tavily_unavailable

    message, suggestion = _error_text(code)
    assert message.strip() != ""
    assert suggestion is not None

    store = _RecordingStore()
    record = await record_failure(
        conversations=store,
        prisma=None,
        user_id="u1",
        conversation_id="c1",
        code=code,
        user_message=message,
        suggested_action=suggestion,
    )

    assert record.code is FailureCode.tavily_unavailable
    assert record.recoverable is True
    assert record.suggested_action == suggestion
    assert record.user_message == message

    assert len(store.appended) == 1
    appended = store.appended[0]
    assert appended["role"] == "assistant"
    assert appended["failure_record_id"] == record.id
    assert appended["conversation_id"] == "c1"


def test_missing_tavily_api_key_classifies_as_tavily_unavailable():
    """Removing TAVILY_API_KEY must raise TavilyUnavailable which maps to the
    specific failure code — NOT llm_invalid_output (the generic fallback)."""
    exc = TavilyUnavailable("TAVILY_API_KEY is not configured")
    assert _exception_to_failure_code(exc) is FailureCode.tavily_unavailable


def test_pymongo_storage_failure_classifies_as_llm_unavailable():
    """Atlas SSL / server-selection errors are retryable service errors, not
    generic invalid-output errors. We match by module path so pymongo stays
    an optional import."""

    class _FakePymongoErr(Exception):
        pass

    _FakePymongoErr.__module__ = "pymongo.errors"
    exc = _FakePymongoErr("SSL handshake failed")
    assert _exception_to_failure_code(exc) is FailureCode.llm_unavailable


def test_ssl_handshake_string_matches_llm_unavailable():
    """Fallback string-match path for generic exceptions carrying Atlas SSL
    messaging (defensive — class-based match above is the primary path)."""
    exc = RuntimeError("SSL handshake failed: tlsv1 alert internal error")
    assert _exception_to_failure_code(exc) is FailureCode.llm_unavailable
