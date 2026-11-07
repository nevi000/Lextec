from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> repo root is 4 levels up from this file's directory
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Runtime configuration. Read from environment variables or the repo-root `.env`."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["development", "test", "production"] = "development"
    ai_provider: Literal["mock", "gemini"] = "mock"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    ai_timeout_seconds: float = 30.0
    ai_max_retries: int = 1  # transient errors only; every attempt counts against the limits
    ai_rephrase_questions: bool = False
    ai_thinking_level: str = (
        "LOW"  # gemini-3.x: LOW / MEDIUM / HIGH (MINIMAL is rejected by 3.8-flash)
    )

    # --- cost control (application-level limits, NOT a guaranteed Google billing cap) ---
    ai_max_calls_per_case: int = 12
    ai_max_input_tokens_per_call: int = 8000
    ai_max_output_tokens_per_call: int = (
        2500  # hard cap sent to Gemini (incl. thinking tokens); live test used 1367
    )
    ai_daily_request_limit: int = 30
    ai_daily_token_limit: int = 150_000
    ai_daily_budget_usd: float = 0.50
    ai_case_budget_usd: float = 0.10
    # Optional price override (USD per 1M tokens). Default: built-in official price table per model.
    ai_price_input_per_mtok: float | None = None
    ai_price_output_per_mtok: float | None = None
    ai_max_analysis_attempts_per_message: int = 3
    # Reference date for derived values (days since receipt). Default: today. Set e.g. 2026-11-07 for
    # reproducible demos/tests.
    app_today: date | None = None

    # --- Fedlex (official Swiss federal law; public, no API key; deterministic, never uses the LLM) ---
    fedlex_enabled: bool = True  # False = cache only, no network at all
    fedlex_sparql_url: str = "https://fedlex.data.admin.ch/sparqlendpoint"
    fedlex_allowed_hosts: list[str] = ["fedlex.data.admin.ch"]
    fedlex_cache_enabled: bool = True
    fedlex_cache_max_age_days: int = (
        14  # older snapshots are shown as "possibly outdated", never as verified
    )
    fedlex_timeout_seconds: float = 15.0
    fedlex_max_concurrent_requests: int = 2
    fedlex_min_request_interval_seconds: float = 0.5
    fedlex_max_retries: int = 2
    fedlex_max_response_bytes: int = 25_000_000
    fedlex_language: str = "de"
    # Public deep-link base of the Fedlex viewer (the data host serves data, the viewer serves people).
    fedlex_viewer_base: str = "https://www.fedlex.admin.ch"

    database_url: str = f"sqlite:///{(REPO_ROOT / 'data' / 'lextec.db').as_posix()}"
    knowledge_base_dir: Path = REPO_ROOT / "knowledge_base"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    auto_migrate: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
