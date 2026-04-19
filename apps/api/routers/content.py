"""Content generation REST endpoints (T032-T034, T045, T058).

The trigger flow:

    1. POST /api/v1/content/generate — validates ownership + brief
       completeness, acquires the per-brief in-flight lock, persists a new
       `ContentGenerationRequest` in `suggesting`, and returns the
       `sse_endpoint` the client should open next.
    2. GET  /api/v1/content/stream?request_id=... — server-sent-event
       stream for a single request. Drives the agent inline so SSE frames
       follow the agent's lifecycle directly.
    3. POST /api/v1/content/{request_id}/direction — delivers the user's
       creative-direction reply to the waiting SSE handler via
       `resume_bus`.

Rehydration:

    - GET /api/v1/content/{request_id}
    - GET /api/v1/briefs/{brief_id}/content-requests
    - GET /api/v1/content/image/{image_key}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agents.content_generation import _remaining_caps, run_content_generation
from deps import get_brief_store, get_mongo_db, get_redis
from models.content import (
    ContentGenerationRequest,
    RequestStatus,
)
from services import resume_bus
from services.brief_store import BriefStore
from services.content_store import ContentStore
from services.image_store import ImageStore, build_image_store
from services.inflight_lock import InflightLock
from sse.events import (
    ContentSuggestionsEvent,
    ContentVariantPartial,
    ContentVariantProgress,
    ContentVariantReady,
    Done,
    EphemeralUI,
    ErrorEvent,
    SseEvent,
)
from sse.sink import set_sink, reset_sink
from sse.transform import SseEventIdAllocator, format_sse_frame

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/content", tags=["content"])
briefs_router = APIRouter(prefix="/api/v1/briefs", tags=["content"])


async def _require_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="unauthenticated")
    return user_id


async def _get_content_store(request: Request) -> ContentStore:
    db = await get_mongo_db(request)
    return ContentStore(db)


async def _get_inflight_lock(request: Request) -> InflightLock:
    redis = await get_redis(request)
    return InflightLock(redis)


def _get_image_store(request: Request) -> ImageStore:
    app = request.app
    store = getattr(app.state, "image_store", None)
    if store is None:
        store = build_image_store()
        app.state.image_store = store
    return store


class GenerateRequestBody(BaseModel):
    brief_id: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)


class DirectionRequestBody(BaseModel):
    user_direction: str = Field(..., min_length=1, max_length=2000)


@router.post("/generate")
async def generate_content(
    request: Request,
    body: GenerateRequestBody,
    briefs: BriefStore = Depends(get_brief_store),
) -> Any:
    user_id = await _require_user(request)
    content_store = await _get_content_store(request)
    inflight = await _get_inflight_lock(request)

    brief = await briefs.get(brief_id=body.brief_id, user_id=user_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="brief_not_found")
    if not brief.findings:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "brief_incomplete",
                    "message": "Brief has no findings; cannot generate content.",
                    "recoverable": False,
                }
            },
        )

    if await inflight.is_locked(body.brief_id):
        existing = await content_store.list_by_brief(
            brief_id=body.brief_id, user_id=user_id
        )
        active = next(
            (
                r
                for r in existing
                if r.status not in {RequestStatus.COMPLETE, RequestStatus.FAILED}
            ),
            None,
        )
        return JSONResponse(
            status_code=202,
            content={
                "already_running": True,
                "request_id": active.id if active else "",
            },
        )

    acquired = await inflight.acquire(body.brief_id)
    if not acquired:
        return JSONResponse(
            status_code=202,
            content={"already_running": True, "request_id": ""},
        )

    try:
        new_req = ContentGenerationRequest(
            id="placeholder",
            brief_id=body.brief_id,
            conversation_id=body.conversation_id,
            user_id=user_id,
            status=RequestStatus.SUGGESTING,
            suggestions=[],
            variants=[],
            diversity_warning=False,
            started_at=datetime.now(UTC),
        )
        request_id = await content_store.create(request=new_req)
        await briefs.append_generation_request(
            brief_id=body.brief_id, user_id=user_id, request_id=request_id
        )
    except Exception:
        await inflight.release(body.brief_id)
        raise

    return {
        "request_id": request_id,
        "sse_endpoint": f"/api/v1/content/stream?request_id={request_id}",
    }


@router.post("/{request_id}/direction")
async def submit_direction(
    request_id: str,
    body: DirectionRequestBody,
    request: Request,
) -> Any:
    await _require_user(request)
    delivered = resume_bus.submit_resume(
        f"content:{request_id}",
        {"user_direction": body.user_direction},
    )
    if not delivered:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "not_awaiting_direction",
                    "message": (
                        "No run is waiting for creative direction on this request."
                    ),
                    "recoverable": False,
                }
            },
        )
    return {"status": "resumed"}


@router.get("/stream")
async def stream_content(
    request: Request,
    request_id: str = Query(..., min_length=1),
    briefs: BriefStore = Depends(get_brief_store),
) -> StreamingResponse:
    user_id = await _require_user(request)

    content_store = await _get_content_store(request)
    inflight = await _get_inflight_lock(request)
    image_store = _get_image_store(request)
    prisma = getattr(request.app.state, "prisma", None)

    existing = await content_store.get(request_id=request_id, user_id=user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="request_not_found")

    brief = await briefs.get(brief_id=existing.brief_id, user_id=user_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="brief_not_found")
    brief_findings = [f.model_dump(mode="json") for f in brief.findings]

    async def sse_gen():
        alloc = SseEventIdAllocator()

        def _emit(event: SseEvent) -> str:
            return format_sse_frame(alloc.next(), event)

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def sink(name: str, data: dict[str, Any]) -> None:
            await queue.put({"name": name, "data": data})

        message_id = f"msg_{request_id}"

        async def _runner() -> None:
            token = set_sink(sink)
            try:
                await run_content_generation(
                    request=existing,
                    brief_findings=brief_findings,
                    content_store=content_store,
                    image_store=image_store,
                    inflight_lock=inflight,
                    prisma=prisma,
                )
            finally:
                reset_sink(token)
                await queue.put(None)

        task = asyncio.create_task(_runner())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                name = item["name"]
                data = item["data"]
                now = datetime.now(UTC)
                try:
                    if name == "content_suggestions":
                        yield _emit(
                            ContentSuggestionsEvent(
                                conversation_id=existing.conversation_id,
                                at=now,
                                message_id=message_id,
                                request_id=data.get("request_id", request_id),
                                suggestions=data.get("suggestions", []),
                                question=data.get("question", ""),
                            )
                        )
                    elif name == "ephemeral_ui":
                        component_type = data.get("component_type")
                        # The variants grid must not share the suggestions'
                        # message id — otherwise chat-store's id-based dedupe
                        # treats the grid as a duplicate of the suggestions
                        # card and the variants never render.
                        ephemeral_message_id = (
                            f"msg_variants_{request_id}"
                            if component_type == "content_variant_grid"
                            else message_id
                        )
                        yield _emit(
                            EphemeralUI(
                                conversation_id=existing.conversation_id,
                                at=now,
                                message_id=ephemeral_message_id,
                                component_type=component_type,  # type: ignore[arg-type]
                                component=data.get("component", {}),
                            )
                        )
                    elif name == "content_variant_progress":
                        yield _emit(
                            ContentVariantProgress(
                                conversation_id=existing.conversation_id,
                                at=now,
                                request_id=data.get("request_id", request_id),
                                variant_label=data.get("variant_label", "A"),
                                step=data.get("step", ""),
                                progress_hint=data.get("progress_hint"),
                            )
                        )
                    elif name == "content_variant_ready":
                        yield _emit(
                            ContentVariantReady(
                                conversation_id=existing.conversation_id,
                                at=now,
                                request_id=data.get("request_id", request_id),
                                variant=data.get("variant"),  # type: ignore[arg-type]
                            )
                        )
                    elif name == "content_variant_partial":
                        yield _emit(
                            ContentVariantPartial(
                                conversation_id=existing.conversation_id,
                                at=now,
                                request_id=data.get("request_id", request_id),
                                variant_label=data.get("variant_label", "A"),
                                description_status=data.get(
                                    "description_status", "pending"
                                ),
                                image_status=data.get("image_status", "pending"),
                                description=data.get("description"),
                                image_signed_url=data.get("image_signed_url"),
                                retry_target=data.get("retry_target", "image"),
                            )
                        )
                    elif name == "content_error":
                        yield _emit(
                            ErrorEvent(
                                conversation_id=existing.conversation_id,
                                at=now,
                                code=data.get("code"),  # type: ignore[arg-type]
                                message=data.get("message", "Content generation failed."),
                                recoverable=data.get("recoverable", False),
                                failure_record_id=data.get("failure_record_id", ""),
                                trace_id=data.get("trace_id"),
                            )
                        )
                except Exception:
                    log.exception(
                        "failed to emit sse frame name=%s payload=%r", name, data
                    )

            with contextlib.suppress(Exception):
                await task

            yield _emit(
                Done(
                    conversation_id=existing.conversation_id,
                    at=datetime.now(UTC),
                    final_status="brief_ready",
                    summary="content generation complete",
                )
            )
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        sse_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{request_id}")
async def get_request(
    request_id: str,
    request: Request,
) -> Any:
    user_id = await _require_user(request)
    content_store = await _get_content_store(request)
    existing = await content_store.get(request_id=request_id, user_id=user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="request_not_found")
    return existing.model_dump(mode="json")


@router.get("/image/{image_key:path}")
async def refresh_image_url(
    image_key: str,
    request: Request,
) -> Any:
    await _require_user(request)
    image_store = _get_image_store(request)
    try:
        signed_url = image_store.sign(image_key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="image_not_found") from exc
    return {"signed_url": signed_url}


@briefs_router.get("/{brief_id}/content-requests")
async def list_requests_for_brief(
    brief_id: str,
    request: Request,
) -> Any:
    user_id = await _require_user(request)
    content_store = await _get_content_store(request)
    items = await content_store.list_by_brief(brief_id=brief_id, user_id=user_id)
    return {
        "requests": [i.model_dump(mode="json") for i in items],
        "regeneration_caps_by_request": {
            i.id: _remaining_caps(i.variants) for i in items
        },
    }


import contextlib  # noqa: E402
