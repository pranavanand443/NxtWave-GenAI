from __future__ import annotations

import json
from pathlib import Path

from lesson_generator.evaluator import LessonEvaluator
from lesson_generator.generator import DEMO_MISCONCEPTION, LessonGenerator
from lesson_generator.graph import LessonWorkflow
from lesson_generator.memory import SQLiteMemoryRepository
from lesson_generator.persistence import ArtifactRepository
from lesson_generator.schemas import CriterionName, RejectionRecord

from .helpers import FakeProvider, make_evaluation, substantive_lesson


def workflow_for(
    tmp_path: Path,
    provider: FakeProvider,
    *,
    max_retries: int = 2,
    memory: SQLiteMemoryRepository | None = None,
) -> LessonWorkflow:
    return LessonWorkflow(
        generator=LessonGenerator(provider),
        evaluator=LessonEvaluator(provider),
        memory=memory or SQLiteMemoryRepository(tmp_path / "memory.sqlite3"),
        artifacts=ArtifactRepository(tmp_path / "outputs"),
        max_retries=max_retries,
    )


def test_first_attempt_pass_finalizes_and_saves_all_artifacts(tmp_path: Path) -> None:
    provider = FakeProvider(evaluations=[make_evaluation()])
    state = workflow_for(tmp_path, provider).run()

    assert state["final_status"] == "PASSED"
    assert state["attempt_number"] == 1
    assert state["retry_count"] == 0
    assert len(state["evaluation_history"]) == 1
    assert state["rejection_log"] == []
    assert state["trace"] == ["load_memory", "generate:1", "evaluate:1", "finalize"]
    for path in state["artifact_paths"].values():
        assert Path(path).exists()


def test_failed_feedback_reaches_regeneration_and_history_is_preserved(tmp_path: Path) -> None:
    reason = "The draft incorrectly says retrieval changes trained weights."
    provider = FakeProvider(
        evaluations=[
            make_evaluation(CriterionName.TECHNICAL_ACCURACY, reason=reason),
            make_evaluation(),
        ],
        lessons=[substantive_lesson("first"), substantive_lesson("corrected")],
    )
    state = workflow_for(tmp_path, provider).run()

    assert state["final_status"] == "PASSED"
    assert state["attempt_number"] == 2
    assert state["retry_count"] == 1
    assert len(state["evaluation_history"]) == 2
    assert len(state["rejection_log"]) == 1
    assert reason in provider.generate_prompts[1]
    assert "Improve technical_accuracy explicitly" in provider.generate_prompts[1]
    assert substantive_lesson("first") in provider.generate_prompts[1]

    history = json.loads(Path(state["artifact_paths"]["evaluation_history"]).read_text("utf-8"))
    rejections = json.loads(Path(state["artifact_paths"]["rejection_log"]).read_text("utf-8"))
    assert [item["attempt"] for item in history] == [1, 2]
    assert rejections[0]["criterion"] == "technical_accuracy"


def test_workflow_always_stops_after_two_retries(tmp_path: Path) -> None:
    failed = make_evaluation(CriterionName.TEACHING_FLOW)
    provider = FakeProvider(evaluations=[failed, failed, failed])
    state = workflow_for(tmp_path, provider).run()

    assert state["final_status"] == "FAILED_AFTER_MAX_RETRIES"
    assert state["attempt_number"] == 3
    assert state["retry_count"] == 2
    assert provider.generation_calls == 3
    assert provider.evaluation_calls == 3
    assert len(state["evaluation_history"]) == 3
    assert len(state["rejection_log"]) == 3
    assert state["trace"][-1] == "finalize"
    final = Path(state["artifact_paths"]["final_lesson"]).read_text("utf-8")
    assert "FINAL STATUS: FAILED_AFTER_MAX_RETRIES" in final


def test_deliberate_error_is_content_only_and_uses_same_evaluator_path(tmp_path: Path) -> None:
    def semantic_judge(evaluator_prompt: str):
        if DEMO_MISCONCEPTION in evaluator_prompt:
            return make_evaluation(
                CriterionName.TECHNICAL_ACCURACY,
                reason="The lesson falsely says RAG changes model weights.",
            )
        return make_evaluation()

    provider = FakeProvider(evaluator=semantic_judge)
    memory = SQLiteMemoryRepository(tmp_path / "memory.sqlite3")
    state = workflow_for(tmp_path, provider, memory=memory).run(demo_mode=True)

    assert state["final_status"] == "PASSED"
    assert state["attempt_number"] == 2
    assert provider.evaluation_calls == 2
    assert DEMO_MISCONCEPTION in provider.evaluate_prompts[0]
    assert DEMO_MISCONCEPTION not in provider.evaluate_prompts[1]
    assert all(item.demo_mode for item in state["rejection_log"])
    # The artificial failure is auditable in SQLite but excluded from future adaptation.
    assert memory.load_guidance() == []


def test_persistent_memory_guidance_influences_generation_prompt(tmp_path: Path) -> None:
    memory = SQLiteMemoryRepository(tmp_path / "memory.sqlite3")
    memory.record_failures(
        [
            RejectionRecord(
                run_id="older-run",
                topic="RAG",
                attempt=1,
                criterion=CriterionName.JARGON_CLARITY,
                reason="Embeddings appeared before a definition.",
                evidence="Opening paragraph.",
                recommended_correction="Define embeddings first.",
            )
        ]
    )
    provider = FakeProvider(evaluations=[make_evaluation()])
    state = workflow_for(tmp_path, provider, memory=memory).run()

    assert state["memory_context"]
    assert "Observed 1 jargon_clarity failure" in provider.generate_prompts[0]
    assert "Define each important term" in provider.generate_prompts[0]


def test_zero_retry_configuration_terminates_after_initial_failure(tmp_path: Path) -> None:
    failed = make_evaluation(CriterionName.KEY_CONCEPT_COVERAGE)
    provider = FakeProvider(evaluations=[failed])
    state = workflow_for(tmp_path, provider, max_retries=0).run()
    assert state["final_status"] == "FAILED_AFTER_MAX_RETRIES"
    assert state["attempt_number"] == 1
    assert provider.evaluation_calls == 1
