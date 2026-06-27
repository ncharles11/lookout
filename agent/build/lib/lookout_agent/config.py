from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Agent configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BACKEND_URL: str = "http://localhost:8000"
    API_KEY: str = "lookout-dev-key"
    AGENT_ID: str = "dev-agent-01"
    COLLECT_INTERVAL_S: int = 15
    ENABLE_DOCKER: bool = True
