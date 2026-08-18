"""Publish one finalized review through the durable publication unit of work.

This module accepts only durable review/world identifiers and performs a
durable-first replay read. On a new operation it delegates payload construction
to B.2f-a and invokes the publication repository once, with one exact recovery
probe only after a thrown attempt.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, NoReturn

from pydantic import ValidationError

from ..contracts.contribution_review import (
    CONTRIBUTION_REVIEW_STATE_SCHEMA,
    ContributionReviewState,
)
from ..contracts.contribution_review_v2 import (
    CONTRIBUTION_REVIEW_STATE_V2_SCHEMA,
    ContributionReviewStateV2,
)
from ..contracts.review_publication import (
    FinalizedReviewPublication,
    FinalizedReviewPublicationCommand,
)
from ..domain.canonical import canonical_sha256
from ..domain.errors import (
    ContributionReviewNotFoundError,
    DungeonMindError,
    FinalizedReviewPublicationOutcomeUnknownError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    RevisionNotFoundError,
)
from ..domain.revision_ids import compute_revision_id
from .graph_snapshot import GraphSnapshotReader
from .repositories import (
    ContributionReviewRepository,
    DurableContributionReviewState,
    FinalizedReviewPublicationRepository,
    WorldGraphRepository,
)
from .review_materialization import (
    FinalizedReviewGraphMaterialization,
    materialize_finalized_review,
)
from .review_materialization_v6 import materialize_finalized_review_v6


def _integrity(reason: str) -> NoReturn:
    raise PersistenceIntegrityError(
        "finalized review publication failed persistence-integrity validation",
        details={"reason": reason},
    ) from None


def _reload_review(
    state: DurableContributionReviewState,
    *,
    world_id: str,
    review_id: str,
) -> DurableContributionReviewState:
    try:
        dumped = state.model_dump(mode="json")
        schema_version = dumped.get("schema_version")
        if schema_version == CONTRIBUTION_REVIEW_STATE_V2_SCHEMA:
            reloaded: DurableContributionReviewState = (
                ContributionReviewStateV2.model_validate(dumped)
            )
        elif schema_version == CONTRIBUTION_REVIEW_STATE_SCHEMA:
            reloaded = ContributionReviewState.model_validate(dumped)
        else:
            _integrity("finalized_review_reload_validation")
    except Exception:
        _integrity("finalized_review_reload_validation")
    if reloaded.record.world_id != world_id or reloaded.record.review_id != review_id:
        _integrity("finalized_review_identity_mismatch")
    return reloaded


def _validate_materialization(
    materialization: FinalizedReviewGraphMaterialization,
    *,
    state: DurableContributionReviewState,
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
        or materialization.graph_schema != plan_ref.base_graph_schema
        or payload_digest != materialization.graph_payload_sha256
    ):
        _integrity("materialization_binding_mismatch")
    return payload


def _reload_publication(
    publication: FinalizedReviewPublication,
    *,
    world_id: str,
    review_id: str,
) -> FinalizedReviewPublication:
    try:
        reloaded = FinalizedReviewPublication.model_validate(
            publication.model_dump(mode="json")
        )
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("publication_record_reload_validation")
    if reloaded.world_id != world_id or reloaded.review_id != review_id:
        _integrity("publication_record_identity_mismatch")
    return reloaded


def publish_finalized_review(
    world_id: str,
    review_id: str,
    *,
    published_at: datetime,
    review_repository: ContributionReviewRepository,
    world_graph_repository: WorldGraphRepository,
    publication_repository: FinalizedReviewPublicationRepository,
    graph_reader: GraphSnapshotReader,
) -> FinalizedReviewPublication:
    """Publish or exactly replay one durable finalized review."""
    existing = publication_repository.get_for_review(world_id, review_id)
    if existing is not None:
        return _reload_publication(existing, world_id=world_id, review_id=review_id)

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

    parent = world_graph_repository.get_revision(world_id, expected_parent_revision_id)
    if parent is None:
        raise RevisionNotFoundError(
            f"revision {expected_parent_revision_id!r} not found for world {world_id!r}"
        )

    if isinstance(state, ContributionReviewStateV2):
        materialization = materialize_finalized_review_v6(
            state,
            parent=parent,
            graph_reader=graph_reader,
        )
    else:
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
    graph_payload_sha256 = canonical_sha256(payload)
    expected_revision_id = compute_revision_id(
        world_id=world_id,
        parent_revision_id=expected_parent_revision_id,
        operation_ids=[record.operation_id],
        graph_schema=materialization.graph_schema,
        graph_payload_sha256=graph_payload_sha256,
    )
    try:
        command = FinalizedReviewPublicationCommand(
            world_id=world_id,
            review_id=record.review_id,
            reviewed_contribution_id=record.reviewed_contribution_id,
            reviewed_contribution_sha256=record.reviewed_contribution_sha256,
            review_intent_sha256=record.review_intent_sha256,
            confirmation_id=record.confirmation_id,
            operation_id=record.operation_id,
            expected_parent_revision_id=expected_parent_revision_id,
            parent_graph_payload_sha256=record.plan_ref.base_graph_payload_sha256,
            expected_published_revision_id=expected_revision_id,
            graph_schema=materialization.graph_schema,
            graph_payload=payload,
            graph_payload_sha256=graph_payload_sha256,
            requested_published_at=published_at,
        )
    except (TypeError, ValidationError, ValueError):
        _integrity("publication_command_validation")

    try:
        publication = publication_repository.publish(command)
        return _reload_publication(
            publication,
            world_id=world_id,
            review_id=review_id,
        )
    except Exception as exc:
        try:
            recovered = publication_repository.get_for_review(world_id, review_id)
            if recovered is not None:
                return _reload_publication(
                    recovered,
                    world_id=world_id,
                    review_id=review_id,
                )
        except Exception:
            pass
        if isinstance(exc, DungeonMindError) and not isinstance(
            exc, PersistenceUnavailableError
        ):
            raise
        raise FinalizedReviewPublicationOutcomeUnknownError(
            world_id=world_id,
            review_id=review_id,
            operation_id=record.operation_id,
            expected_published_revision_id=command.expected_published_revision_id,
            reason="publication_attempt_or_recovery_probe_failed",
        ) from None
