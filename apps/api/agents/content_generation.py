"""ContentGenerationAgent (T030, T031, T061).

Orchestrates the Stage 2 content-generation flow:

1. **Suggestion step** — calls Haiku with brief findings and produces 2-4
   `PostSuggestion` objects plus a consolidated creative-direction question.
   Emits `content_suggestions` via the ephemeral-UI dispatch and advances
   the request from `suggesting` -> `awaiting_input`.
2. **Wait for user direction** — blocks on `resume_bus.wait_for_resume`
   keyed on `request_id` with a 300s timeout.
3. **Parallel variant production** — dispatches two `produce_variant`
   coroutines concurrently via `asyncio.gather`, one for label A and one
   for label B. Each call emits its own progress/ready events.
4. **Diversity gate** — if the two copy drafts are too similar the agent
   retries variant B once with a differentiation hint; if still too
   similar it sets `diversity_warning=True` on the request.
5. **Terminal completion** — updates status to `complete` (or `failed` on
   safety block / timeout), emits a final `content_variant_grid`
   ephemeral-UI event summarising both variants + regeneration caps, and
   a `done` event.

For the MVP the agent runs inline in a dedicated SSE handler (see
`routers.content`) rather than as a LangGraph node. T031 adds the
Supervisor passthrough so a content-generation intent in chat can still
route into this flow, but the primary trigger is the REST endpoint.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models.content import (
    ContentGenerationRequest,
    PostSuggestion,
    PostVariant,
    RequestStatus,
    VariantLabel,
)
from models.errors import FailureCode
from services import resume_bus
from services.content_store import ContentStore
from services.failures import record_content_failure
from services.image_store import ImageStore
from services.inflight_lock import InflightLock
from services.llm_router import get_llm
from services.tracing import get_current_trace_id
from sse.sink import emit as _emit
from tools.generate_copy import ContentSafetyBlocked
from workers.content_tasks import produce_variant
from workers.diversity import needs_retry

log = logging.getLogger(__name__)

RUN_TIMEOUT_SECONDS = 180
DIRECTION_TIMEOUT_SECONDS = 300


class _SuggestionBundle(BaseModel):
    """LLM-structured output for the suggestion step."""

    suggestions: list[PostSuggestion] = Field(..., min_length=2, max_length=4)
    question: str = Field(..., min_length=1, max_length=500)


SUGGESTION_PROMPT = """You are the Content Generation Agent's suggestion step.
Given the provided intelligence brief findings, propose 2-4 short Facebook-post \
angles the user could run with. Each suggestion must reference the ids of \
specific findings it draws on (`finding_ids`). Mark `low_confidence` true \
when the brief has <3 findings or no high-confidence finding.

After the suggestions, write ONE consolidated creative-direction question the \
user should answer — it MUST ask them to pick (or describe) the angle AND \
the audience AND the tone in a single prompt. Keep the question under 260 \
characters.

