"""The finite LangGraph generate-evaluate-decide-regenerate workflow."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from .config import MAX_WORKFLOW_RETRIES, Settings
from .evaluator import LessonEvaluator
from .generator import LessonGenerator
from .memory import MemoryRepository, SQLiteMemoryRepository
from .persistence import ArtifactRepository
from .provider import ModelProvider, build_model_provider
from .rubric import RUBRIC_VERSION
from .schemas import EvaluationAttempt, RejectionRecord, RunSummary
from .state import LessonState

DEFAULT_LEARNER_PROFILE = (
    "A recent Grade 12 graduate from India who is beginning AI, may have studied in a "
    "non-English-medium school, and has limited English and technical vocabulary."
)

EventSink = Callable[[str, dict[str, Any]], None]


def _no_events(_event: str, _details: dict[str, Any]) -> None:
    return None


def build_revision_feedback(rejections: list[RejectionRecord]) -> str:
    """Turn evaluator evidence into focused instructions for the next attempt."""

    lines = [
        "Revise the previous draft using every item below. Preserve content that was accurate "
        "and clear; directly correct the cited weaknesses.",
    ]
    for item in rejections:
        evidence = f" Evidence: {item.evidence}" if item.evidence else ""
        lines.append(
            f"- {item.criterion.value}: {item.reason}{evidence} "
            f"Required correction: {item.recommended_correction}"
        )
    return "\n".join(lines)


class LessonWorkflow:
    """Dependency-injected workflow that remains deterministic around model judgments."""

    def __init__(
        self,
        *,
        generator: LessonGenerator,
        evaluator: LessonEvaluator,
        memory: MemoryRepository,
        artifacts: ArtifactRepository,
        max_retries: int = 2,
        event_sink: EventSink | None = None,
    ) -> None:
        if not 0 <= max_retries <= MAX_WORKFLOW_RETRIES:
            raise ValueError(f"max_retries must be between zero and {MAX_WORKFLOW_RETRIES}")
        self._generator = generator
        self._evaluator = evaluator
        self._memory = memory
        self._artifacts = artifacts
        self._max_retries = max_retries
        self._event_sink = event_sink or _no_events
        self.graph = self._build_graph()

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        provider: ModelProvider | None = None,
        event_sink: EventSink | None = None,
    ) -> LessonWorkflow:
        model_provider = provider or build_model_provider(settings)
        return cls(
            generator=LessonGenerator(model_provider),
            evaluator=LessonEvaluator(model_provider),
            memory=SQLiteMemoryRepository(settings.memory_db_path),
            artifacts=ArtifactRepository(settings.output_dir),
            max_retries=settings.workflow_max_retries,
            event_sink=event_sink,
        )

    def _emit(self, event: str, **details: Any) -> None:
        self._event_sink(event, details)

    def _build_graph(self):
        builder = StateGraph(LessonState)
        builder.add_node("load_memory", self.load_memory_node)
        builder.add_node("generate", self.generate_node)
        builder.add_node("evaluate", self.evaluate_node)
        builder.add_node("record_failure", self.record_failure_node)
        builder.add_node("finalize", self.finalize_node)

        builder.add_edge(START, "load_memory")
        builder.add_edge("load_memory", "generate")
        builder.add_edge("generate", "evaluate")
        builder.add_conditional_edges(
            "evaluate",
            self.route_after_evaluation,
            {"pass": "finalize", "fail": "record_failure"},
        )
        builder.add_conditional_edges(
            "record_failure",
            self.route_after_failure,
            {"retry": "generate", "exhausted": "finalize"},
        )
        builder.add_edge("finalize", END)
        return builder.compile()

    def load_memory_node(self, state: LessonState) -> dict[str, Any]:
        guidance = self._memory.load_guidance()
        self._emit("memory_loaded", guidance=guidance)
        return {
            "memory_context": guidance,
            "trace": [*state["trace"], "load_memory"],
        }

    def generate_node(self, state: LessonState) -> dict[str, Any]:
        attempt = state["attempt_number"] + 1
        retry_count = attempt - 1
        self._emit("attempt_started", attempt=attempt, retry_count=retry_count)
        lesson = self._generator.generate(
            topic=state["topic"],
            learner_profile=state["learner_profile"],
            attempt_number=attempt,
            previous_lesson=state["current_lesson"],
            revision_feedback=state["revision_feedback"],
            memory_guidance=state["memory_context"],
            inject_error=state["demo_mode"],
        )
        self._emit("lesson_generated", attempt=attempt, characters=len(lesson))
        return {
            "attempt_number": attempt,
            "retry_count": retry_count,
            "current_lesson": lesson,
            "current_evaluation": None,
            "trace": [*state["trace"], f"generate:{attempt}"],
        }

    def evaluate_node(self, state: LessonState) -> dict[str, Any]:
        self._emit("evaluation_started", attempt=state["attempt_number"])
        evaluation = self._evaluator.evaluate(
            topic=state["topic"],
            lesson=state["current_lesson"],
        )
        attempt = EvaluationAttempt(
            run_id=state["run_id"],
            attempt=state["attempt_number"],
            lesson=state["current_lesson"],
            evaluation=evaluation,
            overall_pass=evaluation.overall_pass,
            rubric_version=RUBRIC_VERSION,
        )
        self._emit(
            "evaluation_completed",
            attempt=state["attempt_number"],
            evaluation=evaluation,
            overall_pass=evaluation.overall_pass,
        )
        return {
            "current_evaluation": evaluation,
            "evaluation_history": [*state["evaluation_history"], attempt],
            "trace": [*state["trace"], f"evaluate:{state['attempt_number']}"],
        }

    @staticmethod
    def route_after_evaluation(state: LessonState) -> Literal["pass", "fail"]:
        evaluation = state["current_evaluation"]
        if evaluation is None:
            raise RuntimeError("Evaluation route reached without an evaluation.")
        return "pass" if evaluation.overall_pass else "fail"

    def record_failure_node(self, state: LessonState) -> dict[str, Any]:
        evaluation = state["current_evaluation"]
        if evaluation is None:
            raise RuntimeError("Failure node reached without an evaluation.")
        new_rejections = [
            RejectionRecord(
                run_id=state["run_id"],
                topic=state["topic"],
                attempt=state["attempt_number"],
                criterion=criterion,
                reason=result.reason,
                evidence=result.evidence,
                recommended_correction=result.improvement
                or "Correct the failed criterion using the rubric.",
                demo_mode=state["demo_mode"],
            )
            for criterion, result in evaluation.failed_criteria
        ]
        self._memory.record_failures(new_rejections)
        feedback = build_revision_feedback(new_rejections)
        retries_remain = state["attempt_number"] <= state["max_retries"]
        self._emit(
            "failure_recorded",
            attempt=state["attempt_number"],
            failures=new_rejections,
            revision_feedback=feedback,
            retries_remain=retries_remain,
        )
        return {
            "rejection_log": [*state["rejection_log"], *new_rejections],
            "revision_feedback": feedback,
            "trace": [*state["trace"], f"record_failure:{state['attempt_number']}"],
        }

    @staticmethod
    def route_after_failure(state: LessonState) -> Literal["retry", "exhausted"]:
        # Attempt 1 can retry when max_retries >= 1; attempt 3 cannot when max_retries == 2.
        return "retry" if state["attempt_number"] <= state["max_retries"] else "exhausted"

    def finalize_node(self, state: LessonState) -> dict[str, Any]:
        evaluation = state["current_evaluation"]
        if evaluation is None:
            raise RuntimeError("Finalize node reached without an evaluation.")
        status = "PASSED" if evaluation.overall_pass else "FAILED_AFTER_MAX_RETRIES"
        summary = RunSummary(
            run_id=state["run_id"],
            topic=state["topic"],
            final_status=status,
            attempts=state["attempt_number"],
            retries_used=state["retry_count"],
            demo_mode=state["demo_mode"],
            rubric_version=RUBRIC_VERSION,
            memory_guidance=state["memory_context"],
        )
        paths = self._artifacts.save_run(
            summary=summary,
            lesson=state["current_lesson"],
            history=state["evaluation_history"],
            rejections=state["rejection_log"],
        )
        self._emit(
            "finalized",
            final_status=status,
            attempts=state["attempt_number"],
            artifact_paths=paths,
        )
        return {
            "final_status": status,
            "artifact_paths": paths,
            "trace": [*state["trace"], "finalize"],
        }

    def run(
        self,
        *,
        topic: str = "Introduction to RAG",
        learner_profile: str = DEFAULT_LEARNER_PROFILE,
        demo_mode: bool = False,
    ) -> LessonState:
        if not topic.strip():
            raise ValueError("topic must not be empty")
        initial: LessonState = {
            "run_id": uuid4().hex,
            "topic": topic.strip(),
            "learner_profile": learner_profile,
            "current_lesson": "",
            "current_evaluation": None,
            "attempt_number": 0,
            "retry_count": 0,
            "max_retries": self._max_retries,
            "evaluation_history": [],
            "rejection_log": [],
            "revision_feedback": "",
            "memory_context": [],
            "final_status": None,
            "demo_mode": demo_mode,
            "artifact_paths": {},
            "trace": [],
        }
        recursion_limit = max(25, 4 * (self._max_retries + 1) + 5)
        return self.graph.invoke(initial, {"recursion_limit": recursion_limit})
