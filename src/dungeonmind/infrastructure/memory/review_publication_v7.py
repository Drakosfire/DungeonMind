"""Explicit V7 writer/replay boundary; legacy publication stays independent."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, TypeAlias

from ...application.publication_admission import (
    admission_source_refs,
    context_for,
    denied,
    require_command_policy,
    verified_profile,
    verify_receipt,
)
from ...application.review_publication import validate_reviewed_identity_publication_preconditions
from ...application.review_publication_v7_proof import (
    make_v7_receipt,
    reprove_v7_delta,
    validate_v7_identity,
    verify_v7_history,
)
from ...application.source_description_correction import (
    SourceDescriptionCorrectionProof,
    verify_source_description_corrections,
)
from ...application.source_provenance_snapshot import SourceProvenanceSnapshot
from ...contracts.contribution_review_v3 import ContributionReviewStateV3
from ...contracts.contribution_review_v4 import ContributionReviewStateV4
from ...contracts.contribution_review_v5 import ContributionReviewStateV5
from ...contracts.graph import PublishRevisionCommand, StoredGraphRevision
from ...contracts.publication_admission import CONTEXT_BYTES, GRAPH_BYTES, bounded_canonical
from ...contracts.review_publication import (
    FinalizedReviewPublicationCommandV3,
    FinalizedReviewPublicationV3,
)
from ...domain.canonical import canonical_sha256
from ...domain.errors import ContributionReviewNotFoundError, PersistenceIntegrityError

if TYPE_CHECKING:
    from .repositories import InMemoryFinalizedReviewPublicationRepository


TypedReviewV7: TypeAlias = (
    ContributionReviewStateV3 | ContributionReviewStateV4 | ContributionReviewStateV5
)


def _review(
    repo: InMemoryFinalizedReviewPublicationRepository,
    world: str,
    review_id: str,
) -> TypedReviewV7:
    state = repo._reviews.get(world, review_id)
    if not isinstance(
        state, (ContributionReviewStateV3, ContributionReviewStateV4, ContributionReviewStateV5)
    ):
        raise ContributionReviewNotFoundError("V7 typed confirmed review missing")
    return state


def _history(
    repo: InMemoryFinalizedReviewPublicationRepository,
    world: str,
) -> list[dict[str, Any]]:
    if repo._identity is None:
        raise PersistenceIntegrityError("V7 identity authority unavailable")
    return [d.model_dump(mode="json") for d in repo._identity.list_for_world(world)]


def _source_refs(state: TypedReviewV7) -> tuple[tuple[str, ...], tuple[str, ...]]:
    artifacts, revisions = admission_source_refs(state)
    guard = getattr(state.record, "reviewed_identity_preconditions", None)
    if guard is not None:
        artifacts = tuple(sorted(set(artifacts) | {s.source_artifact_id for s in guard.sources}))
        revisions = tuple(sorted(set(revisions) | {s.source_revision_id for s in guard.sources}))
    return artifacts, revisions


def _admission_sources(
    state: TypedReviewV7, sources: SourceProvenanceSnapshot
) -> SourceProvenanceSnapshot:
    artifacts, revisions = admission_source_refs(state)
    return SourceProvenanceSnapshot.from_loaded(
        requested_artifact_ids=frozenset(artifacts),
        requested_revision_ids=frozenset(revisions),
        artifacts={k: sources.artifacts[k] for k in artifacts if k in sources.artifacts},
        revisions={k: sources.revisions[k] for k in revisions if k in sources.revisions},
    )


def _correction(
    repo: InMemoryFinalizedReviewPublicationRepository,
    state: TypedReviewV7,
    parent: StoredGraphRevision,
) -> SourceDescriptionCorrectionProof | None:
    return verify_source_description_corrections(
        state,
        parent=parent,
        world_graph=repo._graph,
        reviews=repo._reviews,
        publications=repo,
    )


def reconstruct_v7(
    repo: InMemoryFinalizedReviewPublicationRepository,
    receipt: FinalizedReviewPublicationV3,
) -> FinalizedReviewPublicationV3:
    state = _review(repo, receipt.world_id, receipt.review_id)
    if repo._sources is None:
        raise PersistenceIntegrityError("V7 historical authority unavailable")
    repo._validate_record_review(receipt, state)
    parent = repo._graph.get_revision(receipt.world_id, receipt.expected_parent_revision_id)
    child = repo._graph.get_revision(receipt.world_id, receipt.published_revision_id)
    if parent is None or child is None:
        raise PersistenceIntegrityError("V7 immutable lineage missing")
    repo._validate_parent_revision(
        parent,
        world_id=receipt.world_id,
        parent_revision_id=receipt.expected_parent_revision_id,
        graph_schema=receipt.parent_graph_schema,
        graph_payload_sha256=receipt.parent_graph_payload_sha256,
    )
    revision = child.revision
    if (
        revision.world_id != receipt.world_id
        or revision.revision_id != receipt.published_revision_id
        or revision.parent_revision_id != receipt.expected_parent_revision_id
        or revision.operation_ids != [receipt.operation_id]
        or revision.graph_schema != receipt.graph_schema
        or revision.graph_payload_sha256 != receipt.graph_payload_sha256
        or canonical_sha256(child.graph_payload) != receipt.graph_payload_sha256
        or revision.created_at != receipt.published_at
        or revision.status != "published"
    ):
        raise PersistenceIntegrityError("V7 receipt/immutable revision differs")
    profile = verified_profile(state, parent, child.graph_payload)
    verify_receipt(receipt, state, parent, child, repo._admission.get(profile))
    verify_v7_history(
        receipt,
        state,
        parent,
        child,
        _history(repo, receipt.world_id),
        repo._sources.get_revision,
        repo._v7_graph_reader,
        correction_proof=_correction(repo, state, parent),
    )
    return receipt.model_copy(deep=True)


def publish_v7(
    repo: InMemoryFinalizedReviewPublicationRepository,
    command: FinalizedReviewPublicationCommandV3,
) -> FinalizedReviewPublicationV3:
    # Reject non-JSON raw values before any coercive serialization/reload.
    raw = bounded_canonical(command.graph_payload, max_bytes=GRAPH_BYTES)
    validated = repo._reload_command(command)
    if not isinstance(validated, FinalizedReviewPublicationCommandV3):
        raise PersistenceIntegrityError("V7 command family unavailable")
    if raw != bounded_canonical(validated.graph_payload, max_bytes=GRAPH_BYTES):
        raise PersistenceIntegrityError("V7 raw graph changed on reload")
    if repo._sources is None or repo._identity is None or repo._v7_graph_reader is None:
        raise PersistenceIntegrityError("V7 publication authority unavailable")
    world = validated.world_id
    with repo._graph._lock_for(world), repo._source_lock, repo._identity_lock:
        state = _review(repo, world, validated.review_id)
        if state is None:
            raise ContributionReviewNotFoundError("V7 confirmed review missing")
        repo._validate_review_binding(validated, state)
        parent = repo._graph.get_revision(world, validated.expected_parent_revision_id)
        if parent is None:
            raise PersistenceIntegrityError("V7 parent missing")
        repo._validate_parent_revision(
            parent,
            world_id=world,
            parent_revision_id=validated.expected_parent_revision_id,
            graph_schema=validated.parent_graph_schema,
            graph_payload_sha256=validated.parent_graph_payload_sha256,
        )
        existing = repo._find_matching_unlocked(
            world_id=world,
            review_id=validated.review_id,
            operation_id=validated.operation_id,
            revision_id=validated.expected_published_revision_id,
        )
        if existing is not None:
            verified = repo._reconstruct_unlocked(existing)
            repo._validate_command_record(validated, verified)
            if not isinstance(verified, FinalizedReviewPublicationV3):
                raise PersistenceIntegrityError("V7 replay family differs")
            return verified
        profile = verified_profile(state, parent, validated.graph_payload)
        with repo._admission.transaction(profile):
            policy = repo._admission.get(profile)
            require_command_policy(validated, policy)
            artifacts, revisions = _source_refs(state)
            sources = repo._sources.get_provenance_snapshot(
                artifact_ids=artifacts,
                revision_ids=revisions,
            )
            history = _history(repo, world)
            guard = getattr(state.record, "reviewed_identity_preconditions", None)
            if guard is not None:
                validate_reviewed_identity_publication_preconditions(
                    guard,
                    parent=parent,
                    decisions=repo._identity.list_for_world(world),
                    sources=sources,
                )
            validate_v7_identity(state, parent, history)
            reprove_v7_delta(
                validated,
                state,
                parent,
                sources,
                repo._v7_graph_reader,
                correction_proof=_correction(repo, state, parent),
            )
            context = None
            if policy is not None:
                context, parent_bytes, child_bytes = context_for(
                    state,
                    parent,
                    validated,
                    policy,
                    _admission_sources(state, sources),
                )
                repo._admission_registry.validate(
                    policy,
                    bounded_canonical(context.model_dump(mode="json"), max_bytes=CONTEXT_BYTES),
                    parent_bytes,
                    child_bytes,
                )
            key = (world, validated.expected_published_revision_id)
            if key in repo._graph._revisions:
                denied("admission_raw_revision_adoption_forbidden")
            old_head = deepcopy(repo._graph._heads.get(world))
            stores = (
                (repo._records_by_review, (world, validated.review_id)),
                (repo._records_by_operation, (world, validated.operation_id)),
                (repo._records_by_revision, key),
            )
            old_records = [(store, k, deepcopy(store.get(k))) for store, k in stores]
            try:
                revision = repo._graph._publish_revision_locked(
                    PublishRevisionCommand(
                        world_id=world,
                        parent_revision_id=validated.expected_parent_revision_id,
                        expected_parent_revision_id=validated.expected_parent_revision_id,
                        operation_ids=[validated.operation_id],
                        graph_schema=validated.graph_schema,
                        graph_payload=validated.graph_payload,
                        created_at=validated.requested_published_at,
                    )
                )
                if repo._failure_hook is not None:
                    repo._failure_hook()
                receipt = make_v7_receipt(
                    repo._record_from_revision(validated, revision),
                    validated,
                    sources,
                    history,
                    admission_context=context,
                )
                repo._store_unlocked(receipt)
                if repo._failure_hook is not None:
                    repo._failure_hook()
                reconstructed = repo._reconstruct_unlocked(receipt)
                if not isinstance(reconstructed, FinalizedReviewPublicationV3):
                    raise PersistenceIntegrityError("V7 stored receipt family differs")
                return reconstructed
            except BaseException:
                repo._graph._revisions.pop(key, None)
                if old_head is None:
                    repo._graph._heads.pop(world, None)
                else:
                    repo._graph._heads[world] = old_head
                for store, k, old in old_records:
                    if old is None:
                        store.pop(k, None)
                    else:
                        store[k] = old
                raise
