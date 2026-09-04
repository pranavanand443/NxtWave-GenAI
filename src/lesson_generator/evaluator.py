"""Semantic evaluation plus narrow deterministic validity checks."""

from __future__ import annotations

from .prompts import build_evaluator_prompts
from .provider import ModelProvider
from .schemas import CriterionResult, LessonEvaluation

MINIMUM_SUBSTANTIVE_CHARACTERS = 500


def _empty_lesson_evaluation() -> LessonEvaluation:
    result = CriterionResult(
        passed=False,
        reason="The lesson is empty, so its educational quality cannot be evaluated.",
        evidence="No lesson content was provided.",
        improvement="Generate a complete standalone lesson before evaluation.",
    )
    return LessonEvaluation(
        technical_accuracy=result,
        beginner_friendliness=result,
        teaches_by_example=result,
        jargon_clarity=result,
        key_concept_coverage=result,
        teaching_flow=result,
    )


class LessonEvaluator:
    """Apply the real semantic judge; deterministic checks cover objective invalidity only."""

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    def evaluate(self, *, topic: str, lesson: str) -> LessonEvaluation:
        stripped = lesson.strip()
        if not stripped:
            return _empty_lesson_evaluation()

        system_prompt, user_prompt = build_evaluator_prompts(topic=topic, lesson=lesson)
        evaluation = self._provider.evaluate_lesson(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # This is a gross completeness guard, not keyword-based quality scoring. All semantic
        # criteria remain controlled by the independent model judgment.
        if len(stripped) < MINIMUM_SUBSTANTIVE_CHARACTERS:
            short_result = CriterionResult(
                passed=False,
                reason="The lesson is too short to substantively cover the required concepts.",
                evidence=f"The lesson contains only {len(stripped)} characters.",
                improvement=(
                    "Expand it into a complete lesson covering the full pipeline and limits."
                ),
            )
            evaluation = evaluation.model_copy(update={"key_concept_coverage": short_result})
        return evaluation
