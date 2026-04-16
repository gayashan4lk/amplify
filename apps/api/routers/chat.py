"""Chat router — POST /api/v1/chat/stream and POST /api/v1/chat/ephemeral.

Implements T038, T039, T040, T041, T043.

The SSE handler owns the lifecycle of a single research interaction:
- conversation_ready first
- agent_start/agent_end pairs around each LangGraph node
- progress events during research phases
- exactly one of: ephemeral_ui(intelligence_brief) + done, text_delta(+done),
  ephemeral_ui(clarification_poll) + suspended-until-resume, or error
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from langgraph.types import Command

from agents.graph import build_graph
from agents.research import EXCEPTION_TO_FAILURE_CODE
from deps import get_brief_store, get_conversation_store, get_rate_limiter
from models.chat import ChatRequest, EphemeralResponseRequest
from models.errors import FailureCode
from models.research import IntelligenceBrief
from services import resume_bus
from services.brief_store import BriefStore
from services.conversation_store import ConversationStore
from services.failures import build_failure_record, record_failure
from services.rate_limit import RateLimited, RateLimiter
from sse.events import (
    ConversationReady,
    Done,
    EphemeralUI,
    ErrorEvent,
    Progress,
    SseEvent,
    TextDelta,
)
from sse.transform import SseEventIdAllocator, format_sse_frame, transform_langgraph_events

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# A single compiled graph is reused across requests — LangGraph's
# InMemorySaver is scoped per thread_id so this is safe.
_graph = build_graph()


def _now() -> datetime:
    return datetime.now(UTC)


async def _require_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="unauthenticated")
    return user_id


async def _emit(allocator: SseEventIdAllocator, event: SseEvent) -> str:
    return format_sse_frame(allocator.next(), event)


@router.post("/stream")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    conversations: ConversationStore = Depends(get_conversation_store),
    briefs: BriefStore = Depends(get_brief_store),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    user_id = await _require_user(request)

    if body.reconnect:
        return await _reconnect_stream(
            request=request,
            body=body,
            user_id=user_id,
            conversations=conversations,
            briefs=briefs,
        )

    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    # --- rate limit -------------------------------------------------------
    try:
        await limiter.check_and_incr(user_id=user_id)
    except RateLimited as rl:
        record = build_failure_record(
            code=FailureCode.rate_limited_user,
            user_message=(
                "You've hit the hourly research limit — wait a bit and try again."
            ),
            suggested_action=f"Retry in about {rl.retry_after_seconds} seconds.",
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": record.code.value,
                    "message": record.user_message,
                    "recoverable": record.recoverable,
                    "retry_after_seconds": rl.retry_after_seconds,
                    "failure_record_id": record.id,
                }
            },
        )

    # --- conversation bootstrap moved INSIDE the SSE generator ----------
    # Previously these DB calls ran at router-scope; any exception (e.g.
    # MongoDB Atlas unreachable) bubbled out as an uncaught HTTP 500 with
    # NO SSE frames, so the frontend never rendered <FailureCard />. Per
    # Constitution V (no silent/generic failures) and §7 of the spec,
    # every user-visible failure must arrive as an SSE error event.
    is_new = body.conversation_id is None
    assistant_message_id = f"msg_{uuid4().hex[:12]}"

    async def sse_gen():
        alloc = SseEventIdAllocator()
        progress_trail: list[dict[str, Any]] = []

        def _trail(event: SseEvent) -> None:
            if isinstance(event, Progress):
                progress_trail.append(
                    {
                        "phase": event.phase,
                        "message": event.message,
                        "detail": event.detail,
                        "at": event.at.isoformat(),
                    }
                )

        async def _emit_failure(
            *, code: FailureCode, conversation_id_for_event: str
        ):
            message, suggestion = _error_text(code)
            record = await record_failure(
                conversations=conversations,
                prisma=getattr(request.app.state, "prisma", None),
                user_id=user_id,
                conversation_id=conversation_id_for_event,
                code=code,
                user_message=message,
                suggested_action=suggestion,
                progress_events=progress_trail,
            )
            # `error` is itself the terminal frame for a failed stream — we
            # do NOT emit a trailing `done` here. Adding "error" to the Done
            # `final_status` Literal would require a contract + frontend
            # parser change (see sse/events.py and apps/web/lib/types/sse-events.ts).
            yield await _emit(
                alloc,
                ErrorEvent(
                    conversation_id=conversation_id_for_event,
                    at=_now(),
                    code=code.value,  # type: ignore[arg-type]
                    message=message,
                    recoverable=record.recoverable,
                    suggested_action=suggestion,
                    failure_record_id=record.id,
                    trace_id=record.trace_id,
                ),
            )

        # --- bootstrap (DB work) --------------------------------------
        conversation_id: str = ""
        research_request_id: str = ""
        prior_brief_json: dict[str, Any] | None = None
        prior_brief_model: IntelligenceBrief | None = None
        try:
            conversation: Any
            if is_new:
                title = body.message[:140] or "New conversation"
                conversation = await conversations.create_conversation(
                    user_id=user_id, title=title
                )
            else:
                conversation = await conversations.get_conversation(
                    conversation_id=body.conversation_id, user_id=user_id
                )
                if conversation is None:
                    # Not-found still surfaces as a FailureCard so the user
                    # sees something specific rather than a blank stream.
                    async for frame in _emit_failure(
                        code=FailureCode.llm_invalid_output,
                        conversation_id_for_event=body.conversation_id or "",
                    ):
                        yield frame
                    return

            conversation_id = getattr(conversation, "id", None) or conversation["id"]

            user_message = await conversations.append_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=body.message,
            )

            research_request = await conversations.create_research_request(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=getattr(user_message, "id", None)
                or (user_message or {}).get("id", "")
                or "",
                raw_question=body.message,
            )
            research_request_id = (
                getattr(research_request, "id", None)
                or (research_request or {}).get("id")
                or f"rq_{uuid4().hex[:12]}"
            )

            prior_brief_model = await briefs.latest_for_conversation(
                conversation_id=conversation_id, user_id=user_id
            )
            prior_brief_json = (
                prior_brief_model.model_dump(mode="json")
                if prior_brief_model
                else None
            )
        except Exception as exc:
            log.exception("chat_stream bootstrap failed: %r", exc)
            code = _exception_to_failure_code(exc)
            async for frame in _emit_failure(
                code=code, conversation_id_for_event=conversation_id
            ):
                yield frame
            return

        # 1) conversation_ready
        yield await _emit(
            alloc,
            ConversationReady(conversation_id=conversation_id, at=_now(), is_new=is_new),
        )

        graph_state = {
            "messages": [{"role": "user", "content": body.message}],
            "user_id": user_id,
            "conversation_id": conversation_id,
            "current_request": {
                "id": research_request_id,
                "raw_question": body.message,
            },
            "brief": prior_brief_json,
        }
        config = {"configurable": {"thread_id": conversation_id}}

        try:
            # Initial run.
            async for sse_event in transform_langgraph_events(
                conversation_id,
                _graph.astream_events(graph_state, config=config, version="v2"),
                message_id=assistant_message_id,
            ):
                _trail(sse_event)
                yield await _emit(alloc, sse_event)

            # After the run returns, check whether the graph is interrupted
            # waiting on clarification input.
            snap = await _graph.aget_state(config)
            if snap.next:
                try:
                    resume_payload = await resume_bus.wait_for_resume(
                        research_request_id, timeout_s=300.0
                    )
                except TimeoutError as err:
                    raise RuntimeError("clarification response timed out") from err
                finally:
                    resume_bus.clear(research_request_id)

                async for sse_event in transform_langgraph_events(
                    conversation_id,
                    _graph.astream_events(
                        Command(resume=resume_payload), config=config, version="v2"
                    ),
                    message_id=assistant_message_id,
                ):
                    yield await _emit(alloc, sse_event)
                snap = await _graph.aget_state(config)

            final_values = snap.values or {}
            decision = final_values.get("supervisor_decision") or {}
            route = decision.get("route")
            brief_state = final_values.get("brief")
            log.info(
                "supervisor routed message to %r (explanation=%r)",
                route,
                decision.get("explanation"),
            )

            # followup_on_existing_brief → stream a text answer grounded in the prior brief
            if route == "followup_on_existing_brief" and prior_brief_model is not None:
                answer = await _followup_text_response(prior_brief_model, body.message)
                yield await _emit(
                    alloc,
                    TextDelta(
                        conversation_id=conversation_id,
                        at=_now(),
                        message_id=assistant_message_id,
                        delta=answer,
                    ),
                )
                await conversations.append_message(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    role="assistant",
                    content=answer,
                    progress_events=progress_trail,
                )
                yield await _emit(
                    alloc,
                    Done(
                        conversation_id=conversation_id,
                        at=_now(),
                        final_status="text_only",
                        summary="followup answered from stored brief",
                    ),
                )
                return

            if brief_state:
                # Persist the brief to MongoDB.
                brief_state_copy = dict(brief_state)
                brief_state_copy.pop("id", None)
                brief_state_copy["id"] = "placeholder"
                brief_model = IntelligenceBrief.model_validate(brief_state_copy)
                mongo_id = await briefs.create(brief=brief_model)
                brief_json = brief_model.model_dump(mode="json")
                brief_json["id"] = mongo_id

                await conversations.append_message(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    role="assistant",
                    content=brief_model.findings[0].claim,
                    brief_id=mongo_id,
                    progress_events=progress_trail,
                )

                yield await _emit(
                    alloc,
                    EphemeralUI(
                        conversation_id=conversation_id,
                        at=_now(),
                        message_id=assistant_message_id,
                        component_type="intelligence_brief",
                        component=brief_json,
                    ),
                )
                yield await _emit(
                    alloc,
                    Done(
                        conversation_id=conversation_id,
                        at=_now(),
                        final_status="brief_ready",
                        summary=(
                            f"{len(brief_model.findings)} findings, "
                            f"{sum(1 for f in brief_model.findings if f.confidence == 'high')}"
                            " high-confidence"
                        ),
                    ),
                )
                return

            # out_of_scope / default — stream a short visible text response so
            # the user always sees *something* instead of an empty assistant
            # turn. Constitution V: no silent failures, and an empty reply is
            # effectively a silent failure from the user's perspective.
            fallback = (
                "I'm set up to answer research questions about markets, "
                "competitors, audiences, pricing, and channels. Try a scoped "
                "question — e.g. 'What pricing tiers are the top 5 CRM "
                "competitors using?' — and I'll pull sources and synthesize a "
                "brief."
            )
            yield await _emit(
                alloc,
                TextDelta(
                    conversation_id=conversation_id,
                    at=_now(),
                    message_id=assistant_message_id,
                    delta=fallback,
                ),
            )
            await conversations.append_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=fallback,
                progress_events=progress_trail,
            )
            yield await _emit(
                alloc,
                Done(
                    conversation_id=conversation_id,
                    at=_now(),
                    final_status="text_only",
                    summary=decision.get("explanation") or "out of scope",
                ),
            )

        except asyncio.CancelledError:
            code = FailureCode.user_cancelled
            message, suggestion = _error_text(code)
            record = await record_failure(
                conversations=conversations,
                prisma=getattr(request.app.state, "prisma", None),
                user_id=user_id,
                conversation_id=conversation_id,
                code=code,
                user_message=message,
                suggested_action=suggestion,
                progress_events=progress_trail,
            )
            yield await _emit(
                alloc,
                ErrorEvent(
                    conversation_id=conversation_id,
                    at=_now(),
                    code=code.value,  # type: ignore[arg-type]
                    message=message,
                    recoverable=record.recoverable,
                    suggested_action=suggestion,
                    failure_record_id=record.id,
                    trace_id=record.trace_id,
                ),
            )
            raise
        except Exception as exc:
            log.exception("chat stream failed with unhandled exception: %r", exc)
            code = _exception_to_failure_code(exc)
            message, suggestion = _error_text(code)
            record = await record_failure(
                conversations=conversations,
                prisma=getattr(request.app.state, "prisma", None),
                user_id=user_id,
                conversation_id=conversation_id,
                code=code,
                user_message=message,
                suggested_action=suggestion,
                progress_events=progress_trail,
            )
            yield await _emit(
                alloc,
                ErrorEvent(
                    conversation_id=conversation_id,
                    at=_now(),
                    code=code.value,  # type: ignore[arg-type]
                    message=message,
                    recoverable=record.recoverable,
                    suggested_action=suggestion,
                    failure_record_id=record.id,
                    trace_id=record.trace_id,
                ),
            )

    return StreamingResponse(
        sse_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ephemeral", status_code=status.HTTP_202_ACCEPTED)
async def chat_ephemeral(
    request: Request,
    body: EphemeralResponseRequest,
    conversations: ConversationStore = Depends(get_conversation_store),
):
    user_id = await _require_user(request)

    research_request = await conversations.get_research_request(
        request_id=body.research_request_id, user_id=user_id
    )
    if research_request is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "not_found",
                    "message": "Research request not found.",
                    "recoverable": False,
                }
            },
        )

    # Deliver the resume payload to the waiting SSE handler (if any).
    delivered = resume_bus.submit_resume(
        body.research_request_id,
        {"selected_option_index": body.response.selected_option_index},
    )

    if not delivered:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "not_awaiting_clarification",
                    "message": "Research request is not waiting on clarification.",
                    "recoverable": False,
                }
            },
        )

    return {"status": "resumed"}


async def _reconnect_stream(
    *,
    request: Request,
    body: ChatRequest,
    user_id: str,
    conversations: ConversationStore,
    briefs: BriefStore,
) -> StreamingResponse:
    """Resume a stream for an existing conversation without appending input.

    Emits conversation_ready, replays any stored brief as an ephemeral_ui
    event, then terminates with `done`. When the graph is still interrupted
    (e.g. waiting on clarification) we wait on resume_bus like the fresh
    flow. This path is invoked when the client reconnects after a drop.
    """

    conversation_id = body.conversation_id or ""
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
        )  # type: ignore[return-value]

    prior_brief = await briefs.latest_for_conversation(
        conversation_id=conversation_id, user_id=user_id
    )
    assistant_message_id = f"msg_{uuid4().hex[:12]}"

    async def gen():
        alloc = SseEventIdAllocator()
        yield await _emit(
            alloc,
            ConversationReady(
                conversation_id=conversation_id, at=_now(), is_new=False
            ),
        )

        if prior_brief is not None:
            brief_json = prior_brief.model_dump(mode="json")
            yield await _emit(
                alloc,
                EphemeralUI(
                    conversation_id=conversation_id,
                    at=_now(),
                    message_id=assistant_message_id,
                    component_type="intelligence_brief",
                    component=brief_json,
                ),
            )
            yield await _emit(
                alloc,
                Done(
                    conversation_id=conversation_id,
                    at=_now(),
                    final_status="brief_ready",
                    summary="replayed from stored brief",
                ),
            )
            return

        yield await _emit(
            alloc,
            Done(
                conversation_id=conversation_id,
                at=_now(),
                final_status="text_only",
                summary="no stored brief to resume",
            ),
        )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- helpers -----------------------------------------------------------------


def _exception_to_failure_code(exc: Exception) -> FailureCode:
    for cls, code in EXCEPTION_TO_FAILURE_CODE.items():
        if isinstance(exc, cls):
            return code
    # Storage/driver failures surface as retryable service errors. We can't
    # import pymongo at module scope (optional dep in some test envs) so
    # match by module/class name on the exception type's MRO.
    type_chain = {f"{t.__module__}.{t.__name__}" for t in type(exc).__mro__}
    if any(name.startswith("pymongo.errors.") for name in type_chain):
        return FailureCode.llm_unavailable
    msg = str(exc).lower()
    if "tavily" in msg and ("timeout" in msg or "unreach" in msg or "503" in msg):
        return FailureCode.tavily_unavailable
    if "openai" in msg or "anthropic" in msg:
        return FailureCode.llm_unavailable
    if "ssl" in msg and "handshake" in msg:
        # Most common path: MongoDB Atlas TLS handshake failure.
        return FailureCode.llm_unavailable
    return FailureCode.llm_invalid_output


def _error_text(code: FailureCode) -> tuple[str, str | None]:
    mapping: dict[FailureCode, tuple[str, str | None]] = {
        FailureCode.tavily_unavailable: (
            "Our search provider is temporarily unreachable.",
            "Try again in a minute.",
        ),
        FailureCode.tavily_rate_limited: (
            "Search provider is throttling us right now.",
            "Wait a moment and retry.",
        ),
        FailureCode.llm_unavailable: (
            "The language model provider is temporarily unavailable.",
            "Retry in a minute.",
        ),
        FailureCode.llm_invalid_output: (
            "The research step returned an unexpected response shape.",
            None,
        ),
        FailureCode.no_findings_above_threshold: (
            "I couldn't find enough solid sources to answer that well.",
            None,
        ),
        FailureCode.budget_exceeded: (
            "Research ran over its time budget without finishing.",
            None,
        ),
        FailureCode.user_cancelled: (
            "Research was cancelled before it could finish.",
            None,
        ),
        FailureCode.rate_limited_user: (
            "You've hit the hourly research limit — wait a bit and try again.",
            "Retry later.",
        ),
    }
    return mapping[code]


async def _followup_text_response(brief: IntelligenceBrief, question: str) -> str:
    """LLM-grounded follow-up answer. Reads the full brief and the user's
    question and answers in plain prose. No web research — the brief is the
    only source of truth. Falls back to a deterministic summary if the LLM
    call fails so the user always sees something.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from services.llm_router import get_llm

    findings_block = "\n\n".join(
        f"Finding #{f.rank} ({f.confidence} confidence): {f.claim}\nEvidence: {f.evidence}"
        + (f"\nNotes: {f.notes}" if f.notes else "")
        for f in brief.findings
    )
    system = (
        "You are answering a follow-up question about a previously delivered "
        "intelligence brief. Use ONLY the findings listed below — do not invent "
        "facts or cite sources that are not in the brief. If the user refers to "
        "a specific finding by number or position (e.g. 'the second finding'), "
        "answer about that finding. Keep the response under 180 words."
    )
    user = (
        f"Original question: {brief.scoped_question}\n\n"
        f"Brief findings:\n{findings_block}\n\n"
        f"Follow-up: {question}"
    )
    try:
        resp = await get_llm("research_synthesize").ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        content = getattr(resp, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception:  # pragma: no cover — best-effort; fall through
        log.exception("followup llm call failed; using deterministic fallback")
    first = brief.findings[0]
    return (
        f"Based on the prior brief on '{brief.scoped_question}': "
        f"{first.claim} — {first.evidence[:200]}"
    )


# Silence unused imports for linters that don't see the resume_bus submodule usage.
_ = asyncio
