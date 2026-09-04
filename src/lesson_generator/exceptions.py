"""Application-specific exceptions with user-facing failure boundaries."""


class LessonGeneratorError(Exception):
    """Base class for expected application errors."""


class ConfigurationError(LessonGeneratorError):
    """Raised when required live-model configuration is missing or invalid."""


class ModelGenerationError(LessonGeneratorError):
    """Raised when the model cannot produce usable lesson text."""


class EvaluatorResponseError(LessonGeneratorError):
    """Raised when the evaluator call fails or violates its output schema."""


class PersistenceError(LessonGeneratorError):
    """Raised when run artifacts or persistent memory cannot be stored."""
