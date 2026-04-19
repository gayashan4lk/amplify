"""The ONLY access layer for the MongoDB `intelligence_briefs` collection.

Every read/write accepts `user_id` and filters by it. Callers cannot bypass
isolation because no unfiltered API is exposed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId  # type: ignore[import-untyped]
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from models.research import IntelligenceBrief

_COLLECTION = "intelligence_briefs"


class BriefStore:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._coll: AsyncIOMotorCollection = db[_COLLECTION]

    async def ensure_indexes(self) -> None:
        await self._coll.create_index([("conversation_id", 1), ("generated_at", -1)])
        await self._coll.create_index([("user_id", 1), ("generated_at", -1)])

    async def create(self, *, brief: IntelligenceBrief) -> str:
        doc = brief.model_dump(mode="json")
        doc.pop("id", None)
        doc["generated_at"] = datetime.now(UTC)
        result = await self._coll.insert_one(doc)
        return str(result.inserted_id)

    async def get(self, *, brief_id: str, user_id: str) -> IntelligenceBrief | None:
        try:
            oid = ObjectId(brief_id)
        except Exception:
            return None
        doc = await self._coll.find_one({"_id": oid, "user_id": user_id})
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id"))
        return IntelligenceBrief.model_validate(doc)

    async def latest_for_conversation(
        self, *, conversation_id: str, user_id: str
    ) -> IntelligenceBrief | None:
        doc = await self._coll.find_one(
            {"conversation_id": conversation_id, "user_id": user_id},
            sort=[("generated_at", -1)],
        )
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id"))
        return IntelligenceBrief.model_validate(doc)

    async def list_for_user(self, *, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        cursor = self._coll.find({"user_id": user_id}).sort("generated_at", -1).limit(limit)
        return [d async for d in cursor]

    async def append_generation_request(
        self, *, brief_id: str, user_id: str, request_id: str
    ) -> None:
        """Append a content-generation request id to the brief's back-reference
        list (T035). Read-only from the brief's perspective — the briefs
        themselves remain owned by Stage 1; this is purely a rehydration
        pointer for the content-generation stage.
        """

        try:
            oid = ObjectId(brief_id)
        except Exception:
            return
        await self._coll.update_one(
            {"_id": oid, "user_id": user_id},
            {"$addToSet": {"generation_request_ids": request_id}},
        )
