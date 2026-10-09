"""Publish one finalized review through the durable publication unit of work.

This module accepts only durable review/world identifiers and performs a
durable-first replay read. On a new operation it delegates payload construction
to B.2f-a and invokes the publication repository once, with one exact recovery
probe only after a thrown attempt.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, NoReturn

from pydantic import ValidationError

from ..contracts.contribution_review import (
    CONTRIBUTION_REVIEW_STATE_SCHEMA,
    ContributionReviewRecord,
    ContributionReviewState,
)
from ..contracts.contribution_review_v2 import (
    CONTRIBUTION_REVIEW_STATE_V2_SCHEMA,
    ContributionReviewRecordV2,
    ContributionReviewStateV2,
    ReviewedIdentityPublicationPreconditionsV1,
)
from ..contracts.graph import StoredGraphRevision
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
    DurableIdentityHistoryRecord,
    FinalizedReviewPublicationRepository,
    WorldGraphRepository,
)
from .review_materialization import (
    FinalizedReviewGraphMaterialization,
    materialize_finalized_review,
)
from .review_materialization_v6 import materialize_finalized_review_v6
from .source_provenance_snapshot import SourceProvenanceSnapshot


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
            reloaded: DurableContributionReviewState = ContributionReviewStateV2.model_validate(
                dumped
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
        or materialization.reviewed_contribution_sha256 != record.reviewed_contribution_sha256
        or materialization.review_intent_sha256 != record.review_intent_sha256
        or materialization.confirmation_id != record.confirmation_id
        or materialization.operation_id != record.operation_id
        or materialization.expected_parent_revision_id != expected_parent_revision_id
        or materialization.parent_graph_payload_sha256 != plan_ref.base_graph_payload_sha256
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
        reloaded = FinalizedReviewPublication.model_validate(publication.model_dump(mode="json"))
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
            f"finalized contribution review {review_id!r} was not found for world {world_id!r}",
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
        from ..contracts.contribution_review_v2 import GuardedContributionReviewRecordV2
        from ..contracts.review_publication import GuardedFinalizedReviewPublicationCommand

        command_type = (
            GuardedFinalizedReviewPublicationCommand
            if isinstance(record, GuardedContributionReviewRecordV2)
            else FinalizedReviewPublicationCommand
        )
        guard_fields = (
            {"reviewed_identity_preconditions": record.reviewed_identity_preconditions}
            if isinstance(record, GuardedContributionReviewRecordV2)
            else {}
        )
        command = command_type(
            **guard_fields,
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
        if isinstance(exc, DungeonMindError) and not isinstance(exc, PersistenceUnavailableError):
            raise
        raise FinalizedReviewPublicationOutcomeUnknownError(
            world_id=world_id,
            review_id=review_id,
            operation_id=record.operation_id,
            expected_published_revision_id=command.expected_published_revision_id,
            reason="publication_attempt_or_recovery_probe_failed",
        ) from None


def validate_reviewed_identity_publication_preconditions(
    guard: ReviewedIdentityPublicationPreconditionsV1,
    *,
    parent: StoredGraphRevision,
    decisions: Sequence[DurableIdentityHistoryRecord],
    sources: SourceProvenanceSnapshot,
) -> None:
    """Owning UoW supplies actual durable authority under its writer fence."""
    from ..contracts.evidence import SourceArtifactV2, SourceStatus
    from ..contracts.identity import IdentityDecisionKind, IdentityDecisionStatus
    from ..domain.errors import PersistenceIntegrityError

    def fail(reason: str) -> None:
        raise PersistenceIntegrityError(
            "reviewed identity publication precondition failed", details={"reason": reason}
        )

    selected = [
        d for d in decisions if d.world_id == guard.world_id and d.decision_id == guard.decision_id
    ]
    if len(selected) != 1:
        fail("selected_decision_missing")
    decision = selected[0]
    if (
        decision.decision_kind != IdentityDecisionKind.HUMAN_OVERRIDE
        or decision.status != IdentityDecisionStatus.ACTIVE
        or len(decision.subject_object_ids) != 1
        or decision.target_object_ids != [guard.target_object_id]
        or canonical_sha256(decision.model_dump(mode="json")) != guard.decision_sha256
    ):
        fail("selected_decision_mismatch")
    if any(
        d.world_id == guard.world_id
        and d.status == IdentityDecisionStatus.ACTIVE
        and guard.decision_id in getattr(d, "supersedes_decision_ids", ())
        for d in decisions
    ):
        fail("selected_decision_superseded")
    superseded_ids = {
        identifier
        for d in decisions
        if d.world_id == guard.world_id and d.status == IdentityDecisionStatus.ACTIVE
        for identifier in getattr(d, "supersedes_decision_ids", ())
    }
    if any(
        d.world_id == guard.world_id
        and d.status == IdentityDecisionStatus.ACTIVE
        and d.decision_kind == IdentityDecisionKind.HUMAN_OVERRIDE
        and d.decision_id != decision.decision_id
        and d.decision_id not in superseded_ids
        and d.subject_object_ids == decision.subject_object_ids
        and d.target_object_ids != decision.target_object_ids
        for d in decisions
    ):
        fail("selected_decision_conflict")
    if any(
        d.world_id == guard.world_id
        and d.status == IdentityDecisionStatus.ACTIVE
        and (
            getattr(d, "source_object_id", None) == guard.target_object_id
            or (
                d.decision_kind in {IdentityDecisionKind.MERGE, IdentityDecisionKind.SPLIT}
                and guard.target_object_id in getattr(d, "subject_object_ids", ())
                and getattr(d, "target_object_ids", ()) != [guard.target_object_id]
            )
        )
        for d in decisions
    ):
        fail("target_identity_redirected")
    if (
        parent.revision.world_id != guard.world_id
        or parent.revision.revision_id != guard.expected_parent_revision_id
    ):
        fail("parent_mismatch")
    objects = [
        o
        for o in parent.graph_payload.get("objects", [])
        if o["object_id"] == guard.target_object_id
    ]
    if len(objects) != 1:
        fail("target_missing")
    obj = objects[0]
    meta = obj.get("assertion_metadata") or {}
    if (
        obj.get("kind") != "dnd5e:npc"
        or meta.get("canon_state") != "canonical"
        or meta.get("campaign_scope") != guard.campaign_id
        or canonical_sha256(obj) != guard.target_object_sha256
    ):
        fail("target_mismatch")
    evidence = {e["evidence_ref_id"]: e for e in parent.graph_payload.get("evidence_refs", [])}
    ids = meta.get("evidence_ref_ids", [])
    if not ids or len(ids) != len(set(ids)) or any(e not in evidence for e in ids):
        fail("existence_evidence_missing")
    refs = [evidence[e] for e in ids]
    if canonical_sha256(refs) != guard.existence_evidence_sha256:
        fail("existence_evidence_mismatch")
    pairs = {(e.get("source_artifact_id"), e.get("source_revision_id")) for e in refs}
    if pairs != {(s.source_artifact_id, s.source_revision_id) for s in guard.sources}:
        fail("source_closure_mismatch")
    for proof in guard.sources:
        artifact = sources.get_artifact(proof.source_artifact_id)
        revision = sources.get_revision(proof.source_revision_id)
        if (
            not isinstance(artifact, SourceArtifactV2)
            or revision is None
            or artifact.status != SourceStatus.ACTIVE
            or artifact.world_id != guard.world_id
            or artifact.campaign_id != guard.campaign_id
            or revision.source_artifact_id != artifact.source_artifact_id
            or canonical_sha256(artifact.model_dump(mode="json")) != proof.source_artifact_sha256
            or canonical_sha256(revision.model_dump(mode="json")) != proof.source_revision_sha256
        ):
            fail("source_mismatch")
        if any(
            e.get("source_artifact_id") == artifact.source_artifact_id
            and (
                e.get("source_domain")
                != (artifact.source_domain.value if artifact.source_domain else None)
                or e.get("source_domain_key") != artifact.source_domain_key
            )
            for e in refs
        ):
            fail("source_domain_mismatch")


def validate_guarded_command_binding(
    command: FinalizedReviewPublicationCommand,
    record: ContributionReviewRecord | ContributionReviewRecordV2,
) -> None:
    """Reject guard replacement, stripping or addition at the owning boundary."""
    from ..domain.errors import IdempotencyConflictError

    if getattr(command, "reviewed_identity_preconditions", None) != getattr(
        record, "reviewed_identity_preconditions", None
    ):
        raise IdempotencyConflictError("publication preconditions disagree with durable review")
