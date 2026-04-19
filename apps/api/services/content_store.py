"""Motor CRUD for the `content_generation_requests` MongoDB collection (T011).

Every read/write is scoped by `user_id` so callers cannot bypass tenant
isolation. The store owns index creation for the collection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId  # type: ignore[import-untyped]
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from models.content import (
    ContentGenerationRequest,
    PostVariant,
    RequestStatus,
)

_COLLECTION = "content_generation_requests"


def _oid(request_id: str) -> ObjectId | None:
    try:
        return ObjectId(request_id)
    except Exception:
        return None


def _hydrate(doc: dict[str, Any]) -> ContentGenerationRequest:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return ContentGenerationRequest.model_validate(doc)


class ContentStore:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._coll: AsyncIOMotorCollection = db[_COLLECTION]

    async def ensure_indexes(self) -> None:
        await self._coll.create_index([("brief_id", 1), ("started_at", -1)])
        await self._coll.create_index([("conversation_id", 1), ("started_at", -1)])
        await self._coll.create_index([("user_id", 1), ("status", 1)])

    async def create(self, *, request: ContentGenerationRequest) -> str:
        doc = request.model_dump(mode="json")
        doc.pop("id", None)
        result = await self._coll.insert_one(doc)
        return str(result.inserted_id)

    async def get(
        self, *, request_id: str, user_id: str
    ) -> ContentGenerationRequest | None:
        oid = _oid(request_id)
        if oid is None:
            return None
        doc = await self._coll.find_one({"_id": oid, "user_id": user_id})
        return _hydrate(doc) if doc else None

    async def list_by_brief(
        self, *, brief_id: str, user_id: str
    ) -> list[ContentGenerationRequest]:
        cursor = self._coll.find({"brief_id": brief_id, "user_id": user_id}).sort(
            "started_at", -1
        )
        return [_hydrate(d) async for d in cursor]

    async def list_by_conversation(
        self, *, conversation_id: str, user_id: str
    ) -> list[ContentGenerationRequest]:
        cursor = self._coll.find(
            {"conversation_id": conversation_id, "user_id": user_id}
        ).sort("started_at", -1)
        return [_hydrate(d) async for d in cursor]

    async def update_status(
        self,
        *,
        request_id: str,
        user_id: str,
        status: RequestStatus,
        error_ref: str | None = None,
    ) -> None:
        oid = _oid(request_id)
        if oid is None:
            return
        update: dict[str, Any] = {"status": status.value}
        terminal = {RequestStatus.COMPLETE, RequestStatus.FAILED}
        if status in terminal:
            update["completed_at"] = datetime.now(UTC).isoformat()
        if error_ref is not None:
            update["error_ref"] = error_ref
        await self._coll.update_one(
            {"_id": oid, "user_id": user_id}, {"$set": update}
        )

    async def upsert_variant(
        self,
        *,
        request_id: str,
        user_id: str,
        variant: PostVariant,
    ) -> None:
        """Insert or replace the variant with the matching label."""

        oid = _oid(request_id)
        if oid is None:
            return
        payload = variant.model_dump(mode="json")
        # Pull existing variant with the same label, then push the new one.
        await self._coll.update_one(
            {"_id": oid, "user_id": user_id},
            {"$pull": {"variants": {"label": variant.label}}},
        )
        await self._coll.update_one(
            {"_id": oid, "user_id": user_id},
            {"$push": {"variants": payload}},
        )

    async def increment_regenerations_used(
        self, *, request_id: str, user_id: str, label: str
    ) -> int | None:
        """Atomically bump the per-variant counter, respecting the cap of 3.

        Returns the new counter value, or None when the cap is already hit or
        the request/variant does not exist.
        """

        oid = _oid(request_id)
        if oid is None:
            return None
        doc = await self._coll.find_one_and_update(
            {
                "_id": oid,
                "user_id": user_id,
                "variants": {
                    "$elemMatch": {"label": label, "regenerations_used": {"$lt": 3}}
                },
            },
            {"$inc": {"variants.$.regenerations_used": 1}},
            return_document=True,
        )
        if not doc:
            return None
        for v in doc.get("variants", []):
            if v.get("label") == label:
                return int(v.get("regenerations_used", 0))
        return None
