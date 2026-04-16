"""Per-user research rate limit (T040).

Redis INCR with a 1-hour sliding window. Raises RateLimited when exceeded.
Tests inject a FakeRedis to keep CI hermetic.
"""

from __future__ import annotations

from typing import Protocol

from config import get_settings


class _RedisLike(Protocol):
    async def incr(self, key: str) -> int: ...  # pragma: no cover
    async def expire(self, key: str, seconds: int) -> bool: ...  # pragma: no cover
    async def ttl(self, key: str) -> int: ...  # pragma: no cover


class RateLimited(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"rate limited, retry in {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class RateLimiter:
    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    async def check_and_incr(self, *, user_id: str) -> None:
        s = get_settings()
        key = f"rl:research:{user_id}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 3600)
        if count > s.user_research_rate_limit_per_hour:
            ttl = await self._redis.ttl(key)
            raise RateLimited(retry_after_seconds=max(ttl, 1))
