"""Lesson generation and isolated demonstration-only error injection."""

from __future__ import annotations

from .prompts import build_generator_prompts
from .provider import ModelProvider

DEMO_MISCONCEPTION = (
    "RAG permanently trains and changes the language model's weights using every "
    "retrieved document before it answers."
)


class LessonGenerator:
    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    def build_prompts(
        self,
        *,
        topic: str,
        learner_profile: str,
        attempt_number: int,
        previous_lesson: str,
        revision_feedback: str,
        memory_guidance: list[str],
    ) -> tuple[str, str]:
        return build_generator_prompts(
            topic=topic,
            learner_profile=learner_profile,
            attempt_number=attempt_number,
            previous_lesson=previous_lesson,
            revision_feedback=revision_feedback,
            memory_guidance=memory_guidance,
        )

    def generate(
        self,
        *,
        topic: str,
        learner_profile: str,
        attempt_number: int,
        previous_lesson: str,
        revision_feedback: str,
        memory_guidance: list[str],
        inject_error: bool,
    ) -> str:
        system_prompt, user_prompt = self.build_prompts(
            topic=topic,
            learner_profile=learner_profile,
            attempt_number=attempt_number,
            previous_lesson=previous_lesson,
            revision_feedback=revision_feedback,
            memory_guidance=memory_guidance,
        )
        lesson = self._provider.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if inject_error and attempt_number == 1:
            # Injection changes content only. No demo flag or forced result reaches evaluation.
            lesson = f"{lesson.rstrip()}\n\n## What happens to the model\n\n{DEMO_MISCONCEPTION}\n"
        return lesson
