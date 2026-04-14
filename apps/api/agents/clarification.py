"""Clarification node (T042).

Emits a clarification_poll ephemeral_ui custom event then pauses the graph
via LangGraph's `interrupt`. The SSE handler in routers/chat.py picks up
the interrupt, keeps the stream open, and waits on services.resume_bus
for the user's POST /api/v1/chat/ephemeral response. On resume, the
supervisor is re-entered with the narrowed question.
"""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from services.llm_router import get_llm

CLARIFY_PROMPT = """Given the user's vague research question, produce EXACTLY 3 \
narrowing options the user can pick from with a single click. Keep each option \
under 80 characters and mutually exclusive. Return a JSON object of the form \
{"options": ["...", "...", "..."]}."""


async def _generate_options(raw_question: str) -> list[str]:
    from pydantic import BaseModel, Field

    class _Options(BaseModel):
        options: list[str] = Field(..., min_length=3, max_length=4)

    llm = get_llm("ui_schema").with_structured_output(
        _Options, method="function_calling"
    )
    try:
        resp: _Options = await llm.ainvoke(  # type: ignore[assignment]
            [
                SystemMessage(content=CLARIFY_PROMPT),
                HumanMessage(content=raw_question),
            ]
        )
        return resp.options
    except Exception:
        return [
            "Focus on competitors' public activity",
            "Focus on audience and channel data",
            "Focus on pricing and positioning",
        ]


async def clarification_node(state: dict[str, Any]) -> dict[str, Any]:
    current = state.get("current_request") or {}
    raw = current.get("raw_question") or ""
    research_request_id = current.get("id") or "rq_unknown"

    options = await _generate_options(raw)
    poll = {
        "research_request_id": research_request_id,
        "prompt": "Which direction do you want me to take?",
        "options": options,
    }
    await adispatch_custom_event(
        "ephemeral_ui",
        {"component_type": "clarification_poll", "component": poll},
    )

    # Suspend the graph until POST /chat/ephemeral resumes it.
    chosen = interrupt(poll)

    # chosen is expected to be {"selected_option_index": int}
    idx = (chosen or {}).get("selected_option_index", 0) if isinstance(chosen, dict) else 0
    narrowed = options[idx] if 0 <= idx < len(options) else options[0]

    merged_question = f"{raw}\n\nNarrowing: {narrowed}"
    new_request = {**current, "raw_question": merged_question, "scoped_question": merged_question}
    return {
        **state,
        "current_request": new_request,
        "supervisor_decision": {
            "route": "research",
            "scoped_question": merged_question,
            "explanation": "clarification completed; routing to research",
        },
    }
