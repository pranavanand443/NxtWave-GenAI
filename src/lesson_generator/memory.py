"""SQLite-backed, bounded cross-run learning from observed failures."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from .exceptions import PersistenceError
from .schemas import CriterionName, RejectionRecord

GUIDANCE_TEMPLATES: dict[CriterionName, str] = {
    CriterionName.TECHNICAL_ACCURACY: (
        "Verify the query-to-retrieval-to-context-to-answer pipeline, explicitly separate "
        "retrieval from weight updates, and state that RAG cannot guarantee truth."
    ),
    CriterionName.BEGINNER_FRIENDLINESS: (
        "Use short, direct sentences and explain each difficult idea for a learner with no "
        "prior AI background."
    ),
    CriterionName.TEACHES_BY_EXAMPLE: (
        "Carry one concrete scenario through every pipeline step instead of merely naming it."
    ),
    CriterionName.JARGON_CLARITY: (
        "Define each important term in plain language immediately before or when first used."
    ),
    CriterionName.KEY_CONCEPT_COVERAGE: (
        "Check every required pipeline stage, comparison, benefit, and limitation before finishing."
    ),
    CriterionName.TEACHING_FLOW: (
        "Teach motivation first, then definitions, pipeline, example, comparisons, limitations, "
        "and recap."
    ),
}


class MemoryRepository(Protocol):
    def load_guidance(self, *, limit: int = 3) -> list[str]: ...

    def record_failures(self, failures: Sequence[RejectionRecord]) -> None: ...


class SQLiteMemoryRepository:
    """Append-only failure evidence with deterministic, version-controlled adaptation."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS failure_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        attempt INTEGER NOT NULL,
                        criterion TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        evidence TEXT,
                        improvement TEXT NOT NULL,
                        demo_mode INTEGER NOT NULL CHECK (demo_mode IN (0, 1)),
                        rejected_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_failure_patterns
                    ON failure_events(demo_mode, criterion, rejected_at);
                    """
                )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError(f"Could not initialize memory database: {exc}") from exc

    def record_failures(self, failures: Sequence[RejectionRecord]) -> None:
        if not failures:
            return
        rows = [
            (
                item.run_id,
                item.topic,
                item.attempt,
                item.criterion.value,
                item.reason,
                item.evidence,
                item.recommended_correction,
                int(item.demo_mode),
                item.rejected_at,
            )
            for item in failures
        ]
        try:
            with self._connect() as connection:
                connection.executemany(
                    """
                    INSERT INTO failure_events (
                        run_id, topic, attempt, criterion, reason, evidence,
                        improvement, demo_mode, rejected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
        except sqlite3.Error as exc:
            raise PersistenceError(f"Could not persist failure memory: {exc}") from exc

    def load_guidance(self, *, limit: int = 3) -> list[str]:
        """Derive guidance from real-run patterns; artificial demo failures are excluded."""

        try:
            with self._connect() as connection:
                patterns = connection.execute(
                    """
                    SELECT criterion, COUNT(*) AS failure_count, MAX(rejected_at) AS last_seen
                    FROM failure_events
                    WHERE demo_mode = 0
                    GROUP BY criterion
                    ORDER BY failure_count DESC, last_seen DESC, criterion ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                guidance: list[str] = []
                for pattern in patterns:
                    criterion = CriterionName(pattern["criterion"])
                    recent = connection.execute(
                        """
                        SELECT reason FROM failure_events
                        WHERE demo_mode = 0 AND criterion = ?
                        ORDER BY rejected_at DESC, id DESC LIMIT 1
                        """,
                        (criterion.value,),
                    ).fetchone()
                    recent_reason = recent["reason"] if recent else "No recent reason recorded."
                    guidance.append(
                        f"Observed {pattern['failure_count']} {criterion.value} failure(s). "
                        f"Most recent issue: {recent_reason[:240]} "
                        f"Guidance: {GUIDANCE_TEMPLATES[criterion]}"
                    )
                return guidance
        except (sqlite3.Error, ValueError) as exc:
            raise PersistenceError(f"Could not load persistent memory: {exc}") from exc
