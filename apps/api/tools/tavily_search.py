"""Tavily search wrapper (T032).

Responsibilities per research.md R-010:
- 10s per-call timeout, single retry on network error.
- Short-lived (5 min) Redis cache keyed by SHA-256 of normalized query.
- Module-level per-request URL registry used by the anti-hallucination gate
  in agents/research.py (R-003 step 4) to assert every cited source URL came
  from a real Tavily result.

Tests monkeypatch `_raw_search` to inject recorded fixtures — no live API
calls in CI (research.md R-013).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from config import get_settings

log = logging.getLogger(__name__)

_CALL_TIMEOUT_SECONDS = 10.0
_CACHE_KEY_PREFIX = "tavily:q:"

# per-research_request_id → set of legitimate source URLs ever returned by Tavily
_url_registry: dict[str, set[str]] = {}


class TavilyUnavailable(Exception):
    """Tavily cannot service this request — config/auth/network problem.

    Classified upstream (agents/research.py::EXCEPTION_TO_FAILURE_CODE) to
    FailureCode.tavily_unavailable so the user sees a specific, recoverable
    FailureCard (Constitution V — no silent/generic failures).
    """


@dataclass
class TavilyResult:
    title: str
    url: str
    content: str
    score: float | None = None
    source_type: str = "other"
    accessible: bool = True


def _normalize(query: str) -> str:
    return " ".join(query.lower().split())


def _cache_key(query: str) -> str:
    digest = hashlib.sha256(_normalize(query).encode("utf-8")).hexdigest()
    return f"{_CACHE_KEY_PREFIX}{digest}"


async def _raw_search(query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
    """Live Tavily call. Monkeypatched in tests."""
    from tavily import AsyncTavilyClient  # type: ignore[import-untyped]

    s = get_settings()
    api_key = (s.tavily_api_key or "").strip()
    if not api_key:
        raise TavilyUnavailable("TAVILY_API_KEY is not configured")
    client = AsyncTavilyClient(api_key=api_key)
    try:
        resp = await client.search(
            query=query, max_results=max_results, search_depth="basic"
        )
    except TimeoutError:
        # Let TavilyTool.search own timeout retry/classification.
        raise
    except TavilyUnavailable:
        raise
    except Exception as exc:
        # Auth errors (401/403), network failures, malformed responses, etc.
        raise TavilyUnavailable(f"Tavily call failed: {exc}") from exc
    return list(resp.get("results", []))


def _classify(url: str) -> str:
    lower = url.lower()
    if "news" in lower or any(
        n in lower for n in ("techcrunch", "reuters", "bloomberg", "wsj")
    ):
        return "news"
    if "linkedin.com" in lower or "twitter.com" in lower or "x.com" in lower:
        return "competitor_site"
    if lower.endswith((".gov", ".edu")) or "/official" in lower:
        return "official"
    if "blog" in lower or "medium.com" in lower:
        return "blog"
    if "reddit.com" in lower or "ycombinator" in lower:
        return "forum"
    return "other"


class TavilyTool:
    def __init__(self, *, redis: Any | None = None) -> None:
        self._redis = redis

    async def search(
        self,
        query: str,
        *,
        research_request_id: str,
        max_results: int = 5,
    ) -> list[TavilyResult]:
        cached = await self._cache_get(query)
        if cached is None:
            try:
                raw = await asyncio.wait_for(
                    _raw_search(query, max_results=max_results),
                    timeout=_CALL_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                log.warning("tavily timeout; retrying once", extra={"query": query})
                try:
                    raw = await asyncio.wait_for(
                        _raw_search(query, max_results=max_results),
                        timeout=_CALL_TIMEOUT_SECONDS,
                    )
                except TimeoutError as exc:
                    raise TavilyUnavailable(
                        "Tavily timed out twice in a row"
                    ) from exc
            await self._cache_set(query, raw)
        else:
            raw = cached

        results = [
            TavilyResult(
                title=r.get("title", "") or r.get("url", ""),
                url=r.get("url", ""),
                content=r.get("content", "") or r.get("snippet", ""),
                score=r.get("score"),
                source_type=_classify(r.get("url", "")),
                accessible=bool(r.get("accessible", True)),
            )
            for r in raw
            if r.get("url")
        ]
        registry = _url_registry.setdefault(research_request_id, set())
        for r in results:
            registry.add(r.url)
        return results

    async def _cache_get(self, query: str) -> list[dict[str, Any]] | None:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(_cache_key(query))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:  # pragma: no cover
            return None

    async def _cache_set(self, query: str, raw: list[dict[str, Any]]) -> None:
        if self._redis is None:
            return
        try:
            s = get_settings()
            await self._redis.set(
                _cache_key(query),
                json.dumps(raw),
                ex=s.tavily_cache_ttl_seconds,
            )
        except Exception:  # pragma: no cover
            pass


def get_registered_urls(research_request_id: str) -> set[str]:
    return set(_url_registry.get(research_request_id, set()))


def reset_registry(research_request_id: str) -> None:
    _url_registry.pop(research_request_id, None)


def _test_register_urls(research_request_id: str, urls: list[str]) -> None:
    """Testing hook — lets tests seed the registry without going through search."""
    _url_registry.setdefault(research_request_id, set()).update(urls)
