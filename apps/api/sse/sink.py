"""Contextvar-based SSE event sink used by the content generation flow.

The SSE handler in `routers.content` sets a sink via `set_sink(...)` before
calling the agent. The agent and its inner tools/workers call `emit(name,
data)` to push typed-event payloads into the sink, which the handler then
turns into SSE frames.

This is strictly simpler than LangChain's `adispatch_custom_event` for
flows that don't run inside a LangGraph `astream_events` pipeline.
"""

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable
from typing import Any

Sink = Callable[[str, dict[str, Any]], Awaitable[None]]

_sink: contextvars.ContextVar[Sink | None] = contextvars.ContextVar(
    "content_event_sink", default=None
)


def set_sink(sink: Sink | None) -> contextvars.Token[Sink | None]:
    return _sink.set(sink)


def reset_sink(token: contextvars.Token[Sink | None]) -> None:
    _sink.reset(token)


async def emit(name: str, data: dict[str, Any]) -> None:
    sink = _sink.get()
    if sink is None:
        return
    await sink(name, data)


__all__ = ["Sink", "emit", "set_sink", "reset_sink"]
