"""Minimal failure recording helper used by Phase 3 error paths.

Phase 5 (T070) extends this with full Prisma persistence. For Phase 3 we only
need the in-memory construction of a FailureRecord Pydantic model so the SSE
error event can reference it. Callers pass a Prisma client when available.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from models.errors import FailureCode, FailureRecord

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
