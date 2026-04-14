"""Test fakes for LangChain LLMs and Tavily (T053–T056).

Provides:
- FakeStructuredLLM: stand-in for `get_llm(...).with_structured_output(Cls)`
  that returns a preloaded instance on .ainvoke().
- install_fake_llms(monkeypatch, {purpose: object}): patches get_llm in each
  agents/* module so Plan/Brief/Supervisor calls go through the fakes.
- install_fake_tavily(monkeypatch, list[dict]): replaces tools.tavily_search
  ._raw_search with a fixture-returning async function.

Deterministic CI without hitting live APIs, per research.md R-013.
"""

from __future__ import annotations

from typing import Any


class FakeStructuredLLM:
    def __init__(self, response: Any) -> None:
        self._resp = response

    def with_structured_output(self, _cls: Any) -> FakeStructuredLLM:
        return self

    async def ainvoke(self, _prompt: Any) -> Any:
        return self._resp


def install_fake_llms(monkeypatch, by_purpose: dict[str, Any]) -> None:
    def fake_get_llm(purpose: str) -> FakeStructuredLLM:
        if purpose not in by_purpose:
            raise KeyError(f"no fake LLM registered for purpose={purpose}")
        return FakeStructuredLLM(by_purpose[purpose])

    for mod in ("agents.supervisor", "agents.research", "agents.clarification"):
        monkeypatch.setattr(f"{mod}.get_llm", fake_get_llm, raising=False)


def install_fake_tavily(monkeypatch, results: list[dict]) -> None:
    async def fake_raw_search(query: str, *, max_results: int = 5):
        return results

    monkeypatch.setattr("tools.tavily_search._raw_search", fake_raw_search)
