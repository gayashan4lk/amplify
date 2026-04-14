"""The ONLY access layer for Postgres research entities.

Every method accepts `user_id` and filters by it — no unfiltered API is
exposed. This is the enforcement point for row-level isolation
(data-model.md §Row-level isolation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prisma import Prisma


class ConversationStore:
    def __init__(self, prisma: Prisma) -> None:
        self._prisma = prisma

    # --- Conversations ----------------------------------------------------

    async def create_conversation(self, *, user_id: str, title: str) -> Any:
        return await self._prisma.conversation.create(
            data={"userId": user_id, "title": title[:140]}
        )

    async def get_conversation(self, *, conversation_id: str, user_id: str) -> Any | None:
        return await self._prisma.conversation.find_first(
            where={"id": conversation_id, "userId": user_id, "archivedAt": None}
        )

    async def list_conversations(
        self,
        *,
        user_id: str,
        cursor: str | None = None,
        limit: int = 25,
    ) -> list[Any]:
        kwargs: dict[str, Any] = {
            "where": {"userId": user_id, "archivedAt": None},
            "order": {"updatedAt": "desc"},
            "take": limit,
        }
        if cursor:
            kwargs["cursor"] = {"id": cursor}
            kwargs["skip"] = 1
        return await self._prisma.conversation.find_many(**kwargs)

    async def archive_conversation(self, *, conversation_id: str, user_id: str) -> None:
        # Filter by user_id first to enforce isolation even on write.
        owned = await self.get_conversation(conversation_id=conversation_id, user_id=user_id)
        if not owned:
            return
        from datetime import UTC, datetime

        await self._prisma.conversation.update(
            where={"id": conversation_id},
            data={"archivedAt": datetime.now(UTC)},
        )

    async def touch_conversation(self, *, conversation_id: str, user_id: str) -> None:
        owned = await self.get_conversation(conversation_id=conversation_id, user_id=user_id)
        if not owned:
            return
        from datetime import UTC, datetime

        await self._prisma.conversation.update(
            where={"id": conversation_id},
            data={"updatedAt": datetime.now(UTC)},
        )

    # --- Messages ---------------------------------------------------------

    async def list_messages(self, *, conversation_id: str, user_id: str) -> list[Any]:
        # Enforce isolation by joining through the conversation.
        if not await self.get_conversation(conversation_id=conversation_id, user_id=user_id):
            return []
        return await self._prisma.message.find_many(
            where={"conversationId": conversation_id},
            order={"createdAt": "asc"},
        )

    async def append_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        brief_id: str | None = None,
        failure_record_id: str | None = None,
    ) -> Any | None:
        if not await self.get_conversation(conversation_id=conversation_id, user_id=user_id):
            return None
        return await self._prisma.message.create(
            data={
                "conversationId": conversation_id,
                "role": role,
                "content": content,
                "briefId": brief_id,
                "failureRecordId": failure_record_id,
            }
        )

    # --- Research requests ------------------------------------------------

    async def create_research_request(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
        raw_question: str,
        scoped_question: str | None = None,
    ) -> Any | None:
        if not await self.get_conversation(conversation_id=conversation_id, user_id=user_id):
            return None
        return await self._prisma.researchrequest.create(
            data={
                "conversationId": conversation_id,
                "messageId": message_id,
                "rawQuestion": raw_question,
                "scopedQuestion": scoped_question or raw_question,
            }
        )

    async def get_research_request(self, *, request_id: str, user_id: str) -> Any | None:
        rr = await self._prisma.researchrequest.find_unique(where={"id": request_id})
        if not rr:
            return None
        conv = await self.get_conversation(conversation_id=rr.conversationId, user_id=user_id)
        return rr if conv else None
