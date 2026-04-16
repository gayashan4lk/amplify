"""In-process async bus used to deliver clarification responses from
POST /api/v1/chat/ephemeral back to the SSE handler that is still holding
the stream open waiting on a LangGraph interrupt.

One process is fine for the single-instance MVP. A later spec that runs
multiple API replicas will replace this with a Redis pub/sub channel.
"""

from __future__ import annotations

import asyncio

_queues: dict[str, asyncio.Queue[dict]] = {}


def _queue_for(key: str) -> asyncio.Queue[dict]:
    q = _queues.get(key)
    if q is None:
        q = asyncio.Queue(maxsize=1)
        _queues[key] = q
    return q


async def wait_for_resume(research_request_id: str, timeout_s: float = 300.0) -> dict:
    q = _queue_for(research_request_id)
    async with asyncio.timeout(timeout_s):
        return await q.get()


def submit_resume(research_request_id: str, payload: dict) -> bool:
    q = _queue_for(research_request_id)
    try:
        q.put_nowait(payload)
        return True
    except asyncio.QueueFull:
        return False


def clear(research_request_id: str) -> None:
    _queues.pop(research_request_id, None)
