"""FastAPI dependency providers.

These are module-level so tests can override them via
`app.dependency_overrides` and inject fake Prisma/Motor/Redis clients.

For Phase 3 we intentionally construct the real clients lazily the first
time each provider is hit and cache them on the FastAPI app state. A real
Prisma/Motor/Redis is only required when the server actually handles a
request — contract tests run without touching any of them.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import Request

from services.brief_store import BriefStore
from services.conversation_store import ConversationStore
from services.rate_limit import RateLimiter


async def get_prisma(request: Request) -> Any:
    app = request.app
    client = getattr(app.state, "prisma", None)
    if client is None:
        from prisma import Prisma  # type: ignore[import-not-found]

        client = Prisma(auto_register=True)
        if not client.is_connected():
            await client.connect()
        app.state.prisma = client
    return client


async def get_mongo_db(request: Request) -> Any:
    app = request.app
    db = getattr(app.state, "mongo_db", None)
    if db is None:
        from motor.motor_asyncio import AsyncIOMotorClient

        from config import get_settings

        s = get_settings()
        client = AsyncIOMotorClient(s.mongodb_uri)
        db = client[s.mongodb_db]
        app.state.mongo_client = client
        app.state.mongo_db = db
    return db


async def get_redis(request: Request) -> Any:
    app = request.app
    redis = getattr(app.state, "redis", None)
    if redis is None:
        import redis.asyncio as redis_lib  # type: ignore[import-not-found]

        redis = redis_lib.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
        app.state.redis = redis
    return redis


async def get_conversation_store(request: Request) -> ConversationStore:
    prisma = await get_prisma(request)
    return ConversationStore(prisma)


async def get_brief_store(request: Request) -> BriefStore:
    db = await get_mongo_db(request)
    store = BriefStore(db)
    return store


async def get_rate_limiter(request: Request) -> RateLimiter:
    redis = await get_redis(request)
    return RateLimiter(redis)
