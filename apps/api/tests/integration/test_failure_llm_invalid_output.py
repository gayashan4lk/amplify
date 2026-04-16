"""T079: LLM returns unparseable output → llm_invalid_output, non-recoverable.

Drives `research_node` with a fake plan LLM that always raises. The research
module wraps the error as `LLMInvalidOutput`, and the router maps that to
`FailureCode.llm_invalid_output` via `EXCEPTION_TO_FAILURE_CODE`.
"""

from __future__ import annotations

import pytest

from agents.research import (
    EXCEPTION_TO_FAILURE_CODE,
    LLMInvalidOutput,
    research_node,
)
from models.errors import FailureCode
from tests.integration._fakes import install_fake_tavily


class _ExplodingLLM:
    def with_structured_output(self, *_a, **_kw):
        return self

    async def ainvoke(self, _prompt):
        raise ValueError("not valid JSON")


@pytest.mark.asyncio
async def test_llm_invalid_output_bubbles_as_failure(monkeypatch):
    install_fake_tavily(monkeypatch, [])

    def fake_get_llm(_purpose: str):
        return _ExplodingLLM()

    monkeypatch.setattr("agents.research.get_llm", fake_get_llm)

    state = {
        "messages": [{"role": "user", "content": "Anything at all"}],
        "user_id": "u1",
        "conversation_id": "c1",
        "current_request": {"id": "rq1", "raw_question": "Anything at all"},
    }

    with pytest.raises(LLMInvalidOutput):
        await research_node(state)

    assert EXCEPTION_TO_FAILURE_CODE[LLMInvalidOutput] is FailureCode.llm_invalid_output
