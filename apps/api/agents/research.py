"""Research node (T034, T035, T036, T037).

Implements R-003: plan → parallel Tavily → synthesize → anti-hallucination gate.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import HumanMessage, SystemMessage

from models.errors import FailureCode
from models.research import (
    Finding,
    IntelligenceBrief,
    RawIntelligenceBrief,
    ResearchPlan,
    SourceAttribution,
)

STRONG_SOURCE_TYPES = {"news", "official", "competitor_site"}
CLAIM_MAX = 280
EVIDENCE_MAX = 1200
NOTES_MAX = 500
UNSOURCED_DEFAULT_NOTE = "Evidence not supported by any verified source."
from services.llm_router import get_llm
from tools.tavily_search import TavilyTool, get_registered_urls, reset_registry

log = logging.getLogger(__name__)


async def _safe_dispatch(name: str, data: dict[str, Any]) -> None:
    """Dispatch a custom event, swallowing the "no parent run id" error that
    occurs when the node is invoked directly from a test (not via the graph)."""
    with contextlib.suppress(RuntimeError):
        await adispatch_custom_event(name, data)


class BudgetExceeded(Exception):
    pass


class NoFindingsAboveThreshold(Exception):
    pass


class LLMInvalidOutput(Exception):
    pass


PLAN_PROMPT = """You are the research planning step. Decompose the user's \
question into 3–5 focused sub-queries that together answer it. Each sub-query \
must state an `angle` (competitive, audience, market, channel, temporal, \
adjacent) and a short `query` string."""

SYNTH_PROMPT = """You are the research synthesis step for Amplify. Produce a \
structured IntelligenceBrief.

Rules:
- Use ONLY URLs that appear in the provided snippets — never invent a URL.
- Each finding's `claim` MUST be <= 280 characters. Keep `evidence` <= 1200 characters.
- Mark `confidence="high"` only if a finding has >= 2 sources OR exactly one source \
whose `source_type` is in {news, official, competitor_site}. Otherwise use "medium" or "low".
- If a finding has no supporting source, set `unsourced=true` AND set `notes` \
explaining why it cannot be sourced. Never emit `unsourced=true` without `notes`."""


async def _plan(raw_question: str) -> ResearchPlan:
    llm = get_llm("research_plan").with_structured_output(
        ResearchPlan, method="function_calling"
    )
    prompt = [
        SystemMessage(content=PLAN_PROMPT),
        HumanMessage(content=f"Question: {raw_question}"),
    ]
    try:
        return await llm.ainvoke(prompt)  # type: ignore[return-value]
    except Exception as exc:
        log.exception("research plan failed")
        raise LLMInvalidOutput(f"research plan failed: {exc}") from exc


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    # Leave room for the ellipsis char.
    return text[: max(0, limit - 1)].rstrip() + "…"


def _normalize_raw_brief(
    raw: Any, *, scoped_question: str
) -> IntelligenceBrief:
    """Convert a permissive RawIntelligenceBrief (or anything duck-typed the
    same way) into a strict IntelligenceBrief, repairing common LLM slips."""
    kept: list[Finding] = []
    for rf in getattr(raw, "findings", []) or []:
        claim = _truncate(rf.claim or "", CLAIM_MAX)
        evidence = _truncate(rf.evidence or "", EVIDENCE_MAX)
        notes = rf.notes
        if notes is not None:
            notes = _truncate(notes, NOTES_MAX)
        unsourced = bool(rf.unsourced)
        sources = list(rf.sources or [])

        if unsourced and not notes:
            notes = UNSOURCED_DEFAULT_NOTE

        confidence = rf.confidence
        if confidence == "high" and not unsourced:
            strong = any(s.source_type in STRONG_SOURCE_TYPES for s in sources)
            if not (len(sources) >= 2 or (len(sources) == 1 and strong)):
                confidence = "medium"

        try:
            kept.append(
                Finding(
                    id=rf.id,
                    rank=rf.rank,
                    claim=claim,
                    evidence=evidence,
                    confidence=confidence,
                    sources=sources,
                    contradicts=list(rf.contradicts or []),
                    unsourced=unsourced,
                    notes=notes,
                )
            )
        except Exception:
            log.warning("dropping finding %s after normalization failure", rf.id)
            continue

    if not kept:
        raise LLMInvalidOutput("synthesis produced no usable findings after normalization")

    status = (
        "complete"
        if len(kept) >= 3 and any(f.confidence == "high" for f in kept)
        else "low_confidence"
    )
    return IntelligenceBrief(
        id=getattr(raw, "id", None) or f"br_{uuid4().hex[:12]}",
        v=1,
        user_id=getattr(raw, "user_id", None) or "",
        conversation_id=getattr(raw, "conversation_id", None) or "",
        research_request_id=getattr(raw, "research_request_id", None) or "",
        scoped_question=getattr(raw, "scoped_question", None) or scoped_question,
        status=status,
        findings=kept,
        generated_at=getattr(raw, "generated_at", None) or datetime.now(UTC),
        model_used=getattr(raw, "model_used", None) or "unknown",
        trace_id=getattr(raw, "trace_id", None),
    )


