"""T028: every Pydantic SSE event round-trips, carries v=1, and has the
documented fields per contracts/sse-events.md."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from sse.events import (
    AgentEnd,
    AgentStart,
    ConversationReady,
    Done,
    EphemeralUI,
    ErrorEvent,
    Progress,
    TextDelta,
    ToolCall,
    ToolResult,
)

NOW = datetime.now(UTC)
CID = "conv_test"


def _roundtrip(event):
    js = event.model_dump_json()
    cls = type(event)
    parsed = cls.model_validate_json(js)
    assert parsed.model_dump() == event.model_dump()
    assert parsed.v == 1


def test_conversation_ready():
    _roundtrip(ConversationReady(conversation_id=CID, at=NOW, is_new=True))


def test_agent_start_end_balanced():
    _roundtrip(AgentStart(conversation_id=CID, at=NOW, agent="research", description="go"))
    _roundtrip(AgentEnd(conversation_id=CID, at=NOW, agent="research"))


def test_tool_call_and_result():
    _roundtrip(ToolCall(conversation_id=CID, at=NOW, tool="tavily_search", input={"query": "x"}))
    _roundtrip(
        ToolResult(
            conversation_id=CID,
            at=NOW,
            tool="tavily_search",
            result_count=7,
            duration_ms=842,
        )
    )


def test_progress():
    _roundtrip(
        Progress(
            conversation_id=CID,
            at=NOW,
            phase="planning",
            message="Planning sub-queries",
            detail={"n": 4},
        )
    )


def test_text_delta():
    _roundtrip(TextDelta(conversation_id=CID, at=NOW, message_id="m1", delta="hi"))


def test_ephemeral_ui_clarification_poll():
    ev = EphemeralUI(
        conversation_id=CID,
        at=NOW,
        message_id="m1",
        component_type="clarification_poll",
        component={
            "research_request_id": "rq_1",
            "prompt": "Which direction?",
            "options": ["a", "b", "c"],
        },
    )
    _roundtrip(ev)


def test_error_event_requires_message():
    _roundtrip(
        ErrorEvent(
            conversation_id=CID,
            at=NOW,
            code="tavily_unavailable",
            message="Our search provider is temporarily unreachable.",
            recoverable=True,
            suggested_action="Try again in a minute.",
            failure_record_id="fr_1",
        )
    )

    with pytest.raises(ValidationError):
        ErrorEvent(
            conversation_id=CID,
            at=NOW,
            code="tavily_unavailable",
            message="",  # empty message rejected
            recoverable=True,
            suggested_action="Try again.",
            failure_record_id="fr_1",
        )


def test_done():
    _roundtrip(
        Done(
            conversation_id=CID,
            at=NOW,
            final_status="brief_ready",
            summary="3 findings",
        )
    )


def test_v_must_be_one():
    with pytest.raises(ValidationError):
        ConversationReady.model_validate(
            {
                "v": 2,
                "type": "conversation_ready",
                "conversation_id": CID,
                "at": NOW.isoformat(),
                "is_new": True,
            }
        )
