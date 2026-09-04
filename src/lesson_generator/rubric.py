"""Version-controlled hard-pass rubric used by the semantic evaluator."""

from __future__ import annotations

from .schemas import CriterionName

RUBRIC_VERSION = "1.1.0"

RUBRIC: dict[CriterionName, dict[str, str]] = {
    CriterionName.TECHNICAL_ACCURACY: {
        "pass": (
            "No material factual misconception; the core query-retrieve-context-generate "
            "pipeline is correct; retrieval is distinguished from training and fine-tuning; "
            "the lesson states that RAG does not guarantee truth or remove hallucinations; and "
            "it does not imply that RAG alone guarantees privacy or secure data handling."
        ),
        "fail": (
            "Claims that retrieval updates model weights, equates embeddings with summaries, "
            "guarantees correct retrieval/truth, treats RAG itself as a privacy or security "
            "guarantee, or materially misstates the RAG pipeline."
        ),
    },
    CriterionName.BEGINNER_FRIENDLINESS: {
        "pass": (
            "Assumes no prior RAG knowledge, uses mostly short and direct sentences, and "
            "explains difficult ideas accessibly for a recent Grade 12 graduate in India."
        ),
        "fail": (
            "Relies on unexplained specialist knowledge, dense academic prose, or unnecessary "
            "mathematics and abstractions."
        ),
    },
    CriterionName.TEACHES_BY_EXAMPLE: {
        "pass": (
            "Uses at least one concrete, intuitive, end-to-end example that shows how a query, "
            "retrieval, context, and answer connect."
        ),
        "fail": "Only names an example or analogy without using it to explain the mechanism.",
    },
    CriterionName.JARGON_CLARITY: {
        "pass": (
            "Defines or immediately explains LLM, retrieval, chunks, embeddings, context, and "
            "vector/similarity search before relying on them."
        ),
        "fail": "Uses important technical terms as if a complete beginner already knows them.",
    },
    CriterionName.KEY_CONCEPT_COVERAGE: {
        "pass": (
            "Covers why internal model knowledge can be insufficient; external documents; "
            "preparation/chunking; intuitive embeddings and search; query, retrieval, supplied "
            "context, and answer generation; retrieval versus training/fine-tuning; benefits; "
            "and all four limits: bad retrieval, flawed sources, missed information, and "
            "remaining hallucination/no truth guarantee."
        ),
        "fail": "Omits or materially under-explains any required beginner concept or limitation.",
    },
    CriterionName.TEACHING_FLOW: {
        "pass": (
            "Moves in a sensible sequence from motivation and definitions to the pipeline, an "
            "example, comparisons, and limitations; later ideas do not depend on unexplained ones."
        ),
        "fail": "Is fragmented, repetitive, or introduces dependent concepts out of order.",
    },
}
