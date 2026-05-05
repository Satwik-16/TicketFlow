"""
=============================================================================
Apexon AI Agent — Configuration Core Service
=============================================================================
Centralized configuration loader using Pydantic BaseSettings.

All environment variables are validated at startup — if a required key is
missing or malformed, the application fails fast with a clear error message.

Usage:
    from backend.core.configCoreService import get_settings
    settings = get_settings()
    print(settings.DATABASE_URL)
=============================================================================
"""

from __future__ import annotations

import functools

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """
    Validates and exposes all environment variables required by the Apexon AI
    Agent. Values are loaded from a `.env` file in the project root.

    Attributes:
        DATABASE_URL:  Async-compatible PostgreSQL connection string.
        GROQ_API_KEY:  Groq API key for LLM inference.
        APP_ENV:       Runtime environment identifier.
    """

    # -------------------------------------------------------------------------
    # Pydantic Settings configuration
    # -------------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection string (postgresql://user:pass@host:port/db).",
        examples=["postgresql://apexon_admin:secret@localhost:5432/apexon_ai_db"],
    )

    # -------------------------------------------------------------------------
    # AI / LLM
    # -------------------------------------------------------------------------
    GROQ_API_KEY: str = Field(
        ...,
        description="Groq API key for LLM inference.",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    APP_ENV: str = Field(
        default="development",
        description="Runtime environment (development | staging | production).",
    )


@functools.lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Returns a cached singleton of the application settings.

    The first call validates and loads the `.env` file; subsequent calls
    return the same instance without re-reading the filesystem.
    """
    return AppSettings()  # type: ignore[call-arg]
