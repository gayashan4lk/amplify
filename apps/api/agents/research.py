"""Skeleton Research node. Real plan→search→synthesize→validate lands in T034."""

from typing import Any


async def research_node(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "brief": None,
        "_note": "research stub — Phase 3 implements the real pipeline",
    }
