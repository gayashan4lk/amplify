"""Conversation list / detail / archive endpoints.

Phase 4 (T058, T059, T060) — row-level isolation is enforced at the store
layer; every call here passes `request.state.user_id`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse

from deps import get_brief_store, get_conversation_store
from services.brief_store import BriefStore
from services.conversation_store import ConversationStore

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


async def _require_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="unauthenticated")
    return user_id


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@router.get("")
async def list_conversations(
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    conversations: ConversationStore = Depends(get_conversation_store),
) -> dict:
    user_id = await _require_user(request)
    rows = await conversations.list_conversations(
        user_id=user_id, cursor=cursor, limit=limit
    )

    items = []
    for c in rows:
        conv_id = _attr(c, "id")
        messages = await conversations.list_messages(
            conversation_id=conv_id, user_id=user_id
        )
        latest_status = _derive_latest_status(messages)
        items.append(
            {
                "id": conv_id,
                "title": _attr(c, "title"),
                "created_at": _iso(_attr(c, "createdAt")),
                "updated_at": _iso(_attr(c, "updatedAt")),
                "latest_status": latest_status,
            }
        )

    next_cursor = items[-1]["id"] if len(items) == limit else None
    return {"conversations": items, "next_cursor": next_cursor}


def _derive_latest_status(messages: list[Any]) -> str:
    if not messages:
        return "pending"
    last = messages[-1]
    role = _attr(last, "role")
    role_value = getattr(role, "value", role)
    if _attr(last, "failureRecordId"):
        return "failed"
    if role_value == "assistant" and _attr(last, "briefId"):
        return "complete"
    if role_value == "assistant":
        return "complete"
    return "pending"


@router.get("/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    request: Request,
    conversations: ConversationStore = Depends(get_conversation_store),
    briefs: BriefStore = Depends(get_brief_store),
) -> dict:
    user_id = await _require_user(request)
    conv = await conversations.get_conversation(
        conversation_id=conversation_id, user_id=user_id
    )
    if conv is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "not_found",
                    "message": "Conversation not found.",
                    "recoverable": False,
                }
            },
        )

    messages_rows = await conversations.list_messages(
        conversation_id=conversation_id, user_id=user_id
    )

    messages: list[dict[str, Any]] = []
    for m in messages_rows:
        brief_id = _attr(m, "briefId")
        brief_payload: dict[str, Any] | None = None
        if brief_id:
            brief_model = await briefs.get(brief_id=brief_id, user_id=user_id)
            if brief_model is not None:
                brief_payload = brief_model.model_dump(mode="json")

        failure_payload: dict[str, Any] | None = None
        failure_id = _attr(m, "failureRecordId")
        if failure_id:
            failure_payload = await _load_failure(request, failure_id)

        role = _attr(m, "role")
        role_value = getattr(role, "value", role) or "assistant"

        messages.append(
            {
                "id": _attr(m, "id"),
                "role": role_value,
                "content": _attr(m, "content", ""),
                "created_at": _iso(_attr(m, "createdAt")),
                "progress_events": _attr(m, "progressEvents", []) or [],
                "brief": brief_payload,
                "failure": failure_payload,
            }
        )

    latest_status = _derive_latest_status(messages_rows)

    return {
        "id": conversation_id,
        "title": _attr(conv, "title"),
        "created_at": _iso(_attr(conv, "createdAt")),
        "updated_at": _iso(_attr(conv, "updatedAt")),
        "latest_status": latest_status,
        "messages": messages,
    }


async def _load_failure(request: Request, failure_id: str) -> dict[str, Any] | None:
    prisma = getattr(request.app.state, "prisma", None)
    if prisma is None:
        return None
    try:
        row = await prisma.failurerecord.find_unique(where={"id": failure_id})
    except Exception:
        return None
    if row is None:
        return None
    code = _attr(row, "code")
    return {
        "id": _attr(row, "id"),
        "code": getattr(code, "value", code),
        "user_message": _attr(row, "userMessage"),
        "suggested_action": _attr(row, "suggestedAction"),
        "recoverable": _attr(row, "recoverable"),
    }


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_conversation(
    conversation_id: str,
    request: Request,
    conversations: ConversationStore = Depends(get_conversation_store),
) -> Response:
    user_id = await _require_user(request)
    await conversations.archive_conversation(
        conversation_id=conversation_id, user_id=user_id
    )
    return Response(status_code=204)
