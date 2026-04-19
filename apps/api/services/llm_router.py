"""Centralized model selection per research.md R-009."""

from __future__ import annotations

from functools import cache
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from config import get_settings

Purpose = Literal[
    "supervisor",
    "research_plan",
    "research_synthesize",
    "ui_schema",
    "content_copy",
]

ImagePurpose = Literal["content_image"]

# Target dimensions for Facebook post imagery (FR-007). Letterbox on
# downstream mismatch rather than failing the whole variant.
CONTENT_IMAGE_SIZE: tuple[int, int] = (1080, 1080)
CONTENT_IMAGE_MODEL = "gemini-3.1-flash-image-preview"


@cache
def _supervisor() -> BaseChatModel:
    s = get_settings()
    return ChatAnthropic(
        model_name="claude-haiku-4-5-20251001",
        temperature=0.1,
        anthropic_api_key=s.anthropic_api_key,
        timeout=30,
        max_retries=1,
        stop=None,
    )


@cache
def _research_plan() -> BaseChatModel:
    s = get_settings()
    return ChatOpenAI(
        model="gpt-5.4-nano-2026-03-17",
        temperature=0.2,
        api_key=s.openai_api_key,
        timeout=30,
    )


@cache
def _research_synthesize() -> BaseChatModel:
    s = get_settings()
    return ChatOpenAI(
        model="gpt-5.4-nano-2026-03-17",
        temperature=0.1,
        api_key=s.openai_api_key,
        timeout=45,
    )


@cache
def _ui_schema() -> BaseChatModel:
    s = get_settings()
    return ChatAnthropic(
        model_name="claude-haiku-4-5-20251001",
        temperature=0.0,
        anthropic_api_key=s.anthropic_api_key,
        timeout=30,
        max_retries=1,
        stop=None,
    )


@cache
def _content_copy() -> BaseChatModel:
    """Haiku for Facebook post copy drafting (T012). Temperature tuned for
    on-brand variant diversity; prompt enforces 80-250 chars + emoji."""

    s = get_settings()
    return ChatAnthropic(
        model_name="claude-haiku-4-5-20251001",
        temperature=0.6,
        anthropic_api_key=s.anthropic_api_key,
        timeout=30,
        max_retries=1,
        stop=None,
    )


def get_llm(purpose: Purpose) -> BaseChatModel:
    match purpose:
        case "supervisor":
            return _supervisor()
        case "research_plan":
            return _research_plan()
        case "research_synthesize":
            return _research_synthesize()
        case "ui_schema":
            return _ui_schema()
        case "content_copy":
            return _content_copy()


@cache
def _google_genai_client() -> Any:
    from google import genai  # type: ignore[import-not-found]

    s = get_settings()
    return genai.Client(api_key=s.google_api_key)


def get_image_model(purpose: ImagePurpose) -> tuple[Any, str, tuple[int, int]]:
    """Return `(client, model_name, (width, height))` for an image route.

    Kept as a separate entry-point from `get_llm` because the Google GenAI
    SDK does not share the LangChain `BaseChatModel` interface.
    """

    if purpose != "content_image":
        raise ValueError(f"unknown image purpose {purpose!r}")
    return _google_genai_client(), CONTENT_IMAGE_MODEL, CONTENT_IMAGE_SIZE
