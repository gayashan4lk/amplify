"""Typed settings loaded from env. All env vars live in apps/api/eample.env."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Databases
    database_url: str = Field(..., alias="DATABASE_URL")
    mongodb_uri: str = Field(..., alias="MONGODB_URI")
    mongodb_db: str = Field("amplify_dev", alias="MONGODB_DB")
    redis_url: str = Field(..., alias="REDIS_URL")

    # LLM providers
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

    # Research
    tavily_api_key: str = Field(..., alias="TAVILY_API_KEY")

    # Observability
    langsmith_api_key: str | None = Field(default=None, alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field("amplify-dev", alias="LANGSMITH_PROJECT")
    langsmith_tracing: bool = Field(True, alias="LANGSMITH_TRACING")

    # Research budgets
    research_budget_queries: int = Field(8, alias="RESEARCH_BUDGET_QUERIES")
    research_budget_seconds: int = Field(60, alias="RESEARCH_BUDGET_SECONDS")
    tavily_cache_ttl_seconds: int = Field(300, alias="TAVILY_CACHE_TTL_SECONDS")
    user_research_rate_limit_per_hour: int = Field(10, alias="USER_RESEARCH_RATE_LIMIT_PER_HOUR")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
