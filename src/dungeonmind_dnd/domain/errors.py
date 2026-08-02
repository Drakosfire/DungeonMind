"""Typed failure model for the D&D profile package.

Package-owned and transport-free: usable without FastAPI, a service host,
or any kernel import beyond the narrow allowed contracts. ``code`` is stable
machine-readable vocabulary; ``details`` identifies candidate IDs and term
IDs but never echoes source prose, summaries, or local paths.
"""

from typing import Any


class DndError(Exception):
    """Base for all DungeonMindDnD failures."""

    code = "dnd_error"

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message or self.code)
        self.details = details or {}


class DndVocabularyIntegrityError(DndError):
    """Bundled descriptor/catalog failed validation or pin verification."""

    code = "dnd_vocabulary_integrity_error"


class DndCandidateValidationError(DndError):
    """A candidate packet violated catalog-owned term or pin rules."""

    code = "dnd_candidate_validation_error"
