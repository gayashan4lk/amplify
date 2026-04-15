"""T086: intelligence-brief.md invariant 3 — high confidence requires 2+
sources OR 1 source of a strong source type (news / official /
competitor_site). Enforced at the Pydantic layer by `Finding`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from models.research import Finding, SourceAttribution

CONSULTED_AT = datetime(2026, 4, 15, tzinfo=UTC)


def _src(source_type: str, url: str = "https://example.com/a") -> SourceAttribution:
    return SourceAttribution(
        title="t",
        url=url,  # type: ignore[arg-type]
        source_type=source_type,  # type: ignore[arg-type]
        consulted_at=CONSULTED_AT,
    )


def _finding(confidence: str, sources: list[SourceAttribution]) -> Finding:
    return Finding(
        id="f1",
        rank=1,
        claim="c",
        evidence="e",
        confidence=confidence,  # type: ignore[arg-type]
        sources=sources,
    )


# Strong source types that independently satisfy the high-confidence bar.
STRONG_TYPES = ["news", "official", "competitor_site"]
# Source types that do NOT independently satisfy the high-confidence bar.
WEAK_TYPES = ["blog", "forum", "ad_library", "analytics", "other"]


@pytest.mark.parametrize("source_type", STRONG_TYPES)
def test_high_confidence_one_strong_source_ok(source_type: str):
    f = _finding("high", [_src(source_type)])
    assert f.confidence == "high"


@pytest.mark.parametrize("source_type", WEAK_TYPES)
def test_high_confidence_one_weak_source_rejected(source_type: str):
    with pytest.raises(ValidationError):
        _finding("high", [_src(source_type)])


@pytest.mark.parametrize("source_type", WEAK_TYPES)
def test_high_confidence_two_weak_sources_ok(source_type: str):
    f = _finding(
        "high",
        [
            _src(source_type, "https://example.com/a"),
            _src(source_type, "https://example.com/b"),
        ],
    )
    assert len(f.sources) == 2


@pytest.mark.parametrize("source_type", STRONG_TYPES + WEAK_TYPES)
def test_medium_confidence_one_source_always_ok(source_type: str):
    f = _finding("medium", [_src(source_type)])
    assert f.confidence == "medium"


@pytest.mark.parametrize("source_type", STRONG_TYPES + WEAK_TYPES)
def test_low_confidence_one_source_always_ok(source_type: str):
    f = _finding("low", [_src(source_type)])
    assert f.confidence == "low"


def test_high_confidence_no_sources_rejected():
    with pytest.raises(ValidationError):
        _finding("high", [])


def test_high_confidence_mixed_strong_and_weak_ok():
    f = _finding(
        "high",
        [_src("news"), _src("blog", "https://example.com/b")],
    )
    assert f.confidence == "high"
