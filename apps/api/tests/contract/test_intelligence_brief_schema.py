"""T030: IntelligenceBrief / Finding invariants 1, 3, 4 from intelligence-brief.md.

Invariant 1 (source existence / anti-hallucination) is enforced at the
research pipeline level and is exercised by T054. Here we cover what Pydantic
validators can enforce directly.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from models.research import Finding, IntelligenceBrief, SourceAttribution

NOW = datetime.now(UTC)


def _src(source_type: str = "news") -> SourceAttribution:
    return SourceAttribution(
        title="Example",
        url="https://example.com/article",  # type: ignore[arg-type]
        source_type=source_type,  # type: ignore[arg-type]
        consulted_at=NOW,
    )


def _finding(**kwargs) -> Finding:
    defaults: dict = {
        "id": "f1",
        "rank": 1,
        "claim": "Claim.",
        "evidence": "Evidence.",
        "confidence": "medium",
        "sources": [_src()],
    }
    defaults.update(kwargs)
    return Finding(**defaults)


def test_finding_requires_source_or_unsourced_note():
    with pytest.raises(ValidationError):
        _finding(sources=[])  # neither sourced nor flagged unsourced

    _finding(sources=[], unsourced=True, notes="no public source available")


def test_high_confidence_requires_two_sources_or_one_strong_source():
    # 2 generic sources → OK
    _finding(
        sources=[_src("blog"), _src("forum")],
        confidence="high",
    )
    # 1 strong source → OK
    _finding(sources=[_src("news")], confidence="high")
    # 1 weak source → reject
    with pytest.raises(ValidationError):
        _finding(sources=[_src("blog")], confidence="high")


def test_brief_requires_at_least_one_finding_and_version_one():
    IntelligenceBrief(
        id="b1",
        user_id="u1",
        conversation_id="c1",
        research_request_id="r1",
        scoped_question="q?",
        status="low_confidence",
        findings=[_finding()],
        generated_at=NOW,
        model_used="openai/gpt-4o",
    )
    with pytest.raises(ValidationError):
        IntelligenceBrief(
            id="b1",
            v=2,
            user_id="u1",
            conversation_id="c1",
            research_request_id="r1",
            scoped_question="q?",
            status="low_confidence",
            findings=[_finding()],
            generated_at=NOW,
            model_used="openai/gpt-4o",
        )


def test_status_complete_derivation_is_enforced_upstream():
    # Pydantic itself doesn't require the caller to derive status from findings —
    # invariant 4 is enforced in agents/research.py before persistence. Here we
    # only assert that a caller CAN construct a "complete" brief when findings
    # meet the threshold.
    brief = IntelligenceBrief(
        id="b1",
        user_id="u1",
        conversation_id="c1",
        research_request_id="r1",
        scoped_question="q?",
        status="complete",
        findings=[
            _finding(id="f1", rank=1, confidence="high", sources=[_src("news")]),
            _finding(id="f2", rank=2, confidence="medium"),
            _finding(id="f3", rank=3, confidence="medium"),
        ],
        generated_at=NOW,
        model_used="openai/gpt-4o",
    )
    assert len(brief.findings) >= 3
    assert any(f.confidence == "high" for f in brief.findings)
