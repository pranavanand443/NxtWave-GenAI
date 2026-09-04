"""Explicit LangGraph state: no workflow data is hidden in global variables."""

from __future__ import annotations

from typing import TypedDict

from .schemas import EvaluationAttempt, FinalStatus, LessonEvaluation, RejectionRecord


class LessonState(TypedDict):
    run_id: str
    topic: str
    learner_profile: str
    current_lesson: str
    current_evaluation: LessonEvaluation | None
    attempt_number: int
    retry_count: int
    max_retries: int
    evaluation_history: list[EvaluationAttempt]
    rejection_log: list[RejectionRecord]
    revision_feedback: str
    memory_context: list[str]
    final_status: FinalStatus | None
    demo_mode: bool
    artifact_paths: dict[str, str]
    trace: list[str]
