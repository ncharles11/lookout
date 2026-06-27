from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql://lookout:lookout@localhost:5432/lookout"
    PROBE_CONCURRENCY: int = 10

    # Alerting — Discord webhook (optional)
    DISCORD_WEBHOOK_URL: str | None = None

    # Anti-flapping window defaults
    ALERT_CONSECUTIVE_FAILURES: int = 3
    ALERT_FAILURE_DURATION_S: float = 60.0
    ALERT_CONSECUTIVE_SUCCESSES: int = 2


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
