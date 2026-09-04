from __future__ import annotations

from pathlib import Path

import pytest

from lesson_generator.config import Settings
from lesson_generator.exceptions import ConfigurationError
from lesson_generator.provider import GeminiModelProvider


def test_missing_api_configuration_fails_early_with_actionable_message() -> None:
    settings = Settings(api_key=None, output_dir=Path("out"), memory_db_path=Path("memory.db"))
    with pytest.raises(ConfigurationError, match="GOOGLE_API_KEY"):
        settings.validate_for_live_run()


def test_placeholder_key_and_excess_workflow_retries_are_rejected() -> None:
    placeholder = Settings(api_key="your-gemini-api-key")
    with pytest.raises(ConfigurationError, match="GOOGLE_API_KEY"):
        placeholder.validate_for_live_run()

    unbounded = Settings(api_key="test", workflow_max_retries=3)
    with pytest.raises(ConfigurationError, match="between zero and 2"):
        unbounded.validate_for_live_run()


def test_max_attempts_is_initial_plus_retries() -> None:
    settings = Settings(api_key="test", workflow_max_retries=2)
    assert settings.max_attempts == 3


def test_settings_use_google_key_and_gemini_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "primary-key")
    monkeypatch.setenv("GEMINI_API_KEY", "fallback-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    settings = Settings.from_env()
    assert settings.api_key == "primary-key"
    assert settings.model_name == "gemini-3.6-flash"


def test_gemini_provider_constructs_without_a_network_call() -> None:
    provider = GeminiModelProvider(Settings(api_key="test-key"))
    assert provider.__class__.__name__ == "GeminiModelProvider"
    assert provider._structured_evaluator is not None
