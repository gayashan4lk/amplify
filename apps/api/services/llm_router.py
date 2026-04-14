"""Centralized model selection per research.md R-009."""

from functools import cache
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from config import get_settings

Purpose = Literal["supervisor", "research_plan", "research_synthesize", "ui_schema"]


@cache
def _supervisor() -> BaseChatModel:
    s = get_settings()
    return ChatAnthropic(
        model_name="claude-sonnet-4-5",
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
        model="gpt-4o",
        temperature=0.2,
        api_key=s.openai_api_key,
        timeout=30,
    )


@cache
def _research_synthesize() -> BaseChatModel:
    s = get_settings()
    return ChatOpenAI(
        model="gpt-4o",
        temperature=0.1,
        api_key=s.openai_api_key,
        timeout=45,
    )


@cache
def _ui_schema() -> BaseChatModel:
    s = get_settings()
    return ChatAnthropic(
        model_name="claude-sonnet-4-5",
        temperature=0.0,
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
