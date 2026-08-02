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


class DndContributionPlanningError(DndError):
    """Contribution planning inputs or environment cannot be trusted.

    Integrity failures (malformed packets, payload hash mismatch, unsupported
    graph schema, world/profile mismatch, deterministic-ID collision,
    planner invariant failure) raise this error and produce no plan. Valid
    inputs that merely require human review surface as plan blockers instead.
    Details identify packet/candidate/relationship/object IDs, qualified
    terms, schema/profile/vocabulary IDs, digests, and exception type names —
    never labels, aliases, summaries, source prose, evidence locators, graph
    prose, raw payloads, filesystem paths, or chained parser exceptions.
    """

    code = "dnd_contribution_planning_error"
