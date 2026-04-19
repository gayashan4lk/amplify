"""Haiku copy-generation tool (T027, T060).

Wraps `get_llm("content_copy")` with a prompt that enforces Facebook-post
constraints: 80-250 chars (FR-006) and at least one emoji from the
conservative-render safelist declared in `models.content.ALLOWED_EMOJI`.

The tool never trusts the provider — the returned copy is validated and
repaired server-side:

1. Provider returns text.
2. Strip surrounding whitespace/quotes.
3. If a disallowed emoji sneaks in, it is stripped; if no allowed emoji is
   present, a deterministic safelist emoji is appended.
4. If length is < 80, a short on-brand suffix is appended; if > 250, it is
   truncated on a word boundary with a terminal emoji preserved.
5. Final result is re-validated via `validate_description_emoji` and the
   PostVariant length bounds.

Provider safety refusals (`stop_reason == "refusal"` for Anthropic) are
surfaced as `ContentSafetyBlocked` so the agent can emit an `error` SSE
event with `code: "content_safety_blocked"` (FR-014).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from models.content import ALLOWED_EMOJI, validate_description_emoji
from services.llm_router import get_llm

log = logging.getLogger(__name__)

MIN_LEN = 80
MAX_LEN = 250
_FALLBACK_EMOJI = "✨"

SYSTEM_PROMPT = """You write short, grounded Facebook post descriptions for \
small-business founders. Rules — follow them exactly:

- Length: between 80 and 250 characters. Never exceed 250.
- Must contain at least one emoji from this safelist (and NO others): \
{allowed}
- Plain prose. No hashtags, no @mentions, no URLs.
- Never invent a statistic or citation that is not in the provided brief \
findings.
- Keep it on-brand: confident, warm, concrete.

The user message gives you brief findings and a creative direction. Produce \
ONE description. Return ONLY the description text — no preamble, no quotes."""


class ContentSafetyBlocked(Exception):
    """Provider refused on safety grounds (FR-014)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(slots=True)
class CopyResult:
    text: str
    latency_ms: int
    repaired: bool


def _strip_disallowed_emoji(text: str) -> str:
    """Remove emoji-looking codepoints that are not in ALLOWED_EMOJI."""

    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        combined = ch
        if i + 1 < len(text) and text[i + 1] == "\ufe0f":
            combined = ch + "\ufe0f"
        if combined in ALLOWED_EMOJI or ch in ALLOWED_EMOJI:
            out.append(combined)
            i += len(combined)
            continue
        cp = ord(ch)
        is_emoji = (
            (0x1F300 <= cp <= 0x1FAFF)
            or (0x2600 <= cp <= 0x27BF)
            or (0x1F000 <= cp <= 0x1F2FF)
        )
        if is_emoji:
            # skip
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _has_allowed_emoji(text: str) -> bool:
    try:
        validate_description_emoji(text)
    except ValueError:
        return False
    return True


def repair_copy(text: str) -> tuple[str, bool]:
    """Best-effort repair of a provider response into a compliant description.

    Returns `(repaired_text, was_repaired)`. Exposed for unit testing
    (T023).
    """

    original = text
    repaired = text.strip().strip('"').strip("'").strip()
    repaired = _strip_disallowed_emoji(repaired)
    # Collapse runs of whitespace.
    repaired = re.sub(r"\s+", " ", repaired).strip()

    if not _has_allowed_emoji(repaired):
        repaired = f"{repaired} {_FALLBACK_EMOJI}".strip()

    if len(repaired) > MAX_LEN:
        # Truncate on a word boundary, reserving room for a trailing emoji.
        budget = MAX_LEN - 2
        cut = repaired[:budget]
        # Don't cut mid-word if we can avoid it.
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        repaired = f"{cut.rstrip()} {_FALLBACK_EMOJI}"

    if len(repaired) < MIN_LEN:
        pad = " — share what you think." * 4
        repaired = (repaired + pad)[:MAX_LEN].rstrip()
        if not _has_allowed_emoji(repaired):
            repaired = f"{repaired} {_FALLBACK_EMOJI}"

    return repaired, repaired != original


def _detect_refusal(resp: object) -> str | None:
    """Best-effort extraction of an Anthropic refusal reason."""

    stop_reason = getattr(resp, "response_metadata", {}).get("stop_reason")  # type: ignore[assignment]
    if stop_reason == "refusal":
        content = getattr(resp, "content", "")
        return str(content) or "provider refused on safety grounds"
    return None


async def generate_copy(
    *,
    brief_findings: list[dict[str, str]],
    user_direction: str,
    variant_label: str,
    additional_guidance: str | None = None,
) -> CopyResult:
    """Produce a single Facebook-post description via Haiku.

    `brief_findings` is the trimmed list of findings from the source brief
    (already grounded — the agent filters before calling).
    """

    t0 = time.monotonic()
    llm = get_llm("content_copy")

    findings_block = "\n".join(
        f"- ({f.get('id', '?')}, {f.get('confidence', '?')}) {f.get('claim', '')}"
        for f in brief_findings
    )
    variant_spin = {
        "A": "Lead with the single most surprising finding — make the reader stop scrolling.",
        "B": "Lead with a customer-outcome angle — concrete and results-oriented.",
    }.get(variant_label, "Keep it concrete and on-brand.")
    guidance_block = (
        f"\nAdditional guidance: {additional_guidance}" if additional_guidance else ""
    )

    messages = [
        SystemMessage(
            content=SYSTEM_PROMPT.format(allowed=" ".join(sorted(ALLOWED_EMOJI)))
        ),
        HumanMessage(
            content=(
                f"Creative direction: {user_direction}\n\n"
                f"Variant {variant_label} spin: {variant_spin}\n\n"
                f"Brief findings (use only these as facts):\n{findings_block}"
                f"{guidance_block}"
            )
        ),
    ]

    try:
        resp = await llm.ainvoke(messages)
    except Exception as exc:
        log.exception("generate_copy provider call failed")
        raise

    refusal = _detect_refusal(resp)
    if refusal:
        raise ContentSafetyBlocked(refusal)

    raw = getattr(resp, "content", "") or ""
    if isinstance(raw, list):  # Anthropic content blocks
        raw = "".join(getattr(b, "text", "") or b.get("text", "") for b in raw if b)
    text, repaired = repair_copy(str(raw))
    # Final guard — if the repair fails, let the model-level error bubble.
    validate_description_emoji(text)
    if not (MIN_LEN <= len(text) <= MAX_LEN):
        raise ValueError(
            f"copy length {len(text)} out of bounds after repair: {text!r}"
        )

    latency_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "generate_copy ok variant=%s length=%s repaired=%s latency_ms=%s",
        variant_label,
        len(text),
        repaired,
        latency_ms,
    )
    return CopyResult(text=text, latency_ms=latency_ms, repaired=repaired)


__all__ = [
    "ContentSafetyBlocked",
    "CopyResult",
    "generate_copy",
    "repair_copy",
]
