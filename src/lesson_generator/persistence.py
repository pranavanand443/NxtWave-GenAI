"""Readable, run-scoped artifacts plus convenient latest-run copies."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from .exceptions import PersistenceError
from .schemas import EvaluationAttempt, RejectionRecord, RunSummary


def _atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise PersistenceError(f"Could not write artifact {path}: {exc}") from exc


def _json_for_models(items: Sequence[BaseModel]) -> str:
    payload = [item.model_dump(mode="json") for item in items]
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


class ArtifactRepository:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def save_run(
        self,
        *,
        summary: RunSummary,
        lesson: str,
        history: Sequence[EvaluationAttempt],
        rejections: Sequence[RejectionRecord],
    ) -> dict[str, str]:
        """Preserve a run forever and atomically refresh stable demo-friendly paths."""

        run_dir = self._output_dir / "runs" / summary.run_id
        lesson_content = (
            "# Final Lesson\n\n"
            f"**FINAL STATUS: {summary.final_status}**\n\n"
            f"**Topic:** {summary.topic}\n\n"
            f"{lesson.strip()}\n"
        )
        files = {
            "final_lesson": lesson_content,
            "evaluation_history": _json_for_models(history),
            "rejection_log": _json_for_models(rejections),
            "run_summary": json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False)
            + "\n",
        }
        names = {
            "final_lesson": "final_lesson.md",
            "evaluation_history": "evaluation_history.json",
            "rejection_log": "rejection_log.json",
            "run_summary": "run_summary.json",
        }
        for key, content in files.items():
            _atomic_write_text(run_dir / names[key], content)
            _atomic_write_text(self._output_dir / names[key], content)

        return {
            key: str((self._output_dir / filename).resolve()) for key, filename in names.items()
        } | {"run_directory": str(run_dir.resolve())}