Return only the structured output. Never invent finding ids."""


async def _safe_dispatch(name: str, data: dict[str, Any]) -> None:
    await _emit(name, data)


async def _emit_ephemeral(component_type: str, component: dict[str, Any]) -> None:
    await _safe_dispatch(
        "ephemeral_ui",
        {"component_type": component_type, "component": component},
    )


async def _emit_suggestions_event(
    *,
    request_id: str,
    suggestions: list[PostSuggestion],
    question: str,
) -> None:
    await _safe_dispatch(
        "content_suggestions",
        {
            "request_id": request_id,
            "suggestions": [s.model_dump(mode="json") for s in suggestions],
            "question": question,
        },
    )
    await _emit_ephemeral(
        "content_suggestions",
        {
            "request_id": request_id,
            "suggestions": [s.model_dump(mode="json") for s in suggestions],
            "question": question,
        },
    )


async def _run_suggestion_step(
    *, brief_findings: list[dict[str, Any]]
) -> _SuggestionBundle:
    """Produce grounded suggestions + a consolidated question.

    Uses `content_copy` Haiku for determinism parity with the drafter. Any
    LLM failure bubbles so the surrounding agent maps it to a terminal
    error.
    """

    valid_ids = {f.get("id") for f in brief_findings if f.get("id")}
    llm = get_llm("content_copy").with_structured_output(
        _SuggestionBundle, method="function_calling"
    )
    findings_block = "\n".join(
        f"- id={f.get('id')} rank={f.get('rank')} confidence={f.get('confidence')} "
        f"claim={f.get('claim', '')[:200]}"
        for f in brief_findings
    )
    prompt = [
        SystemMessage(content=SUGGESTION_PROMPT),
        HumanMessage(content=f"Brief findings:\n{findings_block}"),
    ]
    bundle: _SuggestionBundle = await llm.ainvoke(prompt)  # type: ignore[assignment]

    # Strip any invented finding ids. If a suggestion ends up with no valid
    # ids after filtering, we drop it rather than lie.
    cleaned: list[PostSuggestion] = []
    for idx, s in enumerate(bundle.suggestions, start=1):
        kept_ids = [fid for fid in s.finding_ids if fid in valid_ids]
        if not kept_ids:
            continue
        cleaned.append(
            PostSuggestion(
                id=s.id or f"s-{idx}",
                text=s.text,
                finding_ids=kept_ids,
                low_confidence=s.low_confidence
                or len(brief_findings) < 3,
            )
        )
    if len(cleaned) < 2:
        raise ValueError("suggestion step produced fewer than 2 grounded suggestions")
    if len(cleaned) > 4:
        cleaned = cleaned[:4]
    return _SuggestionBundle(suggestions=cleaned, question=bundle.question)


def _remaining_caps(variants: list[PostVariant]) -> dict[str, int]:
    caps: dict[str, int] = {"A": 3, "B": 3}
    for v in variants:
        caps[v.label] = max(0, 3 - v.regenerations_used)
    return caps


async def _emit_variant_grid(
    *, request_id: str, variants: list[PostVariant], diversity_warning: bool
) -> None:
    await _emit_ephemeral(
        "content_variant_grid",
        {
            "request_id": request_id,
            "variants": [v.model_dump(mode="json") for v in variants],
            "diversity_warning": diversity_warning,
            "regeneration_caps": _remaining_caps(variants),
        },
    )


async def run_content_generation(
    *,
    request: ContentGenerationRequest,
    brief_findings: list[dict[str, Any]],
    content_store: ContentStore,
    image_store: ImageStore,
    inflight_lock: InflightLock,
    prisma: Any | None,
) -> ContentGenerationRequest:
    """Drive the full content-generation run. Safe to call from an SSE handler.

    Emits custom events that the SSE transform layer converts into the
    typed events declared in `apps/api/sse/events.py`.
    """

    request_id = request.id
    trace_id = get_current_trace_id() or f"tr_{uuid4().hex[:12]}"

    async def _fail(*, code: FailureCode, message: str, recoverable: bool) -> None:
        record = await record_content_failure(
            prisma=prisma,
            request_id=request_id,
            code=code,
            user_message=message,
            trace_id=trace_id,
            recoverable=recoverable,
        )
        await content_store.update_status(
            request_id=request_id,
            user_id=request.user_id,
            status=RequestStatus.FAILED,
            error_ref=record.id,
        )
        await _safe_dispatch(
            "content_error",
            {
                "request_id": request_id,
                "code": code.value,
                "message": message,
                "recoverable": recoverable,
                "failure_record_id": record.id,
                "trace_id": trace_id,
            },
        )

    try:
        async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
            # 1) Suggestions
            bundle = await _run_suggestion_step(brief_findings=brief_findings)
            request.suggestions = bundle.suggestions
            await content_store.update_status(
                request_id=request_id,
                user_id=request.user_id,
                status=RequestStatus.AWAITING_INPUT,
            )
            # Persist the suggestions list itself.
            await _persist_suggestions(
                content_store, request_id=request_id, user_id=request.user_id,
                suggestions=bundle.suggestions,
            )
            await _emit_suggestions_event(
                request_id=request_id,
                suggestions=bundle.suggestions,
                question=bundle.question,
            )

            # 2) Wait for user direction
            resume_key = f"content:{request_id}"
            try:
                payload = await resume_bus.wait_for_resume(
                    resume_key, timeout_s=DIRECTION_TIMEOUT_SECONDS
                )
            finally:
                resume_bus.clear(resume_key)
            user_direction = str(payload.get("user_direction", "")).strip()
            if not user_direction:
                raise ValueError("user_direction missing from resume payload")
            request.user_direction = user_direction
            await _persist_direction(
                content_store, request_id=request_id, user_id=request.user_id,
                direction=user_direction,
            )
            await content_store.update_status(
                request_id=request_id,
                user_id=request.user_id,
                status=RequestStatus.GENERATING,
            )

            # 3) Parallel variant production
            findings_for_tools = [
                {
                    "id": f.get("id", ""),
                    "claim": f.get("claim", ""),
                    "confidence": f.get("confidence", ""),
                }
                for f in brief_findings
            ]

            async def _one(label: VariantLabel) -> PostVariant | Exception:
                try:
                    return await produce_variant(
                        request_id=request_id,
                        user_id=request.user_id,
                        label=label,
                        brief_findings=findings_for_tools,
                        user_direction=user_direction,
                        content_store=content_store,
                        image_store=image_store,
                    )
                except ContentSafetyBlocked:
                    raise
                except Exception as exc:
                    return exc

            results = await asyncio.gather(
                _one("A"), _one("B"), return_exceptions=False
            )
            variants: list[PostVariant] = [r for r in results if isinstance(r, PostVariant)]
            if len(variants) < 2:
                # Partial: at least one half failed on each of A or B. Still
                # complete the request so the UI renders what it has with
                # retry-half affordances.
                pass

            # 4) Diversity gate (only when both variants came back with copy).
            diversity_warning = False
            if len(variants) == 2 and needs_retry(
                variants[0].description, variants[1].description
            ):
                log.info(
                    "diversity retry triggered for request=%s", request_id
                )
                retry = await _one("B")
                if isinstance(retry, PostVariant):
                    # Replace B.
                    variants = [v for v in variants if v.label != "B"] + [retry]
                    if needs_retry(
                        next(v for v in variants if v.label == "A").description,
                        retry.description,
                    ):
                        diversity_warning = True

            # 5) Terminal completion
            await content_store.update_status(
                request_id=request_id,
                user_id=request.user_id,
                status=RequestStatus.COMPLETE,
            )
            if diversity_warning:
                await _persist_diversity_warning(
                    content_store, request_id=request_id, user_id=request.user_id,
                )
            await _emit_variant_grid(
                request_id=request_id,
                variants=variants,
                diversity_warning=diversity_warning,
            )

            final = await content_store.get(
                request_id=request_id, user_id=request.user_id
            )
            return final or request

    except TimeoutError:
        await _fail(
            code=FailureCode.content_gen_timeout,
            message=(
                "Content generation ran past 180 seconds — we stopped and cleaned up. "
                "Try again in a moment."
            ),
            recoverable=False,
        )
        raise
    except ContentSafetyBlocked as blocker:
        await _fail(
            code=FailureCode.content_safety_blocked,
            message=(
                "The content provider declined this request on safety grounds. "
                f"Reason: {blocker.reason[:180]}"
            ),
            recoverable=True,
        )
        raise
    except Exception as exc:
        log.exception("content generation run failed: %s", exc)
        await _fail(
            code=FailureCode.content_gen_blocked,
            message=(
                "We hit an unexpected error while generating your post variants. "
                "Try again — if it keeps failing, contact support."
            ),
            recoverable=True,
        )
        raise
    finally:
        await inflight_lock.release(request.brief_id)


# --- persistence helpers ----------------------------------------------------


async def _persist_suggestions(
    store: ContentStore,
    *,
    request_id: str,
    user_id: str,
    suggestions: list[PostSuggestion],
) -> None:
    """Direct $set for the `suggestions` array — `content_store` intentionally
    does not expose a generic update, so we reach in via the underlying
    collection handle. This keeps read/write both isolated by user_id."""

    from bson import ObjectId  # type: ignore[import-untyped]

    try:
        oid = ObjectId(request_id)
    except Exception:
        return
    await store._coll.update_one(  # type: ignore[attr-defined]
        {"_id": oid, "user_id": user_id},
        {
            "$set": {
                "suggestions": [s.model_dump(mode="json") for s in suggestions],
            }
        },
    )


async def _persist_direction(
    store: ContentStore, *, request_id: str, user_id: str, direction: str
) -> None:
    from bson import ObjectId  # type: ignore[import-untyped]

    try:
        oid = ObjectId(request_id)
    except Exception:
        return
    await store._coll.update_one(  # type: ignore[attr-defined]
        {"_id": oid, "user_id": user_id},
        {"$set": {"user_direction": direction}},
    )


async def _persist_diversity_warning(
    store: ContentStore, *, request_id: str, user_id: str
) -> None:
    from bson import ObjectId  # type: ignore[import-untyped]

    try:
        oid = ObjectId(request_id)
    except Exception:
        return
    await store._coll.update_one(  # type: ignore[attr-defined]
        {"_id": oid, "user_id": user_id},
        {"$set": {"diversity_warning": True}},
    )


__all__ = ["run_content_generation"]
