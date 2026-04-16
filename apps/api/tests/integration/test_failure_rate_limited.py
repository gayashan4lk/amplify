"""T082: rate limit trips after the configured hourly cap."""

from __future__ import annotations

import pytest

from config import get_settings
from services.rate_limit import RateLimited, RateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -1)


@pytest.mark.asyncio
async def test_rate_limit_trips_at_cap():
    redis = FakeRedis()
    limiter = RateLimiter(redis)
    cap = get_settings().user_research_rate_limit_per_hour

    # First `cap` calls succeed.
    for _ in range(cap):
        await limiter.check_and_incr(user_id="u1")

    # Next call must raise and carry a retry hint.
    with pytest.raises(RateLimited) as info:
        await limiter.check_and_incr(user_id="u1")
    assert info.value.retry_after_seconds >= 1
