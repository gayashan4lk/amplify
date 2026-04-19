"""Nano Banana 2 image-generation tool (T028, T060).

Routes through `llm_router.get_image_model("content_image")` so the provider
choice (Google Gemini Nano Banana 2) is centralised per Constitution §Stack.
The tool:

1. Invokes the image model with a prompt derived from the brief findings +
   user direction + variant spin.
2. Normalises the returned PNG/JPEG to 1080x1080. If the provider returns a
   non-square image, we letterbox onto a white canvas rather than failing
   the whole variant (research R-007, FR-007).
3. Persists the bytes via `image_store.put` and returns `(image_key,
   signed_url)`.

Provider safety blocks surface as `ContentSafetyBlocked`.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from dataclasses import dataclass

from services.image_store import ImageStore
from services.llm_router import get_image_model

from .generate_copy import ContentSafetyBlocked  # re-use typed error

log = logging.getLogger(__name__)

TARGET_SIZE = (1080, 1080)


@dataclass(slots=True)
class ImageResult:
    image_key: str
    signed_url: str
    content_type: str
    latency_ms: int
    letterboxed: bool


IMAGE_PROMPT = (
    "Photographic social-media image for a Facebook feed post. 1:1 square "
    "composition, 1080x1080. Clean lighting, no text overlays, no logos, "
    "no watermarks. Subject should visually reinforce this concept:\n\n"
    "{direction}\n\n"
    "Grounding context from the brief (use for subject/tone, do not render "
    "as text):\n{findings}"
)


def _normalize_to_square(data: bytes, content_type: str) -> tuple[bytes, str, bool]:
    """Ensure the output is exactly 1080x1080. Letterbox on mismatch.

    Returns `(bytes, content_type, letterboxed)`. When Pillow is unavailable
    or the image is unreadable, the original bytes are returned as-is and
    `letterboxed=False` — the downstream frontend keeps rendering, and the
    mismatch shows up in structured logs instead of failing the variant
    (FR-007 letterbox fallback).
    """

    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover — Pillow optional in Phase 3
        log.warning("Pillow not installed; skipping image normalization")
        return data, content_type, False

    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # pragma: no cover — provider returned garbage
        log.exception("image decode failed; passing through raw bytes")
        return data, content_type, False

    if im.size == TARGET_SIZE:
        return data, content_type, False

    # Letterbox onto a white square the size of the longest side.
    longest = max(im.size)
    canvas = Image.new("RGB", (longest, longest), (255, 255, 255))
    offset = ((longest - im.size[0]) // 2, (longest - im.size[1]) // 2)
    canvas.paste(im.convert("RGB"), offset)
    canvas = canvas.resize(TARGET_SIZE, Image.LANCZOS)
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue(), "image/png", True


def _extract_image_bytes(response: object) -> tuple[bytes, str]:
    """Pull (bytes, content_type) out of a google-genai response.

    Gemini SDK returns `response.candidates[0].content.parts[*].inline_data`
    with `data` (bytes or base64) and `mime_type`. We look for the first
    image-* part.
    """

    import base64

    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline is None:
                continue
            mime = getattr(inline, "mime_type", "image/png") or "image/png"
            raw = getattr(inline, "data", None)
            if raw is None:
                continue
            if isinstance(raw, str):
                raw = base64.b64decode(raw)
            return bytes(raw), mime
    # Fallback: whole-response `.image` attr on mocked clients.
    img = getattr(response, "image", None)
    if isinstance(img, bytes | bytearray):
        return bytes(img), "image/png"
    raise ValueError("image response contained no image data")


async def generate_image(
    *,
    brief_findings: list[dict[str, str]],
    user_direction: str,
    variant_label: str,
    image_store: ImageStore,
    request_id: str,
    additional_guidance: str | None = None,
) -> ImageResult:
    t0 = time.monotonic()
    client, model, _ = get_image_model("content_image")
    findings_block = "\n".join(
        f"- {f.get('claim', '')}" for f in brief_findings[:5]
    )
    prompt = IMAGE_PROMPT.format(
        direction=user_direction, findings=findings_block or "(none)"
    )
    if additional_guidance:
        prompt = f"{prompt}\n\nAdditional guidance: {additional_guidance}"

    try:
        # google-genai is sync; run in a thread to avoid blocking the loop.
        def _call() -> object:
            return client.models.generate_content(
                model=model,
                contents=prompt,
            )

        response = await asyncio.to_thread(_call)
    except Exception as exc:  # pragma: no cover — provider-specific detection
        msg = str(exc).lower()
        if "safety" in msg or "blocked" in msg or "refus" in msg:
            raise ContentSafetyBlocked(str(exc)) from exc
        log.exception("generate_image provider call failed")
        raise

    # Safety categories may ride on the response itself.
    prompt_feedback = getattr(response, "prompt_feedback", None)
    if prompt_feedback is not None:
        block_reason = getattr(prompt_feedback, "block_reason", None)
        if block_reason:
            raise ContentSafetyBlocked(str(block_reason))

    data, content_type = _extract_image_bytes(response)
    data, content_type, letterboxed = _normalize_to_square(data, content_type)

    ext = "png" if "png" in content_type else "jpg"
    filename = f"variant-{variant_label}-{request_id}.{ext}"
    key, signed_url = await image_store.put(
        data, content_type, filename=filename
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "generate_image ok",
        extra={
            "step": "generate_image",
            "request_id": request_id,
            "variant_label": variant_label,
            "bytes": len(data),
            "letterboxed": letterboxed,
            "latency_ms": latency_ms,
            "model": "nano-banana-2",
        },
    )
    return ImageResult(
        image_key=key,
        signed_url=signed_url,
        content_type=content_type,
        latency_ms=latency_ms,
        letterboxed=letterboxed,
    )


__all__ = ["ImageResult", "generate_image"]
