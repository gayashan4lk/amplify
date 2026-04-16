"""Supervisor node (T033).

Uses llm_router.get_llm("supervisor") with structured output of
SupervisorDecision per research.md R-005. Routes to
  research | clarification_needed | out_of_scope | followup_on_existing_brief.

Context: last 10 messages in state plus any current IntelligenceBrief.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from models.chat import SupervisorDecision
from services.llm_router import get_llm

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are the Supervisor node for Amplify, a research assistant \
for solo founders and small marketing teams. Your only job is to classify the \
latest user message into ONE of four routes:

- "research": the user is asking a market/competitor/audience question that \
  requires web research to answer well.
- "clarification_needed": the question is too vague to research productively \
  and would benefit from narrowing.
- "out_of_scope": small talk, unrelated requests, or non-research questions. \
  Answer briefly without research.
- "followup_on_existing_brief": the user is referring back to the latest \
  intelligence brief already in this conversation (e.g., "tell me more about \
  finding 2", "can you expand on that competitor", "what sources back that?"). \
  In this case we MUST NOT re-run research; we answer using the stored brief.

Respond with a structured SupervisorDecision. Always set `explanation` to a \
single short sentence."""


def _as_role_content(m: Any) -> tuple[str, str]:
    if isinstance(m, BaseMessage):
        role = (
            "user"
            if isinstance(m, HumanMessage)
            else "assistant"
            if isinstance(m, AIMessage)
            else "system"
        )
        return role, str(m.content)
    if isinstance(m, dict):
        return m.get("role", "system"), m.get("content", "")
    return "system", str(m)


def _recent_messages(messages: list[Any]) -> list[BaseMessage]:
    """Take the last 10 messages, convert to LangChain message objects."""
    out: list[BaseMessage] = []
    for m in messages[-10:]:
        role, content = _as_role_content(m)
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(SystemMessage(content=content))
    return out


def _pick_last_user_message(messages: list[Any]) -> str:
    for m in reversed(messages):
        role, content = _as_role_content(m)
        if role == "user":
            return content
    return ""


async def supervisor_node(state: dict[str, Any]) -> dict[str, Any]:
    messages = state.get("messages") or []
    brief = state.get("brief")

    llm = get_llm("supervisor").with_structured_output(
        SupervisorDecision, method="function_calling"
    )

    context_lines: list[str] = []
    if brief:
        context_lines.append(
            "A prior intelligence brief exists in this conversation with "
            f"{len(brief.get('findings', []))} findings on scoped question: "
            f"{brief.get('scoped_question', '')!r}. If the new message refers to "
            "that brief, route 'followup_on_existing_brief'."
        )

    prompt: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    if context_lines:
        prompt.append(SystemMessage(content="\n".join(context_lines)))
    prompt.extend(_recent_messages(messages))

    try:
        decision: SupervisorDecision = await llm.ainvoke(prompt)  # type: ignore[assignment]
    except Exception as exc:
        log.exception("supervisor llm failed; defaulting to out_of_scope")
        decision = SupervisorDecision(
            route="out_of_scope",
            explanation=f"supervisor llm error: {exc}",
        )

    # Ensure scoped_question falls back to the raw last user message when the LLM
    # didn't set one — makes downstream research deterministic.
    if decision.route == "research" and not decision.scoped_question:
        decision = decision.model_copy(
            update={"scoped_question": _pick_last_user_message(messages)}
        )

    return {
        **state,
        "supervisor_decision": decision.model_dump(mode="json"),
    }
