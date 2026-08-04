"""Publish one durable finalized review through the graph repository CAS.

This module is the B.2f-b application boundary.  It accepts only durable
review and world identifiers, performs the exact-parent preflight, delegates
payload construction to B.2f-a, and invokes ``publish_revision`` once as the
sole graph mutation.  It deliberately has no retry, recovery, or transport
surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, NoReturn

from pydantic import ValidationError

from ..contracts.contribution_review import ContributionReviewState
from ..contracts.graph import PublishRevisionCommand, WorldGraphRevision
from ..domain.canonical import canonical_sha256
from ..domain.errors import (
    ContributionReviewNotFoundError,
    HeadNotFoundError,
    PersistenceIntegrityError,
    RevisionNotFoundError,
    StaleParentRevisionError,
)
from ..domain.revision_ids import compute_revision_id
from .graph_snapshot import GraphSnapshotReader
from .repositories import ContributionReviewRepository, WorldGraphRepository
from .review_materialization import (
    GRAPH_SCHEMA_V3,
    FinalizedReviewGraphMaterialization,
    materialize_finalized_review,
)


@dataclass(frozen=True)
class FinalizedReviewPublication:
    """Ephemeral binding returned after one successful graph-head CAS."""

    world_id: str
    review_id: str
    reviewed_contribution_id: str
    review_intent_sha256: str
    confirmation_id: str
    operation_id: str
    expected_parent_revision_id: str
    published_revision_id: str
    graph_schema: str
    graph_payload_sha256: str
    published_at: datetime


def _integrity(reason: str) -> NoReturn:
    raise PersistenceIntegrityError(
        "finalized review publication failed persistence-integrity validation",
        details={"reason": reason},
    ) from None


def _reload_review(
    state: ContributionReviewState,
    *,
    world_id: str,
    review_id: str,
) -> ContributionReviewState:
    try:
        reloaded = ContributionReviewState.model_validate(state.model_dump(mode="json"))
    except Exception:
        _integrity("finalized_review_reload_validation")
    if reloaded.record.world_id != world_id or reloaded.record.review_id != review_id:
        _integrity("finalized_review_identity_mismatch")
    return reloaded


def _validate_materialization(
    materialization: FinalizedReviewGraphMaterialization,
    *,
    state: ContributionReviewState,
    expected_parent_revision_id: str,
) -> dict[str, Any]:
    record = state.record
    plan_ref = record.plan_ref
    try:
        payload = materialization.graph_payload
        payload_digest = canonical_sha256(payload)
    except Exception:
        _integrity("materialization_payload_validation")
    if (
        materialization.world_id != record.world_id
        or materialization.review_id != record.review_id
        or materialization.reviewed_contribution_id != record.reviewed_contribution_id
        or materialization.reviewed_contribution_sha256
        != record.reviewed_contribution_sha256
        or materialization.review_intent_sha256 != record.review_intent_sha256
        or materialization.confirmation_id != record.confirmation_id
        or materialization.operation_id != record.operation_id
        or materialization.expected_parent_revision_id != expected_parent_revision_id
        or materialization.parent_graph_payload_sha256
        != plan_ref.base_graph_payload_sha256
        or materialization.graph_schema != GRAPH_SCHEMA_V3
        or materialization.graph_schema != plan_ref.base_graph_schema
        or payload_digest != materialization.graph_payload_sha256
    ):
        _integrity("materialization_binding_mismatch")
    return payload


def _validate_published_revision(
    revision: WorldGraphRevision,
    *,
    command: PublishRevisionCommand,
    expected_revision_id: str,
    graph_payload_sha256: str,
) -> WorldGraphRevision:
    try:
        returned = WorldGraphRevision.model_validate(revision.model_dump(mode="json"))
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("published_revision_reload_validation")
    if (
        returned.world_id != command.world_id
        or returned.revision_id != expected_revision_id
        or returned.parent_revision_id != command.parent_revision_id
        or returned.created_at != command.created_at
        or returned.operation_ids != command.operation_ids
        or returned.graph_schema != command.graph_schema
        or returned.graph_payload_sha256 != graph_payload_sha256
        or returned.status != "published"
    ):
        _integrity("published_revision_envelope_mismatch")
    return returned


def publish_finalized_review(
    world_id: str,
    review_id: str,
    *,
    published_at: datetime,
    review_repository: ContributionReviewRepository,
    world_graph_repository: WorldGraphRepository,
    graph_reader: GraphSnapshotReader,
) -> FinalizedReviewPublication:
    """Publish one exact durable finalized review as one expected-parent CAS."""
    stored_state = review_repository.get(world_id, review_id)
    if stored_state is None:
        raise ContributionReviewNotFoundError(
            f"finalized contribution review {review_id!r} was not found for world "
            f"{world_id!r}",
            details={"world_id": world_id, "review_id": review_id},
        )
    state = _reload_review(stored_state, world_id=world_id, review_id=review_id)
    record = state.record
    expected_parent_revision_id = record.plan_ref.expected_parent_revision_id

    head = world_graph_repository.get_head(world_id)
    if head is None:
        raise HeadNotFoundError(f"world head {world_id!r} not found")
    if head.head_revision_id != expected_parent_revision_id:
        raise StaleParentRevisionError(
            world_id=world_id,
            expected_parent_revision_id=expected_parent_revision_id,
            actual_head_revision_id=head.head_revision_id,
        )

    parent = world_graph_repository.get_revision(world_id, expected_parent_revision_id)
    if parent is None:
        raise RevisionNotFoundError(
            f"revision {expected_parent_revision_id!r} not found for world {world_id!r}"
        )

    materialization = materialize_finalized_review(
        state,
        parent=parent,
        graph_reader=graph_reader,
    )
    payload = _validate_materialization(
        materialization,
        state=state,
        expected_parent_revision_id=expected_parent_revision_id,
    )
    operation_ids = [record.operation_id]
    try:
        command = PublishRevisionCommand(
            world_id=world_id,
            parent_revision_id=expected_parent_revision_id,
            expected_parent_revision_id=expected_parent_revision_id,
            operation_ids=operation_ids,
            graph_schema=materialization.graph_schema,
            graph_payload=payload,
            created_at=published_at,
        )
    except (TypeError, ValidationError, ValueError):
        _integrity("publication_command_validation")

    graph_payload_sha256 = canonical_sha256(command.graph_payload)
    expected_revision_id = compute_revision_id(
        world_id=command.world_id,
        parent_revision_id=command.parent_revision_id,
        operation_ids=command.operation_ids,
        graph_schema=command.graph_schema,
        graph_payload_sha256=graph_payload_sha256,
    )

    published_revision = world_graph_repository.publish_revision(command)
    returned_revision = _validate_published_revision(
        published_revision,
        command=command,
        expected_revision_id=expected_revision_id,
        graph_payload_sha256=graph_payload_sha256,
    )
    return FinalizedReviewPublication(
        world_id=record.world_id,
        review_id=record.review_id,
        reviewed_contribution_id=record.reviewed_contribution_id,
        review_intent_sha256=record.review_intent_sha256,
        confirmation_id=record.confirmation_id,
        operation_id=record.operation_id,
        expected_parent_revision_id=expected_parent_revision_id,
        published_revision_id=returned_revision.revision_id,
        graph_schema=returned_revision.graph_schema,
        graph_payload_sha256=returned_revision.graph_payload_sha256,
        published_at=returned_revision.created_at,
    )
