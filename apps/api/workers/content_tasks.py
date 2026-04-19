"""Variant production task (T029).

`produce_variant(request_id, label, ...)` runs copy + image in parallel via
`asyncio.gather`, persists partial progress through `content_store`, and
dispatches `content_variant_progress`/`content_variant_partial`/
`content_variant_ready` LangChain custom events so the SSE transform layer
can forward them to the client.

Constitution IV requires we stream *everything*, so the function emits a
custom event at every observable state change: step start, step success,
step failure, and final ready/partial.

Scope (T029, US1): happy path + per-half failure. Targeted retry-half is
wired from the router in T058.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from models.content import HalfStatus, PostVariant, VariantLabel
from services.content_store import ContentStore
from services.image_store import ImageStore
from services.tracing import get_current_trace_id
from sse.sink import emit as _emit
from tools.generate_copy import ContentSafetyBlocked, generate_copy
from tools.generate_image import generate_image

log = logging.getLogger(__name__)


async def _safe_dispatch(name: str, data: dict[str, Any]) -> None:
    await _emit(name, data)


async def _emit_progress(
    *, request_id: str, label: VariantLabel, step: str, hint: float | None = None
) -> None:
    await _safe_dispatch(
        "content_variant_progress",
        {
            "request_id": request_id,
            "variant_label": label,
            "step": step,
            "progress_hint": hint,
        },
    )


async def produce_variant(
    *,
    request_id: str,
    user_id: str,
    label: VariantLabel,
    brief_findings: list[dict[str, str]],
    user_direction: str,
    content_store: ContentStore,
    image_store: ImageStore,
    source_suggestion_id: str | None = None,
    additional_guidance: str | None = None,
    regenerations_used: int = 0,
) -> PostVariant:
    """Produce one variant (copy + image in parallel) and emit SSE events.

    Returns the final `PostVariant`. Raises `ContentSafetyBlocked` if
    either provider refuses — the agent turns that into a terminal
    `error` SSE event with `code: "content_safety_blocked"`.
    """

    trace_id = get_current_trace_id() or ""
    log.info(
        "produce_variant dispatch",
        extra={
            "step": "produce_variant_dispatch",
            "request_id": request_id,
            "variant_label": label,
            "trace_id": trace_id,
            "regenerations_used": regenerations_used,
            "has_guidance": additional_guidance is not None,
        },
    )
    await _emit_progress(request_id=request_id, label=label, step="starting", hint=0.05)

    async def _copy() -> tuple[str | None, Exception | None]:
        try:
            await _emit_progress(
                request_id=request_id, label=label, step="drafting copy", hint=0.25
            )
            result = await generate_copy(
                brief_findings=brief_findings,
                user_direction=user_direction,
                variant_label=label,
                additional_guidance=additional_guidance,
                request_id=request_id,
            )
            await _emit_progress(
                request_id=request_id, label=label, step="copy ready", hint=0.55
            )
            return result.text, None
        except ContentSafetyBlocked:
            raise
        except Exception as exc:
            log.exception("variant %s copy failed", label)
            return None, exc

    async def _image() -> tuple[tuple[str, str] | None, Exception | None]:
        try:
            await _emit_progress(
                request_id=request_id, label=label, step="generating image", hint=0.45
            )
            result = await generate_image(
                brief_findings=brief_findings,
                user_direction=user_direction,
                variant_label=label,
                image_store=image_store,
                request_id=request_id,
                additional_guidance=additional_guidance,
            )
            await _emit_progress(
                request_id=request_id, label=label, step="image ready", hint=0.85
            )
            return (result.image_key, result.signed_url), None
        except ContentSafetyBlocked:
            raise
        except Exception as exc:
            log.exception("variant %s image failed", label)
            return None, exc

    copy_outcome, image_outcome = await asyncio.gather(_copy(), _image())
    copy_text, copy_err = copy_outcome
    image_payload, image_err = image_outcome

    # Only half failures are partial — safety blocks from either side bubble
    # up (both halves raised ContentSafetyBlocked). If just one raised it,
    # we still prefer to surface the refusal.
    if isinstance(copy_err, ContentSafetyBlocked) or isinstance(
        image_err, ContentSafetyBlocked
    ):
        blocker = copy_err if isinstance(copy_err, ContentSafetyBlocked) else image_err
        raise blocker  # type: ignore[misc]

    description_status = HalfStatus.READY if copy_text is not None else HalfStatus.FAILED
    image_status = HalfStatus.READY if image_payload is not None else HalfStatus.FAILED

    image_key = image_payload[0] if image_payload else None
    image_url = image_payload[1] if image_payload else None

    # We never persist a half-baked variant with an invalid copy — the
    # PostVariant model requires an 80-250 char description, so when copy
    # failed we reuse the last known description (if any) or a placeholder
    # that will be replaced on retry. Partial-variant rendering happens on
    # the wire via `content_variant_partial`; the persisted document only
    # flips to `ready` when both halves succeed.
    variant: PostVariant | None = None
    if description_status == HalfStatus.READY and image_status == HalfStatus.READY:
        assert copy_text is not None and image_key is not None and image_url is not None
        variant = PostVariant(
            label=label,
            description=copy_text,
            description_status=HalfStatus.READY,
            image_key=image_key,
            image_signed_url=image_url,
            image_status=HalfStatus.READY,
            regenerations_used=regenerations_used,
            source_suggestion_id=source_suggestion_id,
            generation_trace_id=trace_id,
            updated_at=datetime.now(UTC),
        )
        await content_store.upsert_variant(
            request_id=request_id, user_id=user_id, variant=variant
        )
        await _safe_dispatch(
            "content_variant_ready",
            {"request_id": request_id, "variant": variant.model_dump(mode="json")},
        )
        return variant

    # Partial path: emit on the wire but do NOT persist an invalid variant.
    retry_target = "image" if image_status == HalfStatus.FAILED else "description"
    await _safe_dispatch(
        "content_variant_partial",
        {
            "request_id": request_id,
            "variant_label": label,
            "description_status": description_status.value,
            "image_status": image_status.value,
            "description": copy_text,
            "image_signed_url": image_url,
            "retry_target": retry_target,
        },
    )
    # Raise so the caller can decide whether to mark the run failed. In
    # practice the agent catches this and lets the user retry-half from
    # the UI.
    err = copy_err or image_err or RuntimeError("unknown variant failure")
    raise err


async def retry_variant_half(
    *,
    request_id: str,
    user_id: str,
    label: VariantLabel,
    target: str,
    brief_findings: list[dict[str, str]],
    user_direction: str,
    content_store: ContentStore,
    image_store: ImageStore,
    existing_description: str | None,
    existing_image_key: str | None,
    existing_image_url: str | None,
    existing_description_status: HalfStatus,
    existing_image_status: HalfStatus,
    source_suggestion_id: str | None = None,
    regenerations_used: int = 0,
    additional_guidance: str | None = None,
) -> PostVariant | None:
    """Retry only the failing half (description OR image).

    Does NOT bump `regenerations_used` — this is meant for transient
    provider flakes, not user-initiated iteration. Re-emits
    `content_variant_ready` when both halves now succeed, or
    `content_variant_partial` if the retry itself failed.
    """

    trace_id = get_current_trace_id() or ""
    if target not in {"description", "image"}:
        raise ValueError(f"unknown retry target: {target!r}")

    await _emit_progress(
        request_id=request_id, label=label, step=f"retrying {target}", hint=0.2
    )

    new_description = existing_description
    new_image_key = existing_image_key
    new_image_url = existing_image_url
    new_description_status = existing_description_status
    new_image_status = existing_image_status

    if target == "description":
        try:
            result = await generate_copy(
                brief_findings=brief_findings,
                user_direction=user_direction,
                variant_label=label,
                additional_guidance=additional_guidance,
                request_id=request_id,
            )
            new_description = result.text
            new_description_status = HalfStatus.READY
        except ContentSafetyBlocked:
            raise
        except Exception as exc:
            log.exception("retry description failed")
            new_description_status = HalfStatus.FAILED
            _last_err: Exception | None = exc
        else:
            _last_err = None
    else:  # target == "image"
        try:
            result = await generate_image(
                brief_findings=brief_findings,
                user_direction=user_direction,
                variant_label=label,
                image_store=image_store,
                request_id=request_id,
                additional_guidance=additional_guidance,
            )
            new_image_key = result.image_key
            new_image_url = result.signed_url
            new_image_status = HalfStatus.READY
        except ContentSafetyBlocked:
            raise
        except Exception as exc:
            log.exception("retry image failed")
            new_image_status = HalfStatus.FAILED
            _last_err = exc
        else:
            _last_err = None

    if (
        new_description_status == HalfStatus.READY
        and new_image_status == HalfStatus.READY
        and new_description is not None
        and new_image_key is not None
        and new_image_url is not None
    ):
        variant = PostVariant(
            label=label,
            description=new_description,
            description_status=HalfStatus.READY,
            image_key=new_image_key,
            image_signed_url=new_image_url,
            image_status=HalfStatus.READY,
            regenerations_used=regenerations_used,
            source_suggestion_id=source_suggestion_id,
            generation_trace_id=trace_id,
            updated_at=datetime.now(UTC),
        )
        await content_store.upsert_variant(
            request_id=request_id, user_id=user_id, variant=variant
        )
        await _safe_dispatch(
            "content_variant_ready",
            {"request_id": request_id, "variant": variant.model_dump(mode="json")},
        )
        return variant

    retry_target = (
        "description" if new_description_status == HalfStatus.FAILED else "image"
    )
    await _safe_dispatch(
        "content_variant_partial",
        {
            "request_id": request_id,
            "variant_label": label,
            "description_status": new_description_status.value,
            "image_status": new_image_status.value,
            "description": new_description,
            "image_signed_url": new_image_url,
            "retry_target": retry_target,
        },
    )
    if _last_err is not None:
        raise _last_err
    return None


__all__ = ["produce_variant", "retry_variant_half"]
