"""T031: conversation_store and brief_store cannot return another user's data.

Both stores are tested against in-memory fakes that mimic the shape of the
real drivers. The point is to assert that every method filters by user_id —
if a new method is added that skips the filter, this test must start failing.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from models.research import Finding, IntelligenceBrief, SourceAttribution
from services.brief_store import BriefStore
from services.conversation_store import ConversationStore

NOW = datetime.now(UTC)


# ---------- Fake Prisma -------------------------------------------------------


class _FakeDelegate:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def create(self, data: dict) -> Any:
        row = {"id": f"id_{len(self.rows)}", "archivedAt": None, **data}
        self.rows.append(row)
        return type("Row", (), row)()

    async def find_first(self, where: dict) -> Any | None:
        for row in self.rows:
            if all(row.get(k) == v for k, v in where.items()):
                return type("Row", (), row)()
        return None

    async def find_unique(self, where: dict) -> Any | None:
        return await self.find_first(where)

    async def find_many(self, **kwargs) -> list[Any]:
        where = kwargs.get("where", {})
        matched = [r for r in self.rows if all(r.get(k) == v for k, v in where.items())]
        return [type("Row", (), r)() for r in matched]

    async def update(self, where: dict, data: dict) -> Any:
        for row in self.rows:
            if all(row.get(k) == v for k, v in where.items()):
                row.update(data)
                return type("Row", (), row)()
        return None


class _FakePrisma:
    def __init__(self) -> None:
        self.conversation = _FakeDelegate([])
        self.message = _FakeDelegate([])
        self.researchrequest = _FakeDelegate([])


@pytest.mark.asyncio
async def test_conversation_store_isolates_by_user():
    prisma = _FakePrisma()
    store = ConversationStore(prisma)  # type: ignore[arg-type]

    a = await store.create_conversation(user_id="user_a", title="A's")
    b = await store.create_conversation(user_id="user_b", title="B's")

    # User B cannot fetch user A's conversation.
    assert await store.get_conversation(conversation_id=a.id, user_id="user_b") is None
    assert await store.get_conversation(conversation_id=a.id, user_id="user_a") is not None

    # List only returns the caller's rows.
    listed = await store.list_conversations(user_id="user_a")
    assert all(r.userId == "user_a" for r in listed)
    assert any(r.id == a.id for r in listed)
    assert not any(r.id == b.id for r in listed)


# ---------- Fake Motor collection --------------------------------------------


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: list[dict] = []

    async def create_index(self, *_args, **_kwargs) -> None:
        return None

    async def insert_one(self, doc: dict):
        from bson import ObjectId  # type: ignore[import-untyped]

        oid = ObjectId()
        doc = {"_id": oid, **doc}
        self._docs.append(doc)
        return type("R", (), {"inserted_id": oid})()

    async def find_one(self, query: dict, sort: Any = None):
        matched = [d for d in self._docs if all(d.get(k) == v for k, v in query.items())]
        if sort:
            key, direction = sort[0]
            matched.sort(key=lambda d: d.get(key), reverse=direction == -1)
        return dict(matched[0]) if matched else None


class _FakeDB:
    def __init__(self) -> None:
        self._coll = _FakeCollection()

    def __getitem__(self, _name: str) -> _FakeCollection:
        return self._coll


def _brief(user_id: str) -> IntelligenceBrief:
    return IntelligenceBrief(
        id="placeholder",  # overwritten on insert
        user_id=user_id,
        conversation_id="c1",
        research_request_id="r1",
        scoped_question="q?",
        status="low_confidence",
        findings=[
            Finding(
                id="f1",
                rank=1,
                claim="Claim.",
                evidence="Evidence.",
                confidence="medium",
                sources=[
                    SourceAttribution(
                        title="T",
                        url="https://example.com/a",  # type: ignore[arg-type]
                        source_type="blog",
                        consulted_at=NOW,
                    )
                ],
            )
        ],
        generated_at=NOW,
        model_used="openai/gpt-4o",
    )


@pytest.mark.asyncio
async def test_brief_store_isolates_by_user():
    db = _FakeDB()
    store = BriefStore(db)  # type: ignore[arg-type]
    await store.ensure_indexes()

    a_id = await store.create(brief=_brief("user_a"))
    _b_id = await store.create(brief=_brief("user_b"))

    # User B asking for user A's brief by id must not be allowed.
    assert await store.get(brief_id=a_id, user_id="user_b") is None
    assert await store.get(brief_id=a_id, user_id="user_a") is not None

    # Latest-for-conversation is also user-scoped.
    assert (await store.latest_for_conversation(conversation_id="c1", user_id="user_a")) is not None
    a_view = await store.latest_for_conversation(conversation_id="c1", user_id="user_a")
    assert a_view is not None and a_view.user_id == "user_a"
