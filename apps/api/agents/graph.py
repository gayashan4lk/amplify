"""LangGraph state graph: supervisor → {research | clarification → research | END}.

The checkpointer is either AsyncPostgresSaver (when `LANGGRAPH_CHECKPOINT_URL`
or `DATABASE_URL` points at a reachable Postgres) or `InMemorySaver` for
tests / local dev without a database. T062 wires the Postgres path.
"""

import logging
import os
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

log = logging.getLogger(__name__)

from agents.clarification import clarification_node
from agents.research import research_node
from agents.supervisor import supervisor_node


class GraphState(TypedDict, total=False):
    messages: Annotated[list[Any], add_messages]
    user_id: str
    conversation_id: str
    current_request: dict[str, Any] | None
    brief: dict[str, Any] | None
    supervisor_decision: dict[str, Any] | None


def _route_after_supervisor(state: GraphState) -> str:
    decision = state.get("supervisor_decision") or {}
    route = decision.get("route", "out_of_scope")
    if route == "research":
        return "research"
    if route == "followup_on_existing_brief":
        # For a followup we have no new research to run; we rely on the chat
        # router to stream a text_delta response grounded in the stored brief,
        # so the graph itself ends here.
        return END
    if route == "clarification_needed":
        return "clarification"
    return END


def _default_checkpointer() -> Any:
    """Best-effort Postgres-backed checkpointer, falling back to in-memory.

    We try AsyncPostgresSaver only when an explicit opt-in env var is set so
    tests and local runs never block on a database connection.
    """
    url = os.getenv("LANGGRAPH_CHECKPOINT_URL")
    if not url:
        return InMemorySaver()
    try:  # pragma: no cover — exercised only with a real DB
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver_cm = AsyncPostgresSaver.from_conn_string(url)
        # The context-manager form is how upstream docs recommend using it;
        # we deliberately keep it open for the lifetime of the process.
        saver = saver_cm.__enter__()  # type: ignore[union-attr]
        log.info("graph using AsyncPostgresSaver")
        return saver
    except Exception as exc:  # pragma: no cover
        log.warning("failed to init AsyncPostgresSaver, falling back: %s", exc)
        return InMemorySaver()


def build_graph(checkpointer: Any | None = None):
    builder = StateGraph(GraphState)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("research", research_node)
    builder.add_node("clarification", clarification_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"research": "research", "clarification": "clarification", END: END},
    )
    # After clarification completes (user chose a narrowing), fall through to
    # the research node directly — cheaper than re-entering the supervisor.
    builder.add_edge("clarification", "research")
    builder.add_edge("research", END)

    return builder.compile(checkpointer=checkpointer or _default_checkpointer())
