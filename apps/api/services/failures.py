"""Failure recording helper.

`build_failure_record` constructs a Pydantic FailureRecord and enforces the
Constitution V invariant (no silent/generic failures at runtime).
`persist_failure_record` writes it to Prisma best-effort.
`record_failure` (T070) is the unified entry point the routing layer uses:
it constructs, persists, and optionally appends an assistant Message row
linking to the failure so reloading the conversation renders the failure in
place.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from models.errors import FailureCode, FailureRecord

log = logging.getLogger(__name__)

_GENERIC = {"", "something went wrong", "an error occurred", "unknown error", "error"}


def build_failure_record(
    *,
    code: FailureCode,
    user_message: str,
    suggested_action: str | None = None,
    trace_id: str | None = None,
    recoverable: bool | None = None,
) -> FailureRecord:
    if user_message.strip().lower() in _GENERIC:
        raise ValueError("user_message must be specific — no generic fallbacks")
    if recoverable is None:
        recoverable = code in {
            FailureCode.tavily_unavailable,
            FailureCode.tavily_rate_limited,
            FailureCode.llm_unavailable,
            FailureCode.rate_limited_user,
        }
    return FailureRecord(
        id=f"fr_{uuid4().hex[:12]}",
        code=code,
        recoverable=recoverable,
        user_message=user_message,
        suggested_action=suggested_action,
        trace_id=trace_id,
        created_at=datetime.now(UTC),
    )


async def persist_failure_record(
    *,
    prisma: Any | None,
    record: FailureRecord,
) -> None:
    """Best-effort Prisma persistence. No-op when prisma is None (tests)."""
    if prisma is None:
        return
    with contextlib.suppress(Exception):  # pragma: no cover — best-effort in Phase 3
        await prisma.failurerecord.create(
            data={
                "id": record.id,
                "code": record.code.value,
                "recoverable": record.recoverable,
                "userMessage": record.user_message,
                "suggestedAction": record.suggested_action,
                "traceId": record.trace_id,
            }
        )


async def record_failure(
    *,
    conversations: Any | None,
    prisma: Any | None,
    user_id: str,
    conversation_id: str,
    code: FailureCode,
    user_message: str,
    suggested_action: str | None = None,
    trace_id: str | None = None,
    recoverable: bool | None = None,
    progress_events: list[dict[str, Any]] | None = None,
) -> FailureRecord:
    """Build + persist a FailureRecord and append an assistant failure Message.

    Enforces Constitution V: `build_failure_record` rejects empty/generic
    `user_message` values. Returns the Pydantic model ready for SSE emission.
    Message append is best-effort — persistence failures never block the
    error event reaching the user.
    """

    record = build_failure_record(
        code=code,
        user_message=user_message,
        suggested_action=suggested_action,
        trace_id=trace_id,
        recoverable=recoverable,
    )
    await persist_failure_record(prisma=prisma, record=record)

    if conversations is not None and conversation_id:
        with contextlib.suppress(Exception):  # pragma: no cover — best-effort
            await conversations.append_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=record.user_message,
                failure_record_id=record.id,
                progress_events=progress_events,
            )
    return record
