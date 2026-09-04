"""One primary model-provider boundary shared by generator and evaluator."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import ValidationError

from .config import Settings
from .exceptions import EvaluatorResponseError, ModelGenerationError
from .schemas import LessonEvaluation


class ModelProvider(Protocol):
    """Small seam used by production Gemini calls and deterministic test fakes."""

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str: ...

    def evaluate_lesson(self, *, system_prompt: str, user_prompt: str) -> LessonEvaluation: ...


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts).strip()
    return ""


class GeminiModelProvider:
    """LangChain Gemini integration with native structured evaluator output."""

    def __init__(self, settings: Settings) -> None:
        settings.validate_for_live_run()
        from langchain_google_genai import ChatGoogleGenerativeAI

        common = {
            "model": settings.model_name,
            "api_key": settings.api_key,
            "request_timeout": settings.request_timeout_seconds,
            "retries": settings.provider_max_retries,
        }
        # Gemini 3.6 Flash uses fixed sampling defaults. Omitting temperature keeps
        # the client quiet and lets the model apply its supported configuration.
        self._generator = ChatGoogleGenerativeAI(**common)
        evaluator_model = ChatGoogleGenerativeAI(**common)
        self._structured_evaluator = evaluator_model.with_structured_output(
            schema=LessonEvaluation.model_json_schema(),
            method="json_schema",
        )

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self._generator.invoke(
                [("system", system_prompt), ("human", user_prompt)],
                automatic_function_calling={"disable": True},
            )
            lesson = _extract_text(response.content)
        except Exception as exc:  # provider errors differ by SDK/version
            raise ModelGenerationError(f"Lesson generation failed: {exc}") from exc
        if not lesson:
            raise ModelGenerationError("Lesson generation returned empty content.")
        return lesson

    def evaluate_lesson(self, *, system_prompt: str, user_prompt: str) -> LessonEvaluation:
        try:
            raw = self._structured_evaluator.invoke(
                [("system", system_prompt), ("human", user_prompt)],
                automatic_function_calling={"disable": True},
            )
            if isinstance(raw, LessonEvaluation):
                return raw
            return LessonEvaluation.model_validate(raw)
        except (ValidationError, TypeError, ValueError) as exc:
            raise EvaluatorResponseError(
                f"Evaluator returned malformed structured output: {exc}"
            ) from exc
        except Exception as exc:  # provider errors differ by SDK/version
            raise EvaluatorResponseError(f"Evaluator model call failed: {exc}") from exc


def build_model_provider(settings: Settings) -> ModelProvider:
    """Centralized provider construction for both model responsibilities."""

    return GeminiModelProvider(settings)
