"""Validated domain models for evaluations, audit logs, and run summaries."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now_iso() -> str:
    """Return a sortable UTC timestamp."""

    return datetime.now(UTC).isoformat()


class CriterionName(StrEnum):
    TECHNICAL_ACCURACY = "technical_accuracy"
    BEGINNER_FRIENDLINESS = "beginner_friendliness"
    TEACHES_BY_EXAMPLE = "teaches_by_example"
    JARGON_CLARITY = "jargon_clarity"
    KEY_CONCEPT_COVERAGE = "key_concept_coverage"
    TEACHING_FLOW = "teaching_flow"


class CriterionResult(BaseModel):
    """One hard PASS/FAIL judgment with inspectable justification."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    reason: str = Field(min_length=1)
    evidence: str | None = None
    improvement: str | None = None

    @model_validator(mode="after")
    def failed_result_has_action(self) -> CriterionResult:
        if not self.passed and not (self.improvement and self.improvement.strip()):
            raise ValueError("A failed criterion must include actionable improvement feedback.")
        return self


class LessonEvaluation(BaseModel):
    """The complete structured judgment returned by the semantic evaluator."""

    model_config = ConfigDict(extra="forbid")

    technical_accuracy: CriterionResult
    beginner_friendliness: CriterionResult
    teaches_by_example: CriterionResult
    jargon_clarity: CriterionResult
    key_concept_coverage: CriterionResult
    teaching_flow: CriterionResult

    def iter_criteria(self) -> Iterator[tuple[CriterionName, CriterionResult]]:
        for name in CriterionName:
            yield name, getattr(self, name.value)

    @property
    def overall_pass(self) -> bool:
        """Application-owned deterministic acceptance; the LLM cannot override this."""

        return all(result.passed for _, result in self.iter_criteria())

    @property
    def failed_criteria(self) -> list[tuple[CriterionName, CriterionResult]]:
        return [(name, result) for name, result in self.iter_criteria() if not result.passed]


class EvaluationAttempt(BaseModel):
    """Immutable-in-output snapshot of one generated lesson and its evaluation."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    attempt: int = Field(ge=1)
    lesson: str
    evaluation: LessonEvaluation
    overall_pass: bool
    rubric_version: str
    evaluated_at: str = Field(default_factory=utc_now_iso)


class RejectionRecord(BaseModel):
    """One criterion failure preserved for debugging and future guidance."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    topic: str
    attempt: int = Field(ge=1)
    criterion: CriterionName
    reason: str
    evidence: str | None = None
    recommended_correction: str
    demo_mode: bool = False
    rejected_at: str = Field(default_factory=utc_now_iso)


FinalStatus = Literal["PASSED", "FAILED_AFTER_MAX_RETRIES"]


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    topic: str
    final_status: FinalStatus
    attempts: int
    retries_used: int
    demo_mode: bool
    rubric_version: str
    memory_guidance: list[str]
    completed_at: str = Field(default_factory=utc_now_iso)
