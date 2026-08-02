"""Package-owned D&D domain primitives (errors only; no kernel imports)."""

from .errors import (
    DndCandidateValidationError,
    DndError,
    DndVocabularyIntegrityError,
)

__all__ = [
    "DndCandidateValidationError",
    "DndError",
    "DndVocabularyIntegrityError",
]
