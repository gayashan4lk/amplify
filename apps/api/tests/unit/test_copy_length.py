"""Unit tests for copy-length repair (T023).

`repair_copy` silently fixes out-of-band output from the LLM:

- strips disallowed emoji,
- truncates >250 chars on a word boundary,
- pads <80 chars with a safe filler,
- ensures at least one allowed emoji is present.
"""

from __future__ import annotations

from tools.generate_copy import repair_copy


def test_in_range_copy_is_untouched() -> None:
    text = (
        "Our flagship headset drops today — pro-grade audio, lightweight frame, "
        "and 40-hour battery life. Tap to join the first shipment wave. 🎯"
    )
    repaired, was_repaired = repair_copy(text)
    assert repaired == text
    assert was_repaired is False


def test_too_long_copy_is_truncated_on_word_boundary() -> None:
    long_text = (
        "We rebuilt our onboarding from scratch and the early numbers are wild. "
        "Setup time down seventy percent. Support tickets down by half. "
        "Daily active users up across every cohort we measured last month. "
        "Every single team member pitched in across three sprint cycles. "
        "Try it free today and tell us what you think ✨"
    )
    repaired, was_repaired = repair_copy(long_text)
    assert len(repaired) <= 250
    assert was_repaired is True
    # truncation must not leave a dangling half-word
    assert not repaired.endswith(" ")


def test_too_short_copy_is_padded() -> None:
    short = "Big news today 🎯"
    repaired, was_repaired = repair_copy(short)
    assert len(repaired) >= 80
    assert was_repaired is True
    assert "🎯" in repaired


def test_missing_emoji_gets_appended() -> None:
    text = (
        "Our flagship headset drops today with pro-grade audio, a lightweight "
        "frame, and forty hour battery life across two-day shoots."
    )
    assert all(e not in text for e in ("🎯", "✨", "🚀", "💡"))
    repaired, was_repaired = repair_copy(text)
    assert was_repaired is True
    # at least one allowed emoji now present
    assert any(e in repaired for e in ("✨", "🎯", "🚀", "💡", "🔥"))
