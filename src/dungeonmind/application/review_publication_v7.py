"""Explicit V7 publication entry; legacy receipt ceilings stay closed."""

from __future__ import annotations

from datetime import datetime

from ..contracts.contribution_review_v3 import ContributionReviewStateV3
from ..contracts.contribution_review_v4 import ContributionReviewStateV4
from ..contracts.contribution_review_v5 import ContributionReviewStateV5
from ..contracts.review_publication import (
    FinalizedReviewPublicationCommandV3,
    FinalizedReviewPublicationV3,
    GuardedFinalizedReviewPublicationCommandV3,
)
from ..domain.canonical import canonical_sha256
from ..domain.errors import CapabilityDeniedError, ContributionReviewNotFoundError
from ..domain.revision_ids import compute_revision_id
from .graph_snapshot import GraphSnapshotReader
from .publication_admission import verified_profile
from .repositories import (
    ContributionReviewRepository,
    FinalizedReviewPublicationRepository,
    WorldGraphRepository,
)
from .review_materialization_v6 import review_source_refs_v6
from .review_materialization_v7 import materialize_finalized_review_v7
from .review_publication import _reload_review
from .source_description_correction import verify_source_description_corrections

V3_RECEIPTS = frozenset({"dm_finalized_review_publication_v3"})


def publish_finalized_review_v7(
    world_id: str,
    review_id: str,
    *,
    published_at: datetime,
    review_repository: ContributionReviewRepository,
    world_graph_repository: WorldGraphRepository,
    publication_repository: FinalizedReviewPublicationRepository,
    graph_reader: GraphSnapshotReader,
    allowed_receipt_schemas: frozenset[str] = V3_RECEIPTS,
) -> FinalizedReviewPublicationV3:
    if allowed_receipt_schemas != V3_RECEIPTS:
        raise CapabilityDeniedError("explicit V3 publication receipt transport required")
    existing = publication_repository.get_for_review(world_id, review_id)
    if existing is not None:
        if not isinstance(existing, FinalizedReviewPublicationV3):
            raise CapabilityDeniedError("existing legacy publication cannot be reinterpreted as V7")
        return FinalizedReviewPublicationV3.model_validate(existing.model_dump(mode="json"))
    stored = review_repository.get(world_id, review_id)
    if stored is None:
        raise ContributionReviewNotFoundError("V7 finalized review missing")
    state = (
        ContributionReviewStateV5.model_validate(stored.model_dump(mode="json"))
        if isinstance(stored, ContributionReviewStateV5)
        else _reload_review(stored, world_id=world_id, review_id=review_id)
    )
    if not isinstance(
        state, (ContributionReviewStateV3, ContributionReviewStateV4, ContributionReviewStateV5)
    ):
        raise CapabilityDeniedError("V7 requires typed V3/V4/V5 review")
    if state.record.world_id != world_id or state.record.review_id != review_id:
        raise CapabilityDeniedError("V7 review identity differs")
    record = state.record
    parent = world_graph_repository.get_revision(
        world_id, record.plan_ref.expected_parent_revision_id
    )
    if parent is None:
        raise CapabilityDeniedError("V7 parent missing")
    artifact_ids, revision_ids = review_source_refs_v6(state)
    guard = getattr(record, "reviewed_identity_preconditions", None)
    if guard is not None:
        artifact_ids = tuple(
            sorted(set(artifact_ids) | {s.source_artifact_id for s in guard.sources})
        )
        revision_ids = tuple(
            sorted(set(revision_ids) | {s.source_revision_id for s in guard.sources})
        )
    sources = publication_repository.get_provenance_snapshot(
        artifact_ids=artifact_ids,
        revision_ids=revision_ids,
    )
    if sources is None:
        raise CapabilityDeniedError("V7 source authority unavailable")
    proof = verify_source_description_corrections(
        state,
        parent=parent,
        world_graph=world_graph_repository,
        reviews=review_repository,
        publications=publication_repository,
    )
    result = materialize_finalized_review_v7(
        state,
        parent=parent,
        graph_reader=graph_reader,
        source_snapshot=sources,
        source_description_correction_proof=proof,
    )
    policy_reader = getattr(publication_repository, "get_admission_policy", None)
    if policy_reader is None:
        raise CapabilityDeniedError("V7 profile policy authority unavailable")
    policy = policy_reader(verified_profile(state, parent, result.graph_payload))
    command_type = (
        GuardedFinalizedReviewPublicationCommandV3
        if guard is not None
        else FinalizedReviewPublicationCommandV3
    )
    parent_schema = parent.revision.graph_schema
    if parent_schema not in ("dm_union_graph_v6", "dm_union_graph_v7"):
        raise CapabilityDeniedError("V7 publication requires a V6/V7 parent")
    if result.graph_schema != "dm_union_graph_v7":
        raise CapabilityDeniedError("V7 materialization returned wrong graph schema")
    command = command_type(
        **({"reviewed_identity_preconditions": guard} if guard is not None else {}),
        world_id=world_id,
        review_id=review_id,
        reviewed_contribution_id=record.reviewed_contribution_id,
        reviewed_contribution_sha256=record.reviewed_contribution_sha256,
        review_intent_sha256=record.review_intent_sha256,
        confirmation_id=record.confirmation_id,
        operation_id=record.operation_id,
        expected_parent_revision_id=parent.revision.revision_id,
        parent_graph_payload_sha256=parent.revision.graph_payload_sha256,
        parent_graph_schema=parent_schema,
        graph_schema="dm_union_graph_v7",
        graph_payload=result.graph_payload,
        graph_payload_sha256=canonical_sha256(result.graph_payload),
        expected_published_revision_id=compute_revision_id(
            world_id=world_id,
            parent_revision_id=parent.revision.revision_id,
            operation_ids=[record.operation_id],
            graph_schema="dm_union_graph_v7",
            graph_payload_sha256=result.graph_payload_sha256,
        ),
        admission_policy_ref=policy.reference if policy is not None else None,
        validator_ref=policy.validator_ref if policy is not None else None,
        requested_published_at=published_at,
    )
    try:
        receipt = publication_repository.publish(command)
    except Exception:
        # One exact durable probe, never an automatic write retry.
        receipt = publication_repository.get_for_review(world_id, review_id)
        if receipt is None:
            raise
    if not isinstance(receipt, FinalizedReviewPublicationV3):
        raise CapabilityDeniedError("V7 publication returned wrong receipt family")
    return FinalizedReviewPublicationV3.model_validate(receipt.model_dump(mode="json"))
