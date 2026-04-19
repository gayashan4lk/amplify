"""Redis per-brief in-flight lock (T009).

Used by the Content Generation trigger to enforce FR-013: while a generation
run is already in flight for a brief, a second click is a no-op — the HTTP
endpoint returns 202 `already_running` and no new run is kicked off.

The lock key is `content_gen:inflight:{brief_id}` with a TTL-bounded SET NX
so a crashed worker cannot wedge the brief permanently.
"""

from __future__ import annotations

from typing import Any

_KEY_PREFIX = "content_gen:inflight:"
DEFAULT_TTL_SECONDS = 180


def _key(brief_id: str) -> str:
    return f"{_KEY_PREFIX}{brief_id}"


class InflightLock:
    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def acquire(self, brief_id: str, *, ttl: int = DEFAULT_TTL_SECONDS) -> bool:
        """Attempt to take the lock. Returns True on acquisition, False if
        a run is already in flight. TTL cleans up after worker crashes."""

        result = await self._redis.set(_key(brief_id), "1", nx=True, ex=ttl)
        return bool(result)

    async def release(self, brief_id: str) -> None:
        await self._redis.delete(_key(brief_id))

    async def is_locked(self, brief_id: str) -> bool:
        val = await self._redis.exists(_key(brief_id))
        return bool(val)
