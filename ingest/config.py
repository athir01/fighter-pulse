"""Typed environment configuration for the ingest worker.

Mirrors the fail-fast pattern used elsewhere: a missing required var raises a
clear error instead of surfacing later as an opaque failure deep in a run.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    database_url: str
    anthropic_api_key: str

    llm_cost_cap_usd: float = 5.00
    """Hard ceiling on cumulative LLM spend across all runs (see cost_tracker.py)."""

    ingest_user_agent: str = "fighter-pulse/0.1"
    ingest_rate_limit_rps: float = 1.0


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        fields = ", ".join(str(err["loc"][0]).upper() for err in exc.errors())
        raise RuntimeError(
            f"Invalid configuration. Check these environment variables: {fields}. "
            "See .env.example."
        ) from exc
