"""Pure domain logic: no I/O, no adapters, no framework imports."""

from .canonical import canonical_json, canonical_sha256, sha256_text
from .capability import evaluate_capability, permitted_tool_names
from .errors import (
    CapabilityDeniedError,
    ContributionMaterializationError,
    ContributionReviewAlreadyFinalizedError,
    ContributionReviewValidationError,
    DocumentNotFoundError,
    DungeonMindError,
    HeadNotFoundError,
    IdempotencyConflictError,
    ImmutableRevisionConflictError,
    InvalidLifecycleTransitionError,
    RevisionNotFoundError,
    ScopeResolutionError,
    StaleParentRevisionError,
    ThreadContextMismatchError,
)
from .fusion import reciprocal_rank_fusion, weighted_minmax_fusion
from .revision_ids import compute_revision_id

__all__ = [
    "CapabilityDeniedError",
    "ContributionMaterializationError",
    "ContributionReviewAlreadyFinalizedError",
    "ContributionReviewValidationError",
    "DocumentNotFoundError",
    "DungeonMindError",
    "HeadNotFoundError",
    "IdempotencyConflictError",
    "ImmutableRevisionConflictError",
    "InvalidLifecycleTransitionError",
    "RevisionNotFoundError",
    "ScopeResolutionError",
    "StaleParentRevisionError",
    "ThreadContextMismatchError",
    "canonical_json",
    "canonical_sha256",
    "compute_revision_id",
    "evaluate_capability",
    "permitted_tool_names",
    "reciprocal_rank_fusion",
    "sha256_text",
    "weighted_minmax_fusion",
]
