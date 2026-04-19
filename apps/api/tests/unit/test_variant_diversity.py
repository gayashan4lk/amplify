"""Unit tests for variant diversity gate (T022).

`needs_retry` must return True when the two candidate descriptions are too
similar (cosine > 0.9) and False when they diverge enough.
"""

from __future__ import annotations

from workers.diversity import cosine_similarity, needs_retry


def test_identical_copies_need_retry() -> None:
    a = "Launch day is here and we could not be more excited to share it with you ✨"
    b = "Launch day is here and we could not be more excited to share it with you ✨"
    assert cosine_similarity(a, b) == 1.0
    assert needs_retry(a, b) is True


def test_divergent_copies_do_not_need_retry() -> None:
    a = "Our new flagship headset is ready for the stage tonight — tune in 🎯"
    b = "Behind the scenes: the engineering team rebuilt the algorithm from scratch 🧠"
    sim = cosine_similarity(a, b)
    assert sim < 0.5
    assert needs_retry(a, b) is False


def test_custom_threshold_is_respected() -> None:
    a = "aaa bbb ccc ddd"
    b = "aaa bbb ccc zzz"
    # 3/4 overlap → cosine 0.75
    sim = cosine_similarity(a, b)
    assert 0.7 < sim < 0.8
    assert needs_retry(a, b, threshold=0.5) is True
    assert needs_retry(a, b, threshold=0.9) is False
