"""Convert LangGraph astream_events v2 output into typed SSE events.

Also exposes `format_sse_frame` which renders a frame in the SSE wire format
with a monotonically increasing event id.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from itertools import count
from typing import Any

from sse.events import (
    AgentEnd,
    AgentStart,
    EphemeralUI,
    Progress,
    SseEvent,
)


def _now() -> datetime:
    return datetime.now(UTC)


def format_sse_frame(event_id: int, event: SseEvent) -> str:
    payload = event.model_dump_json()
    return f"id: {event_id}\nevent: {event.type}\ndata: {payload}\n\n"


class SseEventIdAllocator:
    """Monotonically-increasing event ids, scoped to one stream."""

    def __init__(self, start: int = 1) -> None:
        self._counter = count(start)

    def next(self) -> int:
        return next(self._counter)


async def transform_langgraph_events(
    conversation_id: str,
    source: AsyncIterator[dict[str, Any]],
    *,
    message_id: str = "",
) -> AsyncIterator[SseEvent]:
    """Map a subset of LangGraph astream_events v2 payloads to typed SSE events.

    Handles:
    - on_chain_start/end for supervisor/research/clarification nodes
    - on_custom_event "progress" → Progress
    - on_custom_event "ephemeral_ui" → EphemeralUI
    """

    async for raw in source:
        kind = raw.get("event")
        name = raw.get("name") or raw.get("data", {}).get("name") or ""
        if kind == "on_chain_start" and name in {"supervisor", "research", "clarification"}:
            yield AgentStart(
                conversation_id=conversation_id,
                at=_now(),
                agent=name,  # type: ignore[arg-type]
                description=f"{name} started",
            )
        elif kind == "on_chain_end" and name in {"supervisor", "research", "clarification"}:
            yield AgentEnd(
                conversation_id=conversation_id,
                at=_now(),
                agent=name,  # type: ignore[arg-type]
            )
        elif kind == "on_custom_event" and name == "progress":
            data = raw.get("data", {}) or {}
            yield Progress(
                conversation_id=conversation_id,
                at=_now(),
                phase=data.get("phase", "planning"),
                message=data.get("message", ""),
                detail=data.get("detail"),
            )
        elif kind == "on_custom_event" and name == "ephemeral_ui":
            data = raw.get("data", {}) or {}
            yield EphemeralUI(
                conversation_id=conversation_id,
                at=_now(),
                message_id=message_id,
                component_type=data.get("component_type", "intelligence_brief"),
                component=data.get("component", {}),
            )
