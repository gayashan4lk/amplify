"""Skeleton Clarification node. Real poll emission lands in T042."""

from typing import Any


async def clarification_node(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "_note": "clarification stub — Phase 3 implements poll + interrupt",
    }
