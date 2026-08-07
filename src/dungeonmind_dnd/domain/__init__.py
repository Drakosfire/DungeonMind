"""Package-owned D&D domain primitives (errors only; no kernel imports)."""

from .errors import (
    DndCandidateValidationError,
    DndContributionPlanningError,
    DndError,
    DndThreatMechanicsHydrationError,
    DndVocabularyIntegrityError,
    DndWorldObjectMechanicsHydrationError,
)

__all__ = [
    "DndCandidateValidationError",
    "DndContributionPlanningError",
    "DndError",
    "DndThreatMechanicsHydrationError",
    "DndVocabularyIntegrityError",
    "DndWorldObjectMechanicsHydrationError",
]
