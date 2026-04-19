"""Variant diversity checker (T022).

The two copy variants a run produces MUST differ meaningfully (SC-002). We
compute a crude bag-of-words cosine similarity between A and B; anything
above the threshold triggers ONE retry of variant B with a spin-off prompt,
and if similarity is still above threshold after the retry we emit a
`diversity_warning` flag on the request.

The agent calls `should_retry_for_diversity` after the initial drafts are
in hand and `mark_diversity_warning` if the retry did not help. The
function is deterministic so it is trivial to unit-test.
"""

from __future__ import annotations

import math
import re
from collections import Counter

DIVERSITY_THRESHOLD = 0.9

_WORD = re.compile(r"[A-Za-z0-9']+")


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def cosine_similarity(a: str, b: str) -> float:
    """Token-level cosine similarity in [0, 1]."""

    ta = Counter(_tokens(a))
    tb = Counter(_tokens(b))
    if not ta or not tb:
        return 0.0
    shared = set(ta) & set(tb)
    dot = sum(ta[t] * tb[t] for t in shared)
    na = math.sqrt(sum(v * v for v in ta.values()))
    nb = math.sqrt(sum(v * v for v in tb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def needs_retry(a: str, b: str, *, threshold: float = DIVERSITY_THRESHOLD) -> bool:
    return cosine_similarity(a, b) > threshold


__all__ = [
    "DIVERSITY_THRESHOLD",
    "cosine_similarity",
    "needs_retry",
]