async def _synthesize(
    *,
    user_id: str,
    conversation_id: str,
    research_request_id: str,
    scoped_question: str,
    snippets: list[dict[str, Any]],
) -> IntelligenceBrief:
    llm = get_llm("research_synthesize").with_structured_output(
        RawIntelligenceBrief, method="function_calling"
    )
    context = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "research_request_id": research_request_id,
        "scoped_question": scoped_question,
        "snippets": snippets,
    }
    prompt = [
        SystemMessage(content=SYNTH_PROMPT),
        HumanMessage(content=f"Context:\n{context}"),
    ]
    try:
        raw = await llm.ainvoke(prompt)
    except Exception as exc:
        log.exception("research synthesis failed")
        raise LLMInvalidOutput(f"synthesis failed: {exc}") from exc
    try:
        return _normalize_raw_brief(raw, scoped_question=scoped_question)
    except LLMInvalidOutput:
        raise
    except Exception as exc:
        log.exception("research synthesis normalization failed")
        raise LLMInvalidOutput(f"synthesis normalization failed: {exc}") from exc


def _filter_fabricated(
    brief: IntelligenceBrief, *, research_request_id: str
) -> IntelligenceBrief:
    """Drop sources whose URLs were not returned by Tavily for this request."""
    allowed_raw = get_registered_urls(research_request_id)
    allowed = {u.rstrip("/") for u in allowed_raw}

    def _clean(sources: list[SourceAttribution]) -> list[SourceAttribution]:
        return [s for s in sources if str(s.url).rstrip("/") in allowed]

    kept: list[Finding] = []
    for f in brief.findings:
        cleaned = _clean(f.sources)
        if not cleaned and not f.unsourced:
            continue
        try:
            rebuilt = Finding(
                id=f.id,
                rank=f.rank,
                claim=f.claim,
                evidence=f.evidence,
                confidence=(
                    f.confidence if (cleaned or f.unsourced) else "low"
                ),
                sources=cleaned,
                contradicts=f.contradicts,
                unsourced=f.unsourced,
                notes=f.notes,
            )
        except Exception:
            # High-confidence invariants may fail after filtering; retry as low.
            try:
                rebuilt = Finding(
                    id=f.id,
                    rank=f.rank,
                    claim=f.claim,
                    evidence=f.evidence,
                    confidence="low",
                    sources=cleaned,
                    contradicts=f.contradicts,
                    unsourced=f.unsourced,
                    notes=f.notes,
                )
            except Exception:
                continue
        kept.append(rebuilt)

    if not kept:
        raise NoFindingsAboveThreshold(
            "no findings survived source verification; try rephrasing"
        )

    status = (
        "complete"
        if len(kept) >= 3 and any(k.confidence == "high" for k in kept)
        else "low_confidence"
    )
    return brief.model_copy(update={"findings": kept, "status": status})


async def _run_searches(
    plan: ResearchPlan,
    *,
    tool: TavilyTool,
    research_request_id: str,
    budget_queries: int,
) -> list[dict[str, Any]]:
    sub_queries = plan.sub_queries[:budget_queries]

    async def _one(q: str) -> list[dict[str, Any]]:
        results = await tool.search(q, research_request_id=research_request_id)
        return [
            {
                "title": r.title,
                "url": r.url,
                "content": r.content,
                "source_type": r.source_type,
            }
            for r in results
        ]

    all_snippets: list[dict[str, Any]] = []
    for chunk in await asyncio.gather(*[_one(sq.query) for sq in sub_queries]):
        all_snippets.extend(chunk)
    return all_snippets


async def _research_body(state: dict[str, Any]) -> dict[str, Any]:
    from config import get_settings

    settings = get_settings()
    current = state.get("current_request") or {}
    research_request_id = current.get("id") or f"rq_{uuid4().hex[:12]}"
    raw_question = current.get("raw_question") or ""
    scoped_question = current.get("scoped_question") or raw_question
    user_id = state.get("user_id") or ""
    conversation_id = state.get("conversation_id") or ""

    reset_registry(research_request_id)
    tool = TavilyTool(redis=None)

    await _safe_dispatch(
        "progress",
        {"phase": "planning", "message": "Decomposing your question into sub-queries"},
    )
    plan = await _plan(raw_question)

    await _safe_dispatch(
        "progress",
        {
            "phase": "searching",
            "message": (
                f"Running {min(len(plan.sub_queries), settings.research_budget_queries)} searches"
            ),
            "detail": {"queries": [sq.query for sq in plan.sub_queries]},
        },
    )
    snippets = await _run_searches(
        plan,
        tool=tool,
        research_request_id=research_request_id,
        budget_queries=settings.research_budget_queries,
    )

    await _safe_dispatch(
        "progress",
        {"phase": "synthesizing", "message": "Synthesizing findings"},
    )
    brief = await _synthesize(
        user_id=user_id,
        conversation_id=conversation_id,
        research_request_id=research_request_id,
        scoped_question=scoped_question,
        snippets=snippets,
    )

    await _safe_dispatch(
        "progress",
        {"phase": "validating", "message": "Verifying source attributions"},
    )
    verified = _filter_fabricated(brief, research_request_id=research_request_id)
    verified = verified.model_copy(
        update={
            "user_id": user_id,
            "conversation_id": conversation_id,
            "research_request_id": research_request_id,
            "generated_at": datetime.now(UTC),
        }
    )

    return {
        **state,
        "brief": verified.model_dump(mode="json"),
        "_research_outcome": "complete",
    }


async def research_node(state: dict[str, Any]) -> dict[str, Any]:
    from config import get_settings

    s = get_settings()
    try:
        return await asyncio.wait_for(
            _research_body(state), timeout=s.research_budget_seconds
        )
    except TimeoutError as exc:
        raise BudgetExceeded("research budget exceeded") from exc


EXCEPTION_TO_FAILURE_CODE = {
    BudgetExceeded: FailureCode.budget_exceeded,
    NoFindingsAboveThreshold: FailureCode.no_findings_above_threshold,
    LLMInvalidOutput: FailureCode.llm_invalid_output,
}
