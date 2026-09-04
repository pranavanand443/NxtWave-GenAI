from __future__ import annotations

from lesson_generator.graph import LessonWorkflow
from lesson_generator.schemas import CriterionName, LessonEvaluation
from lesson_generator.state import LessonState

from .helpers import make_evaluation


def state_for(evaluation: LessonEvaluation, *, attempt: int, max_retries: int = 2) -> LessonState:
    return {
        "run_id": "run",
        "topic": "RAG",
        "learner_profile": "beginner",
        "current_lesson": "lesson",
        "current_evaluation": evaluation,
        "attempt_number": attempt,
        "retry_count": max(0, attempt - 1),
        "max_retries": max_retries,
        "evaluation_history": [],
        "rejection_log": [],
        "revision_feedback": "",
        "memory_context": [],
        "final_status": None,
        "demo_mode": False,
        "artifact_paths": {},
        "trace": [],
    }


def test_pass_and_fail_routes_are_deterministic() -> None:
    assert LessonWorkflow.route_after_evaluation(state_for(make_evaluation(), attempt=1)) == "pass"
    failed = make_evaluation(CriterionName.TECHNICAL_ACCURACY)
    assert LessonWorkflow.route_after_evaluation(state_for(failed, attempt=1)) == "fail"


def test_retry_boundary_has_no_off_by_one_error() -> None:
    failed = make_evaluation()
    assert LessonWorkflow.route_after_failure(state_for(failed, attempt=1)) == "retry"
    assert LessonWorkflow.route_after_failure(state_for(failed, attempt=2)) == "retry"
    assert LessonWorkflow.route_after_failure(state_for(failed, attempt=3)) == "exhausted"
