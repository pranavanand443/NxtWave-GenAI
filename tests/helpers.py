from __future__ import annotations

from collections.abc import Callable

from lesson_generator.schemas import CriterionName, CriterionResult, LessonEvaluation


def substantive_lesson(marker: str = "draft") -> str:
    paragraph = (
        "A learner asks a question. The system searches prepared document chunks, selects "
        "relevant context, and gives that context to a language model before it answers. "
        "Retrieval does not train or change the model weights. Results can still be wrong. "
    )
    return f"# {marker}\n\n" + paragraph * 4


def make_evaluation(
    *failed: CriterionName,
    reason: str = "A required idea needs correction.",
) -> LessonEvaluation:
    failed_set = set(failed)

    def result(name: CriterionName) -> CriterionResult:
        if name in failed_set:
            return CriterionResult(
                passed=False,
                reason=reason,
                evidence=f"Evidence for {name.value}.",
                improvement=f"Improve {name.value} explicitly.",
            )
        return CriterionResult(
            passed=True,
            reason="The criterion meets every hard-pass checkpoint.",
            evidence="Relevant lesson evidence was found.",
        )

    return LessonEvaluation(**{name.value: result(name) for name in CriterionName})


class FakeProvider:
    def __init__(
        self,
        *,
        evaluations: list[LessonEvaluation] | None = None,
        evaluator: Callable[[str], LessonEvaluation] | None = None,
        lessons: list[str] | None = None,
    ) -> None:
        self.evaluations = list(evaluations or [])
        self.evaluator = evaluator
        self.lessons = list(lessons or [substantive_lesson()])
        self.generate_prompts: list[str] = []
        self.evaluate_prompts: list[str] = []

    @property
    def generation_calls(self) -> int:
        return len(self.generate_prompts)

    @property
    def evaluation_calls(self) -> int:
        return len(self.evaluate_prompts)

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        del system_prompt
        self.generate_prompts.append(user_prompt)
        index = min(self.generation_calls - 1, len(self.lessons) - 1)
        return self.lessons[index]

    def evaluate_lesson(self, *, system_prompt: str, user_prompt: str) -> LessonEvaluation:
        del system_prompt
        self.evaluate_prompts.append(user_prompt)
        if self.evaluator:
            return self.evaluator(user_prompt)
        index = min(self.evaluation_calls - 1, len(self.evaluations) - 1)
        return self.evaluations[index]
