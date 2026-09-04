"""Polished command-line interface and observable state transitions."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .config import Settings
from .exceptions import LessonGeneratorError
from .graph import LessonWorkflow
from .schemas import LessonEvaluation, RejectionRecord

DISPLAY_NAMES = {
    "technical_accuracy": "Technical Accuracy",
    "beginner_friendliness": "Beginner Friendliness",
    "teaches_by_example": "Teaches By Example",
    "jargon_clarity": "Jargon Clarity",
    "key_concept_coverage": "Concept Coverage",
    "teaching_flow": "Teaching Flow",
}


def console_event(event: str, details: dict[str, Any]) -> None:
    if event == "memory_loaded":
        guidance = details["guidance"]
        print(f"Persistent memory loaded: {len(guidance)} guidance item(s).")
        for item in guidance:
            print(f"  - {item}")
    elif event == "attempt_started":
        print("\n" + "=" * 56)
        print(f"ATTEMPT {details['attempt']}")
        print("=" * 56)
        if details["retry_count"]:
            print(f"Retry {details['retry_count']} started with evaluator feedback.")
    elif event == "lesson_generated":
        print(f"Lesson generated ({details['characters']} characters).")
    elif event == "evaluation_started":
        print("Evaluating with the independent structured evaluator...")
    elif event == "evaluation_completed":
        evaluation: LessonEvaluation = details["evaluation"]
        for criterion, result in evaluation.iter_criteria():
            verdict = "PASS" if result.passed else "FAIL"
            print(f"{DISPLAY_NAMES[criterion.value]:28} {verdict}")
        print(f"\nOVERALL: {'PASS' if details['overall_pass'] else 'FAIL'}")
        for criterion, result in evaluation.failed_criteria:
            print(f"\n{DISPLAY_NAMES[criterion.value]}: {result.reason}")
            if result.evidence:
                print(f"Evidence: {result.evidence}")
            if result.improvement:
                print(f"Correction: {result.improvement}")
    elif event == "failure_recorded":
        failures: list[RejectionRecord] = details["failures"]
        print(f"\nRecorded {len(failures)} rejection(s) and built focused feedback.")
        if details["retries_remain"]:
            print("Regenerating with evaluator feedback...")
        else:
            print("Retry budget exhausted; finalizing without false approval.")
    elif event == "finalized":
        print("\n" + "=" * 56)
        print(f"FINAL STATUS: {details['final_status']}")
        print(f"Attempts: {details['attempts']}")
        print("Saved artifacts:")
        for name, path in details["artifact_paths"].items():
            print(f"  {name}: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate, evaluate, and revise a beginner lesson with LangGraph."
    )
    parser.add_argument(
        "--topic",
        default="Introduction to RAG",
        help='Lesson topic (default: "Introduction to RAG").',
    )
    parser.add_argument(
        "--inject-error",
        action="store_true",
        help="Demo only: inject one misconception into attempt 1 for the real evaluator.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the artifact directory (default: outputs).",
    )
    parser.add_argument(
        "--memory-db",
        type=Path,
        default=None,
        help="Override the SQLite memory path (default: data/lesson_memory.sqlite3).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print("Self-Evaluating Lesson Content Generator")
    print(f"Topic: {args.topic}")
    print(f"Mode: {'DELIBERATE-ERROR DEMO' if args.inject_error else 'NORMAL'}")
    try:
        settings = Settings.from_env(
            output_dir=args.output_dir,
            memory_db_path=args.memory_db,
        )
        settings.validate_for_live_run()
        workflow = LessonWorkflow.from_settings(settings, event_sink=console_event)
        state = workflow.run(topic=args.topic, demo_mode=args.inject_error)
        return 0 if state["final_status"] == "PASSED" else 3
    except LessonGeneratorError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, ValueError) as exc:
        print(f"\nERROR: Workflow could not complete: {exc}", file=sys.stderr)
        return 1
