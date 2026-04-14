"""Skeleton Supervisor node. Real routing lands in Phase 3 (T033)."""

from typing import Any


async def supervisor_node(state: dict[str, Any]) -> dict[str, Any]:
    # Stub: emits a not-yet-implemented note so the graph compiles end-to-end
    # before the real logic arrives in Phase 3.
    return {
        **state,
        "supervisor_decision": {
            "route": "out_of_scope",
            "explanation": "supervisor stub — Phase 3 implements real routing",
        },
    }
