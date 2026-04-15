"""T081: research takes longer than the budget → BudgetExceeded."""

from __future__ import annotations

import asyncio

import pytest

from agents.research import (
    EXCEPTION_TO_FAILURE_CODE,
    BudgetExceeded,
    research_node,
)
from models.errors import FailureCode


class _SlowLLM:
    def with_structured_output(self, *_a, **_kw):
        return self

    async def ainvoke(self, _prompt):
        await asyncio.sleep(5)
        raise AssertionError("should have timed out")


@pytest.mark.asyncio
async def test_research_budget_exceeded(monkeypatch):
    from config import get_settings

    # Drop the budget so the node times out immediately.
    settings = get_settings()
    monkeypatch.setattr(settings, "research_budget_seconds", 0.05, raising=False)

    monkeypatch.setattr("agents.research.get_llm", lambda _p: _SlowLLM())

    state = {
        "messages": [{"role": "user", "content": "q"}],
        "user_id": "u1",
        "conversation_id": "c1",
        "current_request": {"id": "rq1", "raw_question": "q"},
    }

    with pytest.raises(BudgetExceeded):
        await research_node(state)

    assert EXCEPTION_TO_FAILURE_CODE[BudgetExceeded] is FailureCode.budget_exceeded
