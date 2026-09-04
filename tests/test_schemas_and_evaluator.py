from __future__ import annotations

import pytest
from pydantic import ValidationError

from lesson_generator.evaluator import LessonEvaluator
from lesson_generator.exceptions import EvaluatorResponseError, ModelGenerationError
from lesson_generator.prompts import EVALUATOR_SYSTEM_PROMPT, LESSON_REQUIREMENTS
from lesson_generator.provider import GeminiModelProvider
from lesson_generator.schemas import CriterionName, CriterionResult, LessonEvaluation

from .helpers import FakeProvider, make_evaluation, substantive_lesson


def test_private_document_claims_have_generation_and_evaluation_guardrails() -> None:
    assert "RAG alone guarantees privacy or security" in LESSON_REQUIREMENTS
    assert "RAG alone guarantees privacy" in EVALUATOR_SYSTEM_PROMPT


def test_pass_and_fail_representation_and_deterministic_aggregation() -> None:
    passing = CriterionResult(passed=True, reason="All checkpoints pass.")
    failing = CriterionResult(
        passed=False,
        reason="Retrieval was described as training.",
        evidence="The lesson says weights change.",
        improvement="State that normal RAG supplies context without changing weights.",
    )
    assert passing.passed is True
    assert failing.passed is False

    evaluation = make_evaluation(CriterionName.TECHNICAL_ACCURACY)
    assert evaluation.overall_pass is False
    assert [name for name, _ in evaluation.failed_criteria] == [CriterionName.TECHNICAL_ACCURACY]
    assert make_evaluation().overall_pass is True


def test_schema_rejects_missing_failure_feedback_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CriterionResult(passed=False, reason="Failed without an action.")

    payload = make_evaluation().model_dump()
    payload["unexpected"] = "not allowed"
    with pytest.raises(ValidationError):
        LessonEvaluation.model_validate(payload)


def test_empty_lesson_fails_without_spending_a_model_call() -> None:
    provider = FakeProvider(evaluations=[make_evaluation()])
    evaluation = LessonEvaluator(provider).evaluate(topic="RAG", lesson="   ")
    assert evaluation.overall_pass is False
    assert provider.evaluation_calls == 0
    assert all(not result.passed for _, result in evaluation.iter_criteria())


def test_short_lesson_gets_deterministic_coverage_failure() -> None:
    provider = FakeProvider(evaluations=[make_evaluation()])
    evaluation = LessonEvaluator(provider).evaluate(topic="RAG", lesson="A short lesson.")
    assert provider.evaluation_calls == 1
    assert evaluation.key_concept_coverage.passed is False
    assert evaluation.overall_pass is False


class _MalformedStructuredModel:
    def __init__(self) -> None:
        self.invoke_kwargs: dict[str, object] = {}

    def invoke(self, _messages: object, **kwargs: object) -> dict[str, object]:
        self.invoke_kwargs = kwargs
        return {"technical_accuracy": {"passed": "definitely"}}


class _EmptyMessage:
    content = ""


class _EmptyGeneratorModel:
    def __init__(self) -> None:
        self.invoke_kwargs: dict[str, object] = {}

    def invoke(self, _messages: object, **kwargs: object) -> _EmptyMessage:
        self.invoke_kwargs = kwargs
        return _EmptyMessage()


class _RateLimitedGeneratorModel:
    def invoke(self, _messages: object, **_kwargs: object) -> _EmptyMessage:
        raise RuntimeError("429 RESOURCE_EXHAUSTED: free_tier_requests limit reached")


def test_malformed_structured_output_has_clear_error() -> None:
    provider = GeminiModelProvider.__new__(GeminiModelProvider)
    structured_model = _MalformedStructuredModel()
    provider._structured_evaluator = structured_model  # type: ignore[attr-defined]
    with pytest.raises(EvaluatorResponseError, match="malformed structured output"):
        provider.evaluate_lesson(system_prompt="system", user_prompt="lesson")
    assert structured_model.invoke_kwargs["automatic_function_calling"] == {"disable": True}


def test_empty_provider_generation_has_clear_error() -> None:
    provider = GeminiModelProvider.__new__(GeminiModelProvider)
    generator_model = _EmptyGeneratorModel()
    provider._generator = generator_model  # type: ignore[attr-defined]
    with pytest.raises(ModelGenerationError, match="empty content"):
        provider.generate_text(system_prompt="system", user_prompt="lesson")
    assert generator_model.invoke_kwargs["automatic_function_calling"] == {"disable": True}


def test_free_tier_quota_error_is_concise_and_never_suggests_paid_fallback() -> None:
    provider = GeminiModelProvider.__new__(GeminiModelProvider)
    provider._generator = _RateLimitedGeneratorModel()  # type: ignore[attr-defined]
    with pytest.raises(ModelGenerationError) as error:
        provider.generate_text(system_prompt="system", user_prompt="lesson")

    message = str(error.value)
    assert "free-tier quota is currently exhausted" in message
    assert "does not fall back to a paid model" in message
    assert "free_tier_requests limit reached" not in message


def test_substantive_lesson_uses_semantic_provider() -> None:
    provider = FakeProvider(evaluations=[make_evaluation()])
    result = LessonEvaluator(provider).evaluate(topic="RAG", lesson=substantive_lesson())
    assert result.overall_pass is True
    assert provider.evaluation_calls == 1
