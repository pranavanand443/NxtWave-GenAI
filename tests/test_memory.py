from __future__ import annotations

from pathlib import Path

from lesson_generator.memory import SQLiteMemoryRepository
from lesson_generator.schemas import CriterionName, RejectionRecord


def rejection(*, demo_mode: bool = False) -> RejectionRecord:
    return RejectionRecord(
        run_id="run-1",
        topic="Introduction to RAG",
        attempt=1,
        criterion=CriterionName.JARGON_CLARITY,
        reason="Embeddings were used before they were explained.",
        evidence="The first paragraph starts with vector embeddings.",
        recommended_correction="Define embeddings with a simple analogy first.",
        demo_mode=demo_mode,
    )


def test_memory_persists_across_repository_instances(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    SQLiteMemoryRepository(path).record_failures([rejection()])

    guidance = SQLiteMemoryRepository(path).load_guidance()
    assert len(guidance) == 1
    assert "jargon_clarity" in guidance[0]
    assert "Embeddings were used" in guidance[0]
    assert "Define each important term" in guidance[0]


def test_demo_failures_are_audited_but_do_not_bias_future_guidance(tmp_path: Path) -> None:
    repository = SQLiteMemoryRepository(tmp_path / "memory.sqlite3")
    repository.record_failures([rejection(demo_mode=True)])
    assert repository.load_guidance() == []
