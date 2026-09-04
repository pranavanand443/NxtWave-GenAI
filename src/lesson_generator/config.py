"""Centralized environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .exceptions import ConfigurationError

MAX_WORKFLOW_RETRIES = 2


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings shared by generation, evaluation, and persistence."""

    api_key: str | None
    model_name: str = "gemini-3.7-flash"
    request_timeout_seconds: float = 60.0
    provider_max_retries: int = 2
    workflow_max_retries: int = 2
    output_dir: Path = Path("outputs")
    memory_db_path: Path = Path("data/lesson_memory.sqlite3")

    @classmethod
    def from_env(
        cls,
        *,
        output_dir: Path | None = None,
        memory_db_path: Path | None = None,
    ) -> Settings:
        """Load `.env` if present, then read configuration from the environment."""

        load_dotenv()
        return cls(
            api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or None,
            model_name=os.getenv("GEMINI_MODEL", "gemini-3.7-flash"),
            request_timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "60")),
            provider_max_retries=int(os.getenv("MODEL_MAX_RETRIES", "2")),
            workflow_max_retries=int(os.getenv("WORKFLOW_MAX_RETRIES", "2")),
            output_dir=output_dir or Path(os.getenv("OUTPUT_DIR", "outputs")),
            memory_db_path=memory_db_path
            or Path(os.getenv("MEMORY_DB_PATH", "data/lesson_memory.sqlite3")),
        )

    @property
    def max_attempts(self) -> int:
        """Initial attempt plus the configured number of retries."""

        return self.workflow_max_retries + 1

    def validate_for_live_run(self) -> None:
        """Fail early with actionable guidance instead of failing inside a model call."""

        if not self.api_key or self.api_key == "your-gemini-api-key":
            raise ConfigurationError(
                "GOOGLE_API_KEY is not configured. Create a free-tier Gemini API key in "
                "Google AI Studio, copy .env.example to .env, and add the key."
            )
        if not 0 <= self.workflow_max_retries <= MAX_WORKFLOW_RETRIES:
            raise ConfigurationError(
                f"WORKFLOW_MAX_RETRIES must be between zero and {MAX_WORKFLOW_RETRIES}."
            )
        if self.provider_max_retries < 0:
            raise ConfigurationError("MODEL_MAX_RETRIES must be zero or greater.")
        if self.request_timeout_seconds <= 0:
            raise ConfigurationError("MODEL_TIMEOUT_SECONDS must be greater than zero.")
