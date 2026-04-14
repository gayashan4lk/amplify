"""LangGraph state graph: supervisor → {research | clarification | END}.

This is the skeleton wired in Phase 2. Phase 3 fills in real node bodies and
the PostgresSaver checkpointer pointed at Neon.
"""

from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

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
    if route == "research" or route == "followup_on_existing_brief":
        return "research"
    if route == "clarification_needed":
        return "clarification"
    return END


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
    builder.add_edge("research", END)
    builder.add_edge("clarification", END)

    return builder.compile(checkpointer=checkpointer or InMemorySaver())
