"""Package-owned D&D domain primitives (errors only; no kernel imports)."""

from .errors import (
    DndCandidateValidationError,
    DndContributionPlanningError,
    DndError,
    DndVocabularyIntegrityError,
)

__all__ = [
    "DndCandidateValidationError",
    "DndContributionPlanningError",
    "DndError",
    "DndVocabularyIntegrityError",
]
