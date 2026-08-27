"""In-memory implementations of the application ports.

These adapters exist for unit tests and local development, but they are not
toys: they enforce the same invariants the PostgreSQL adapters must honor —
immutable revisions, atomic head publication with stale-parent rejection,
canonical idempotent appends, deep-copied payloads, thread binding, and
fail-closed scope/visibility filtering. Conformance between this module and
the PostgreSQL adapter is what makes the ports real.
"""

import copy
import math
import threading
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, TypeVar

from ...application.existing_world_adoption import (
    bind_existing_world_adoption_command,
    require_v2_contribution_correction_closure,
    terminal_existing_world_adoption_receipt,
)
from ...application.existing_world_adoption_repair import (
    LoadedAdoptedMembership,
    membership_from_loaded,
    prepare_source_classification_repair,
)
from ...application.graph_snapshot import GRAPH_SCHEMA_V6
from ...application.repositories import (
    DurableContributionReviewState,
    DurableExistingWorldAdoptionCommand,
    DurableExistingWorldAdoptionReceipt,
    DurableGraphContribution,
    DurableIdentityDecision,
    normalize_semantic_document_batch,
)
from ...application.reviewed_world_initialization import (
    FirstWorldMaterialization,
    bind_reviewed_world_initialization_command,
    replay_conflict_if_present,
    reviewed_world_initialization_replay_identity,
    terminal_reviewed_world_initialization_receipt,
)
from ...application.source_provenance_snapshot import SourceProvenanceSnapshot
from ...contracts.contribution import (
    ContributionStatus,
    GraphContribution,
    GraphContributionV2,
)
from ...contracts.contribution_review import (
    ContributionReviewRecord,
    ContributionReviewState,
)
from ...contracts.contribution_review_v2 import (
    ContributionReviewRecordV2,
    ContributionReviewStateV2,
    contribution_v2_payload_sha256,
)
from ...contracts.evidence import SourceArtifactRecord, SourceRevision
from ...contracts.existing_world_adoption import (
    EXISTING_WORLD_ADOPTION_RECEIPT_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA,
    ExistingWorldAdoptionReceiptV1,
    ExistingWorldAdoptionReceiptV2,
    ExistingWorldAdoptionReceiptV3,
    ExistingWorldAdoptionReceiptV4,
)
from ...contracts.existing_world_adoption_repair import (
    ExistingWorldAdoptionSourceClassificationRepairCommandV1,
)
from ...contracts.graph import (
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from ...contracts.mind_turn import MindTurnRequest, MindTurnResponse
from ...contracts.retrieval import GraphRetrievalSession
from ...contracts.review_publication import (
    FinalizedReviewPublication,
    FinalizedReviewPublicationCommand,
)
from ...contracts.reviewed_world_initialization import (
    ReviewedWorldInitializationCommandV1,
    ReviewedWorldInitializationReceiptV1,
)
from ...contracts.semantic import (
    CandidateChannel,
    EmbeddingRun,
    EmbeddingRunStatus,
    SemanticCandidate,
    SemanticDocument,
    SemanticQuery,
)
from ...contracts.vocabulary import Visibility
from ...domain.canonical import canonical_json, canonical_sha256
from ...domain.errors import (
    ContributionReviewAlreadyFinalizedError,
    ContributionReviewNotFoundError,
    DocumentNotFoundError,
    IdempotencyConflictError,
    ImmutableRevisionConflictError,
    InvalidLifecycleTransitionError,
    PersistenceIntegrityError,
    RevisionNotFoundError,
    ScopeResolutionError,
    StaleParentRevisionError,
    ThreadContextMismatchError,
)
from ...domain.revision_ids import compute_revision_id

_EMBEDDING_RUN_IMMUTABLE_FIELDS: set[str] = {
    "run_id",
    "embedding_model",
    "embedding_model_revision",
    "embedding_dimensions",
    "embedding_recipe",
    "corpus_fingerprint",
    "benchmark_projection_id",
    "world_id",
    "created_at",
    "schema_version",
}


def _fingerprint(model: object) -> str:
    """Canonical JSON fingerprint of a pydantic model for idempotency checks."""
    dump = model.model_dump(mode="json")  # type: ignore[attr-defined]
    return canonical_json(dump)


def _v2_adoption_facts(model: object) -> dict[str, Any]:
    """The adoption facts shared by v2/v3 receipts (representation excluded)."""
    return model.model_dump(  # type: ignore[attr-defined]
        mode="json",
        exclude={
            "schema_version",
            "membership_sha256",
            "effective_membership_sha256",
            "membership_manifest",
            "source_classification_repair",
        },
    )


def _immutable_run_fingerprint(run: EmbeddingRun) -> str:
    dump = run.model_dump(mode="json", include=_EMBEDDING_RUN_IMMUTABLE_FIELDS)
    return canonical_json(dump)


T = TypeVar("T")


def _copy(model: T) -> T:
    return model.model_copy(deep=True)  # type: ignore[attr-defined]


class InMemoryWorldGraphRepository:
    """Immutable revisions + one head per world, published by atomic CAS."""

    def __init__(self) -> None:
        self._revisions: dict[tuple[str, str], StoredGraphRevision] = {}
        self._heads: dict[str, WorldGraphHead] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._guard = threading.Lock()

    def _lock_for(self, world_id: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(world_id, threading.RLock())

    def get_head(self, world_id: str) -> WorldGraphHead | None:
        head = self._heads.get(world_id)
        return _copy(head) if head is not None else None

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision | None:
        stored = self._revisions.get((world_id, revision_id))
        return _copy(stored) if stored is not None else None

    def _publish_revision_locked(
        self,
        command: PublishRevisionCommand,
    ) -> WorldGraphRevision:
        # Contract already requires parent == expected; CAS requires expected == head.
        payload_hash = canonical_sha256(command.graph_payload)
        revision_id = compute_revision_id(
            world_id=command.world_id,
            parent_revision_id=command.parent_revision_id,
            operation_ids=command.operation_ids,
            graph_schema=command.graph_schema,
            graph_payload_sha256=payload_hash,
        )
        with self._lock_for(command.world_id):
            current_head = self._heads.get(command.world_id)
            current_head_id = current_head.head_revision_id if current_head else None
            if command.expected_parent_revision_id != current_head_id:
                raise StaleParentRevisionError(
                    world_id=command.world_id,
                    expected_parent_revision_id=command.expected_parent_revision_id,
                    actual_head_revision_id=current_head_id,
                )
            # Defense in depth: declared lineage must also equal current head.
            if command.parent_revision_id != current_head_id:
                raise StaleParentRevisionError(
                    world_id=command.world_id,
                    expected_parent_revision_id=command.parent_revision_id,
                    actual_head_revision_id=current_head_id,
                )
            existing = self._revisions.get((command.world_id, revision_id))
            if existing is not None:
                if existing.revision.graph_payload_sha256 != payload_hash:
                    raise ImmutableRevisionConflictError(
                        f"revision {revision_id!r} already exists with different payload"
                    )
                # Identical replay (e.g. after rollback): CAS already passed, so the
                # head still advances — replay is a publication, not just a read.
                self._heads[command.world_id] = WorldGraphHead(
                    world_id=command.world_id,
                    head_revision_id=revision_id,
                    updated_at=command.created_at,
                )
                return _copy(existing.revision)
            envelope = WorldGraphRevision(
                world_id=command.world_id,
                revision_id=revision_id,
                parent_revision_id=command.parent_revision_id,
                created_at=command.created_at,
                operation_ids=list(command.operation_ids),
                graph_schema=command.graph_schema,
                graph_payload_sha256=payload_hash,
            )
            # Deep canonical copy — caller must not mutate stored "immutable" payload.
            frozen_payload = copy.deepcopy(command.graph_payload)
            self._revisions[(command.world_id, revision_id)] = StoredGraphRevision(
                revision=envelope, graph_payload=frozen_payload
            )
            self._heads[command.world_id] = WorldGraphHead(
                world_id=command.world_id,
                head_revision_id=revision_id,
                updated_at=command.created_at,
            )
            return _copy(envelope)

    def publish_revision(self, command: PublishRevisionCommand) -> WorldGraphRevision:
        with self._lock_for(command.world_id):
            return self._publish_revision_locked(command)

    def rollback_head(
        self, world_id: str, target_revision_id: str, *, updated_at: datetime
    ) -> WorldGraphHead:
        with self._lock_for(world_id):
            if (world_id, target_revision_id) not in self._revisions:
                raise RevisionNotFoundError(
                    f"revision {target_revision_id!r} does not exist for world {world_id!r}"
                )
            head = WorldGraphHead(
                world_id=world_id, head_revision_id=target_revision_id, updated_at=updated_at
            )
            self._heads[world_id] = head
            return _copy(head)


class InMemoryContributionRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], DurableGraphContribution] = {}
        self._finalized_review_ids: set[tuple[str, str]] = set()
        self._lock = threading.RLock()

    def append(self, contribution: DurableGraphContribution) -> DurableGraphContribution:
        key = (contribution.world_id, contribution.contribution_id)
        with self._lock:
            existing = self._items.get(key)
            if existing is not None:
                if _fingerprint(existing) != _fingerprint(contribution):
                    raise IdempotencyConflictError(
                        f"contribution {contribution.contribution_id!r} replayed with "
                        "different payload"
                    )
                return _copy(existing)
            if isinstance(contribution, GraphContributionV2):
                world_id = contribution.world_id
                require_v2_contribution_correction_closure(
                    contribution,
                    resolve_target=lambda target_id: self._items.get((world_id, target_id)),
                )
            self._items[key] = _copy(contribution)
            return _copy(contribution)

    def get(self, world_id: str, contribution_id: str) -> DurableGraphContribution | None:
        with self._lock:
            item = self._items.get((world_id, contribution_id))
            return _copy(item) if item is not None else None

    def list_for_world(
        self, world_id: str, *, status: ContributionStatus | None = None
    ) -> list[DurableGraphContribution]:
        with self._lock:
            items = [c for (w, _), c in self._items.items() if w == world_id]
            if status is not None:
                items = [c for c in items if c.status is status]
            items.sort(key=lambda c: c.contribution_id)
            return [_copy(c) for c in items]

    def update_status(
        self,
        world_id: str,
        contribution_id: str,
        status: ContributionStatus,
        *,
        superseded_by: str | None = None,
    ) -> DurableGraphContribution:
        key = (world_id, contribution_id)
        with self._lock:
            existing = self._items.get(key)
            if existing is None:
                raise DocumentNotFoundError(
                    f"contribution {contribution_id!r} not found in world {world_id!r}"
                )
            if key in self._finalized_review_ids:
                raise InvalidLifecycleTransitionError(
                    record_type="contribution",
                    record_id=contribution_id,
                    current_status=existing.status.value,
                    requested_status=status.value,
                    message=(
                        f"contribution {contribution_id!r} is lifecycle-protected "
                        "by a finalized review"
                    ),
                )
            updated = existing.model_copy(deep=True)
            updated.status = status
            if superseded_by is not None:
                updated.diagnostics = {**updated.diagnostics, "superseded_by": superseded_by}
            self._items[key] = updated
            return _copy(updated)


class InMemoryContributionReviewRepository:
    """Atomic finalized-review store sharing contribution repository state."""

    def __init__(
        self,
        contributions: InMemoryContributionRepository,
        *,
        failure_hook: Callable[[], None] | None = None,
    ) -> None:
        self._contributions = contributions
        self._records: dict[
            tuple[str, str], ContributionReviewRecord | ContributionReviewRecordV2
        ] = {}
        self._lock = contributions._lock
        self._failure_hook = failure_hook

    def _reconstruct_unlocked(
        self, record: ContributionReviewRecord | ContributionReviewRecordV2
    ) -> ContributionReviewState | ContributionReviewStateV2:
        candidate = self._contributions._items.get(
            (record.world_id, record.stored_candidate_contribution_id)
        )
        reviewed = self._contributions._items.get(
            (record.world_id, record.reviewed_contribution_id)
        )
        if candidate is None or reviewed is None:
            raise PersistenceIntegrityError(
                f"review {record.review_id!r} is missing a contribution child"
            )
        try:
            if isinstance(record, ContributionReviewRecordV2):
                if not isinstance(candidate, GraphContributionV2) or not isinstance(
                    reviewed, GraphContributionV2
                ):
                    raise PersistenceIntegrityError(
                        f"review {record.review_id!r} received a non-v2 contribution"
                    )
                return ContributionReviewStateV2(
                    record=_copy(record),
                    candidate_contribution=_copy(candidate),
                    reviewed_contribution=_copy(reviewed),
                )
            if not isinstance(candidate, GraphContribution) or not isinstance(
                reviewed, GraphContribution
            ):
                raise PersistenceIntegrityError(
                    f"review {record.review_id!r} received a non-v1 contribution"
                )
            return ContributionReviewState(
                record=_copy(record),
                candidate_contribution=_copy(candidate),
                reviewed_contribution=_copy(reviewed),
            )
        except PersistenceIntegrityError:
            raise
        except Exception:
            raise PersistenceIntegrityError(
                f"review {record.review_id!r} failed reconstruction"
            ) from None

    def finalize(
        self, state: ContributionReviewState | ContributionReviewStateV2
    ) -> ContributionReviewState | ContributionReviewStateV2:
        try:
            dumped = state.model_dump(mode="json")
            validated: ContributionReviewState | ContributionReviewStateV2 = (
                ContributionReviewStateV2.model_validate(dumped)
                if isinstance(state, ContributionReviewStateV2)
                else ContributionReviewState.model_validate(dumped)
            )
        except Exception:
            raise PersistenceIntegrityError(
                "review state failed validation before persistence"
            ) from None
        record = validated.record
        with self._lock:
            existing = self._records.get((record.world_id, record.review_id))
            if existing is not None:
                current = self._reconstruct_unlocked(existing)
                if _fingerprint(current) == _fingerprint(validated):
                    return current
                raise IdempotencyConflictError(
                    f"review {record.review_id!r} replayed with different payload"
                )
            for prior in self._records.values():
                if prior.world_id == record.world_id and prior.operation_id == record.operation_id:
                    raise IdempotencyConflictError(
                        f"operation {record.operation_id!r} replayed with different payload"
                    )
                if (
                    prior.world_id == record.world_id
                    and prior.plan_ref.source_plan_id == record.plan_ref.source_plan_id
                ):
                    raise ContributionReviewAlreadyFinalizedError(
                        f"source plan {record.plan_ref.source_plan_id!r} is already finalized"
                    )
            candidate_key = (record.world_id, record.stored_candidate_contribution_id)
            reviewed_key = (record.world_id, record.reviewed_contribution_id)
            for key, contribution in (
                (candidate_key, validated.candidate_contribution),
                (reviewed_key, validated.reviewed_contribution),
            ):
                existing_contribution = self._contributions._items.get(key)
                if existing_contribution is not None and _fingerprint(
                    existing_contribution
                ) != _fingerprint(contribution):
                    raise IdempotencyConflictError(
                        f"contribution {key[1]!r} conflicts with review payload"
                    )
            inserted_keys: list[tuple[str, str]] = []
            protected_keys: list[tuple[str, str]] = []
            try:
                if candidate_key not in self._contributions._items:
                    self._contributions._items[candidate_key] = _copy(
                        validated.candidate_contribution
                    )
                    inserted_keys.append(candidate_key)
                if candidate_key not in self._contributions._finalized_review_ids:
                    self._contributions._finalized_review_ids.add(candidate_key)
                    protected_keys.append(candidate_key)
                if self._failure_hook is not None:
                    self._failure_hook()
                if reviewed_key not in self._contributions._items:
                    self._contributions._items[reviewed_key] = _copy(
                        validated.reviewed_contribution
                    )
                    inserted_keys.append(reviewed_key)
                if reviewed_key not in self._contributions._finalized_review_ids:
                    self._contributions._finalized_review_ids.add(reviewed_key)
                    protected_keys.append(reviewed_key)
                self._records[(record.world_id, record.review_id)] = _copy(record)
                return self._reconstruct_unlocked(record)
            except BaseException:
                for key in inserted_keys:
                    self._contributions._items.pop(key, None)
                for key in protected_keys:
                    self._contributions._finalized_review_ids.discard(key)
                self._records.pop((record.world_id, record.review_id), None)
                raise

    def get(
        self, world_id: str, review_id: str
    ) -> ContributionReviewState | ContributionReviewStateV2 | None:
        with self._lock:
            record = self._records.get((world_id, review_id))
            return None if record is None else self._reconstruct_unlocked(record)

    def get_for_plan(
        self, world_id: str, source_plan_id: str
    ) -> ContributionReviewState | ContributionReviewStateV2 | None:
        with self._lock:
            record = next(
                (
                    item
                    for (record_world, _), item in self._records.items()
                    if record_world == world_id and item.plan_ref.source_plan_id == source_plan_id
                ),
                None,
            )
            return None if record is None else self._reconstruct_unlocked(record)


class InMemoryFinalizedReviewPublicationRepository:
    """Atomic in-memory review publication unit of work.

    The graph repository owns the per-world lock and locked graph publication
    helper. Publication records use that same lock, so a revision/head change
    and its terminal identity are one reversible in-memory transaction.
    """

    def __init__(
        self,
        review_repository: InMemoryContributionReviewRepository,
        world_graph_repository: InMemoryWorldGraphRepository,
        *,
        failure_hook: Callable[[], None] | None = None,
    ) -> None:
        self._reviews = review_repository
        self._graph = world_graph_repository
        self._records_by_review: dict[tuple[str, str], FinalizedReviewPublication] = {}
        self._records_by_operation: dict[tuple[str, str], FinalizedReviewPublication] = {}
        self._records_by_revision: dict[tuple[str, str], FinalizedReviewPublication] = {}
        self._failure_hook = failure_hook

    @staticmethod
    def _reload_command(
        command: FinalizedReviewPublicationCommand,
    ) -> FinalizedReviewPublicationCommand:
        try:
            return FinalizedReviewPublicationCommand.model_validate(command.model_dump(mode="json"))
        except Exception:
            raise PersistenceIntegrityError(
                "finalized publication command failed validation"
            ) from None

    @staticmethod
    def _validate_review_binding(
        command: FinalizedReviewPublicationCommand,
        state: DurableContributionReviewState,
    ) -> None:
        record = state.record
        expected = (
            record.world_id,
            record.review_id,
            record.reviewed_contribution_id,
            record.reviewed_contribution_sha256,
            record.review_intent_sha256,
            record.confirmation_id,
            record.operation_id,
            record.plan_ref.expected_parent_revision_id,
            record.plan_ref.base_graph_payload_sha256,
            record.plan_ref.base_graph_schema,
        )
        actual = (
            command.world_id,
            command.review_id,
            command.reviewed_contribution_id,
            command.reviewed_contribution_sha256,
            command.review_intent_sha256,
            command.confirmation_id,
            command.operation_id,
            command.expected_parent_revision_id,
            command.parent_graph_payload_sha256,
            command.graph_schema,
        )
        if actual != expected:
            raise IdempotencyConflictError(
                "finalized publication command disagrees with its durable review"
            )

    @staticmethod
    def _validate_revision(
        stored: StoredGraphRevision,
        *,
        command: FinalizedReviewPublicationCommand,
    ) -> None:
        revision = stored.revision
        if (
            revision.world_id != command.world_id
            or revision.revision_id != command.expected_published_revision_id
            or revision.parent_revision_id != command.expected_parent_revision_id
            or revision.operation_ids != [command.operation_id]
            or revision.graph_schema != command.graph_schema
            or revision.status != "published"
            or canonical_sha256(stored.graph_payload) != command.graph_payload_sha256
            or revision.graph_payload_sha256 != command.graph_payload_sha256
            or stored.graph_payload != command.graph_payload
        ):
            raise PersistenceIntegrityError(
                "finalized publication revision does not match its command"
            )

    @staticmethod
    def _validate_parent_revision(
        stored: StoredGraphRevision,
        *,
        world_id: str,
        parent_revision_id: str,
        graph_schema: str,
        graph_payload_sha256: str,
    ) -> None:
        revision = stored.revision
        if (
            revision.world_id != world_id
            or revision.revision_id != parent_revision_id
            or revision.graph_schema != graph_schema
            or revision.status != "published"
            or revision.graph_payload_sha256 != graph_payload_sha256
            or canonical_sha256(stored.graph_payload) != graph_payload_sha256
        ):
            raise PersistenceIntegrityError(
                "finalized publication parent revision does not match its binding"
            )

    @classmethod
    def _validate_record_review(
        cls,
        publication: FinalizedReviewPublication,
        state: DurableContributionReviewState,
    ) -> None:
        record = state.record
        if (
            publication.world_id != record.world_id
            or publication.review_id != record.review_id
            or publication.reviewed_contribution_id != record.reviewed_contribution_id
            or publication.reviewed_contribution_sha256 != record.reviewed_contribution_sha256
            or publication.review_intent_sha256 != record.review_intent_sha256
            or publication.confirmation_id != record.confirmation_id
            or publication.operation_id != record.operation_id
            or publication.expected_parent_revision_id
            != record.plan_ref.expected_parent_revision_id
            or publication.parent_graph_payload_sha256 != record.plan_ref.base_graph_payload_sha256
            or publication.graph_schema != record.plan_ref.base_graph_schema
        ):
            raise PersistenceIntegrityError(
                "finalized publication record disagrees with its durable review"
            )

    @staticmethod
    def _validate_command_record(
        command: FinalizedReviewPublicationCommand,
        publication: FinalizedReviewPublication,
    ) -> None:
        if (
            publication.world_id != command.world_id
            or publication.review_id != command.review_id
            or publication.reviewed_contribution_id != command.reviewed_contribution_id
            or publication.reviewed_contribution_sha256 != command.reviewed_contribution_sha256
            or publication.review_intent_sha256 != command.review_intent_sha256
            or publication.confirmation_id != command.confirmation_id
            or publication.operation_id != command.operation_id
            or publication.expected_parent_revision_id != command.expected_parent_revision_id
            or publication.parent_graph_payload_sha256 != command.parent_graph_payload_sha256
            or publication.published_revision_id != command.expected_published_revision_id
            or publication.graph_schema != command.graph_schema
            or publication.graph_payload_sha256 != command.graph_payload_sha256
        ):
            raise IdempotencyConflictError(
                "finalized publication identity conflicts with the requested content"
            )

    def _validate_record(
        self,
        publication: FinalizedReviewPublication,
    ) -> FinalizedReviewPublication:
        try:
            return FinalizedReviewPublication.model_validate(publication.model_dump(mode="json"))
        except Exception:
            raise PersistenceIntegrityError(
                "finalized publication record failed reconstruction"
            ) from None

    def _find_matching_unlocked(
        self,
        *,
        world_id: str,
        review_id: str | None = None,
        operation_id: str | None = None,
        revision_id: str | None = None,
    ) -> FinalizedReviewPublication | None:
        matches: dict[str, FinalizedReviewPublication] = {}
        if review_id is not None:
            value = self._records_by_review.get((world_id, review_id))
            if value is not None:
                matches[_fingerprint(value)] = value
        if operation_id is not None:
            value = self._records_by_operation.get((world_id, operation_id))
            if value is not None:
                matches[_fingerprint(value)] = value
        if revision_id is not None:
            value = self._records_by_revision.get((world_id, revision_id))
            if value is not None:
                matches[_fingerprint(value)] = value
        if len(matches) > 1:
            raise PersistenceIntegrityError("multiple finalized publication identities conflict")
        return next(iter(matches.values()), None)

    def _reconstruct_unlocked(
        self,
        publication: FinalizedReviewPublication,
    ) -> FinalizedReviewPublication:
        verified = self._validate_record(publication)
        state = self._reviews.get(verified.world_id, verified.review_id)
        if state is None:
            raise PersistenceIntegrityError("finalized publication references a missing review")
        self._validate_record_review(verified, state)
        stored = self._graph._revisions.get((verified.world_id, verified.published_revision_id))
        if stored is None:
            raise PersistenceIntegrityError("finalized publication references a missing revision")
        parent = self._graph._revisions.get(
            (verified.world_id, verified.expected_parent_revision_id)
        )
        if parent is None:
            raise PersistenceIntegrityError(
                "finalized publication references a missing parent revision"
            )
        self._validate_parent_revision(
            parent,
            world_id=verified.world_id,
            parent_revision_id=verified.expected_parent_revision_id,
            graph_schema=verified.graph_schema,
            graph_payload_sha256=verified.parent_graph_payload_sha256,
        )
        command = FinalizedReviewPublicationCommand(
            world_id=verified.world_id,
            review_id=verified.review_id,
            reviewed_contribution_id=verified.reviewed_contribution_id,
            reviewed_contribution_sha256=verified.reviewed_contribution_sha256,
            review_intent_sha256=verified.review_intent_sha256,
            confirmation_id=verified.confirmation_id,
            operation_id=verified.operation_id,
            expected_parent_revision_id=verified.expected_parent_revision_id,
            parent_graph_payload_sha256=verified.parent_graph_payload_sha256,
            expected_published_revision_id=verified.published_revision_id,
            graph_schema=verified.graph_schema,
            graph_payload=stored.graph_payload,
            graph_payload_sha256=verified.graph_payload_sha256,
            requested_published_at=verified.published_at,
        )
        self._validate_revision(stored, command=command)
        if stored.revision.created_at != verified.published_at:
            raise PersistenceIntegrityError(
                "finalized publication timestamp disagrees with its revision"
            )
        return _copy(verified)

    def get(
        self,
        world_id: str,
        operation_id: str,
    ) -> FinalizedReviewPublication | None:
        with self._graph._lock_for(world_id):
            publication = self._find_matching_unlocked(
                world_id=world_id,
                operation_id=operation_id,
            )
            return None if publication is None else self._reconstruct_unlocked(publication)

    def get_for_review(
        self,
        world_id: str,
        review_id: str,
    ) -> FinalizedReviewPublication | None:
        with self._graph._lock_for(world_id):
            publication = self._find_matching_unlocked(
                world_id=world_id,
                review_id=review_id,
            )
            return None if publication is None else self._reconstruct_unlocked(publication)

    @staticmethod
    def _record_from_revision(
        command: FinalizedReviewPublicationCommand,
        revision: WorldGraphRevision,
    ) -> FinalizedReviewPublication:
        return FinalizedReviewPublication(
            world_id=command.world_id,
            review_id=command.review_id,
            reviewed_contribution_id=command.reviewed_contribution_id,
            reviewed_contribution_sha256=command.reviewed_contribution_sha256,
            review_intent_sha256=command.review_intent_sha256,
            confirmation_id=command.confirmation_id,
            operation_id=command.operation_id,
            expected_parent_revision_id=command.expected_parent_revision_id,
            parent_graph_payload_sha256=command.parent_graph_payload_sha256,
            published_revision_id=command.expected_published_revision_id,
            graph_schema=command.graph_schema,
            graph_payload_sha256=command.graph_payload_sha256,
            published_at=revision.created_at,
        )

    def _store_unlocked(self, publication: FinalizedReviewPublication) -> None:
        keys = (
            (self._records_by_review, (publication.world_id, publication.review_id)),
            (self._records_by_operation, (publication.world_id, publication.operation_id)),
            (
                self._records_by_revision,
                (publication.world_id, publication.published_revision_id),
            ),
        )
        for records, key in keys:
            prior = records.get(key)
            if prior is not None and _fingerprint(prior) != _fingerprint(publication):
                raise IdempotencyConflictError(
                    "finalized publication identity conflicts with existing content"
                )
        for records, key in keys:
            records[key] = _copy(publication)

    def publish(
        self,
        command: FinalizedReviewPublicationCommand,
    ) -> FinalizedReviewPublication:
        validated_command = self._reload_command(command)
        world_id = validated_command.world_id
        with self._graph._lock_for(world_id):
            state = self._reviews.get(world_id, validated_command.review_id)
            if state is None:
                raise ContributionReviewNotFoundError(
                    "finalized contribution review was not found",
                    details={"world_id": world_id, "review_id": validated_command.review_id},
                )
            self._validate_review_binding(validated_command, state)
            parent = self._graph._revisions.get(
                (world_id, validated_command.expected_parent_revision_id)
            )
            if parent is None:
                raise PersistenceIntegrityError(
                    "finalized publication references a missing parent revision"
                )
            self._validate_parent_revision(
                parent,
                world_id=world_id,
                parent_revision_id=validated_command.expected_parent_revision_id,
                graph_schema=validated_command.graph_schema,
                graph_payload_sha256=validated_command.parent_graph_payload_sha256,
            )
            existing = self._find_matching_unlocked(
                world_id=world_id,
                review_id=validated_command.review_id,
                operation_id=validated_command.operation_id,
                revision_id=validated_command.expected_published_revision_id,
            )
            if existing is not None:
                self._validate_record_review(existing, state)
                self._validate_command_record(validated_command, existing)
                return self._reconstruct_unlocked(existing)

            existing_revision = self._graph._revisions.get(
                (world_id, validated_command.expected_published_revision_id)
            )
            if existing_revision is not None:
                self._validate_revision(existing_revision, command=validated_command)
                publication = self._record_from_revision(
                    validated_command,
                    existing_revision.revision,
                )
                self._store_unlocked(publication)
                return self._reconstruct_unlocked(publication)

            revision_key = (world_id, validated_command.expected_published_revision_id)
            old_revision = self._graph._revisions.get(revision_key)
            old_head = self._graph._heads.get(world_id)
            record_keys = (
                (self._records_by_review, (world_id, validated_command.review_id)),
                (self._records_by_operation, (world_id, validated_command.operation_id)),
                (
                    self._records_by_revision,
                    (world_id, validated_command.expected_published_revision_id),
                ),
            )
            old_records = tuple(
                (records, key, _copy(records[key]) if key in records else None)
                for records, key in record_keys
            )
            try:
                revision = self._graph._publish_revision_locked(
                    PublishRevisionCommand(
                        world_id=world_id,
                        parent_revision_id=validated_command.expected_parent_revision_id,
                        expected_parent_revision_id=validated_command.expected_parent_revision_id,
                        operation_ids=[validated_command.operation_id],
                        graph_schema=validated_command.graph_schema,
                        graph_payload=validated_command.graph_payload,
                        created_at=validated_command.requested_published_at,
                    )
                )
                if self._failure_hook is not None:
                    self._failure_hook()
                publication = self._record_from_revision(validated_command, revision)
                self._store_unlocked(publication)
                if self._failure_hook is not None:
                    self._failure_hook()
                return self._reconstruct_unlocked(publication)
            except BaseException:
                if old_revision is None:
                    self._graph._revisions.pop(revision_key, None)
                else:
                    self._graph._revisions[revision_key] = old_revision
                if old_head is None:
                    self._graph._heads.pop(world_id, None)
                else:
                    self._graph._heads[world_id] = old_head
                for records, key, old_record in old_records:
                    if old_record is None:
                        records.pop(key, None)
                    else:
                        records[key] = old_record
                raise


class InMemoryIdentityDecisionRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], DurableIdentityDecision] = {}
        # Re-entrant: promotion holds this family lock across its membership
        # re-proof, whose provider enumerates through this same repository.
        self._lock = threading.RLock()

    def append(self, decision: DurableIdentityDecision) -> DurableIdentityDecision:
        key = (decision.world_id, decision.decision_id)
        with self._lock:
            existing = self._items.get(key)
            if existing is not None:
                if _fingerprint(existing) != _fingerprint(decision):
                    raise IdempotencyConflictError(
                        f"identity decision {decision.decision_id!r} replayed with "
                        "different payload"
                    )
                return _copy(existing)
            self._items[key] = _copy(decision)
            return _copy(decision)

    def get(self, world_id: str, decision_id: str) -> DurableIdentityDecision | None:
        item = self._items.get((world_id, decision_id))
        return _copy(item) if item is not None else None

    def list_for_world(self, world_id: str) -> list[DurableIdentityDecision]:
        items = [d for (w, _), d in self._items.items() if w == world_id]
        items.sort(key=lambda d: d.decision_id)
        return [_copy(d) for d in items]


class InMemorySourceRepository:
    def __init__(self) -> None:
        self._artifacts: dict[str, SourceArtifactRecord] = {}
        self._revisions: dict[str, SourceRevision] = {}
        # Re-entrant: promotion holds this family lock across its membership
        # re-proof, whose provider enumerates through this same repository.
        self._lock = threading.RLock()

    def put_artifact(self, artifact: SourceArtifactRecord) -> SourceArtifactRecord:
        with self._lock:
            existing = self._artifacts.get(artifact.source_artifact_id)
            if existing is not None:
                if _fingerprint(existing) != _fingerprint(artifact):
                    raise IdempotencyConflictError(
                        f"source artifact {artifact.source_artifact_id!r} replayed with "
                        "different payload; mutable lifecycle needs a typed operation"
                    )
                return _copy(existing)
            self._artifacts[artifact.source_artifact_id] = _copy(artifact)
            return _copy(artifact)

    def list_artifacts_for_world(self, world_id: str) -> list[SourceArtifactRecord]:
        with self._lock:
            items = [a for a in self._artifacts.values() if a.world_id == world_id]
            items.sort(key=lambda a: a.source_artifact_id)
            return [_copy(a) for a in items]

    def get_artifact(self, source_artifact_id: str) -> SourceArtifactRecord | None:
        item = self._artifacts.get(source_artifact_id)
        return _copy(item) if item is not None else None

    def put_revision(self, revision: SourceRevision) -> SourceRevision:
        with self._lock:
            existing = self._revisions.get(revision.source_revision_id)
            if existing is not None:
                if _fingerprint(existing) != _fingerprint(revision):
                    raise IdempotencyConflictError(
                        f"source revision {revision.source_revision_id!r} replayed with "
                        "different payload"
                    )
                return _copy(existing)
            self._revisions[revision.source_revision_id] = _copy(revision)
            return _copy(revision)

    def get_revision(self, source_revision_id: str) -> SourceRevision | None:
        item = self._revisions.get(source_revision_id)
        return _copy(item) if item is not None else None

    def list_revisions(self, source_artifact_id: str) -> list[SourceRevision]:
        items = [r for r in self._revisions.values() if r.source_artifact_id == source_artifact_id]
        items.sort(key=lambda r: r.source_revision_id)
        return [_copy(r) for r in items]

    def get_provenance_snapshot(
        self,
        *,
        artifact_ids: Sequence[str],
        revision_ids: Sequence[str],
    ) -> SourceProvenanceSnapshot:
        requested_artifacts = frozenset(artifact_ids)
        requested_revisions = frozenset(revision_ids)
        with self._lock:
            artifacts = {
                artifact_id: _copy(self._artifacts[artifact_id])
                for artifact_id in requested_artifacts
                if artifact_id in self._artifacts
            }
            revisions = {
                revision_id: _copy(self._revisions[revision_id])
                for revision_id in requested_revisions
                if revision_id in self._revisions
            }
        return SourceProvenanceSnapshot.from_loaded(
            requested_artifact_ids=requested_artifacts,
            requested_revision_ids=requested_revisions,
            artifacts=artifacts,
            revisions=revisions,
        )


class InMemoryRetrievalSessionRepository:
    def __init__(self) -> None:
        self._items: dict[str, GraphRetrievalSession] = {}
        self._lock = threading.Lock()

    def create(self, session: GraphRetrievalSession) -> GraphRetrievalSession:
        with self._lock:
            existing = self._items.get(session.session_id)
            if existing is not None:
                if _fingerprint(existing) != _fingerprint(session):
                    raise IdempotencyConflictError(
                        f"retrieval session {session.session_id!r} already exists"
                    )
                return _copy(existing)
            self._items[session.session_id] = _copy(session)
            return _copy(session)

    def get(self, session_id: str) -> GraphRetrievalSession | None:
        item = self._items.get(session_id)
        return _copy(item) if item is not None else None

    def save(self, session: GraphRetrievalSession) -> GraphRetrievalSession:
        with self._lock:
            if session.session_id not in self._items:
                raise DocumentNotFoundError(f"retrieval session {session.session_id!r} not found")
            self._items[session.session_id] = _copy(session)
            return _copy(session)


class InMemoryMindThreadRepository:
    """v1: caller-private, cross-surface threads. Surface is per-turn only."""

    def __init__(self) -> None:
        self._threads: dict[str, dict[str, str | None]] = {}
        self._turns: dict[str, list[tuple[MindTurnRequest, MindTurnResponse]]] = {}
        self._lock = threading.Lock()

    def create_thread(
        self,
        thread_id: str,
        *,
        world_id: str,
        campaign_id: str | None,
        caller_id: str,
        tenant_id: str | None,
        created_at: datetime,
    ) -> str:
        binding = {
            "world_id": world_id,
            "campaign_id": campaign_id,
            "caller_id": caller_id,
            "tenant_id": tenant_id,
            "created_at": created_at.isoformat(),
        }
        with self._lock:
            existing = self._threads.get(thread_id)
            if existing is not None:
                # created_at is part of the immutable caller-provided binding.
                for key in (
                    "world_id",
                    "campaign_id",
                    "caller_id",
                    "tenant_id",
                    "created_at",
                ):
                    if existing[key] != binding[key]:
                        raise IdempotencyConflictError(
                            f"thread {thread_id!r} already bound with different context"
                        )
                return thread_id
            self._threads[thread_id] = binding
            self._turns[thread_id] = []
            return thread_id

    def append_turn(self, request: MindTurnRequest, response: MindTurnResponse) -> None:
        with self._lock:
            binding = self._threads.get(request.thread_id)
            if binding is None:
                raise DocumentNotFoundError(f"thread {request.thread_id!r} not found")
            if request.world_id != binding["world_id"]:
                raise ThreadContextMismatchError(
                    f"request world_id {request.world_id!r} != thread world {binding['world_id']!r}"
                )
            if request.campaign_id != binding["campaign_id"]:
                raise ThreadContextMismatchError(
                    f"request campaign_id {request.campaign_id!r} != thread campaign "
                    f"{binding['campaign_id']!r}"
                )
            if request.caller_scope.tenant_id != binding["tenant_id"]:
                raise ThreadContextMismatchError(
                    f"request tenant_id {request.caller_scope.tenant_id!r} != thread tenant "
                    f"{binding['tenant_id']!r}"
                )
            if request.caller_scope.caller_id != binding["caller_id"]:
                raise ThreadContextMismatchError(
                    f"request caller_id {request.caller_scope.caller_id!r} != thread caller "
                    f"{binding['caller_id']!r}"
                )
            if response.request_id != request.request_id:
                raise ThreadContextMismatchError(
                    f"response.request_id {response.request_id!r} != "
                    f"request.request_id {request.request_id!r}"
                )
            if response.thread_id != request.thread_id:
                raise ThreadContextMismatchError(
                    f"response.thread_id {response.thread_id!r} != "
                    f"request.thread_id {request.thread_id!r}"
                )
            if response.world_id != request.world_id:
                raise ThreadContextMismatchError(
                    f"response.world_id {response.world_id!r} != "
                    f"request.world_id {request.world_id!r}"
                )
            if response.campaign_id != request.campaign_id:
                raise ThreadContextMismatchError(
                    f"response.campaign_id {response.campaign_id!r} != "
                    f"request.campaign_id {request.campaign_id!r}"
                )

            turns = self._turns[request.thread_id]
            for existing_req, existing_resp in turns:
                if existing_resp.turn_id == response.turn_id:
                    if _fingerprint(existing_req) == _fingerprint(request) and _fingerprint(
                        existing_resp
                    ) == _fingerprint(response):
                        return  # exact replay; no duplicate
                    raise IdempotencyConflictError(
                        f"turn_id {response.turn_id!r} replayed with different payload"
                    )
                if existing_req.request_id == request.request_id:
                    raise IdempotencyConflictError(
                        f"request_id {request.request_id!r} already bound to a different turn"
                    )

            turns.append((_copy(request), _copy(response)))

    def list_turns(self, thread_id: str) -> list[tuple[MindTurnRequest, MindTurnResponse]]:
        return [(_copy(req), _copy(resp)) for req, resp in self._turns.get(thread_id, [])]


class InMemoryEmbeddingRunRepository:
    """Monotonic lifecycle: RUNNING→COMPLETED|FAILED; COMPLETED|FAILED→SUPERSEDED.

    ``activate`` binds one COMPLETED run per world for retrieval when a query
    omits ``materialization_run_id``. Superseding an active run clears it.

    ``materialization_lock`` is the shared unit-of-work lock for run transitions,
    document insert/delete, active-pointer changes, and retrieval eligibility
    snapshots. Document and search adapters must use this same lock.
    """

    def __init__(self) -> None:
        self._runs: dict[str, EmbeddingRun] = {}
        self._active_by_world: dict[str, str] = {}
        self.materialization_lock = threading.RLock()
        # Test-only: when set, released/reacquired around the callback so a
        # racing thread can mutate run state; production paths leave this None
        # and hold the UoW lock continuously across check+use.
        self._concurrency_yield: Callable[[], None] | None = None

    def _peek(self, run_id: str) -> EmbeddingRun | None:
        """Return a copy of the run. Caller must hold ``materialization_lock``."""
        item = self._runs.get(run_id)
        return _copy(item) if item is not None else None

    def _active_run_id_unlocked(self, world_id: str) -> str | None:
        return self._active_by_world.get(world_id)

    def _concurrency_yield_unlocked(self) -> None:
        """Test hook: drop the UoW lock so a racer can mutate, then reacquire."""
        gate = self._concurrency_yield
        if gate is None:
            return
        self.materialization_lock.release()
        try:
            gate()
        finally:
            self.materialization_lock.acquire()

    def begin(self, run: EmbeddingRun) -> EmbeddingRun:
        if run.status is not EmbeddingRunStatus.RUNNING:
            raise InvalidLifecycleTransitionError(
                record_type="embedding_run",
                record_id=run.run_id,
                current_status=run.status.value,
                requested_status=EmbeddingRunStatus.RUNNING.value,
            )
        if run.completed_at is not None:
            raise InvalidLifecycleTransitionError(
                "begin rejects terminal timestamps on input",
                record_type="embedding_run",
                record_id=run.run_id,
                current_status=run.status.value,
                requested_status=EmbeddingRunStatus.RUNNING.value,
            )
        with self.materialization_lock:
            existing = self._runs.get(run.run_id)
            if existing is not None:
                if _immutable_run_fingerprint(existing) != _immutable_run_fingerprint(run):
                    raise IdempotencyConflictError(
                        f"embedding run {run.run_id!r} replayed with different "
                        "immutable creation metadata"
                    )
                return _copy(existing)
            self._runs[run.run_id] = _copy(run)
            return _copy(run)

    def complete(self, run_id: str, *, completed_at: datetime) -> EmbeddingRun:
        with self.materialization_lock:
            existing = self._runs.get(run_id)
            if existing is None:
                raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
            if existing.status is EmbeddingRunStatus.COMPLETED:
                return _copy(existing)
            if existing.status is not EmbeddingRunStatus.RUNNING:
                raise InvalidLifecycleTransitionError(
                    record_type="embedding_run",
                    record_id=run_id,
                    current_status=existing.status.value,
                    requested_status=EmbeddingRunStatus.COMPLETED.value,
                )
            updated = existing.model_copy(
                deep=True,
                update={
                    "status": EmbeddingRunStatus.COMPLETED,
                    "completed_at": completed_at,
                },
            )
            self._runs[run_id] = updated
            return _copy(updated)

    def fail(self, run_id: str, *, completed_at: datetime) -> EmbeddingRun:
        with self.materialization_lock:
            existing = self._runs.get(run_id)
            if existing is None:
                raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
            if existing.status is EmbeddingRunStatus.FAILED:
                return _copy(existing)
            if existing.status is not EmbeddingRunStatus.RUNNING:
                raise InvalidLifecycleTransitionError(
                    record_type="embedding_run",
                    record_id=run_id,
                    current_status=existing.status.value,
                    requested_status=EmbeddingRunStatus.FAILED.value,
                )
            updated = existing.model_copy(
                deep=True,
                update={
                    "status": EmbeddingRunStatus.FAILED,
                    "completed_at": completed_at,
                },
            )
            self._runs[run_id] = updated
            return _copy(updated)

    def supersede(self, run_id: str, *, completed_at: datetime) -> EmbeddingRun:
        with self.materialization_lock:
            existing = self._runs.get(run_id)
            if existing is None:
                raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
            if existing.status is EmbeddingRunStatus.SUPERSEDED:
                return _copy(existing)
            if existing.status not in (
                EmbeddingRunStatus.COMPLETED,
                EmbeddingRunStatus.FAILED,
            ):
                raise InvalidLifecycleTransitionError(
                    record_type="embedding_run",
                    record_id=run_id,
                    current_status=existing.status.value,
                    requested_status=EmbeddingRunStatus.SUPERSEDED.value,
                )
            updated = existing.model_copy(
                deep=True,
                update={
                    "status": EmbeddingRunStatus.SUPERSEDED,
                    "completed_at": completed_at,
                },
            )
            self._runs[run_id] = updated
            if (
                existing.world_id is not None
                and self._active_by_world.get(existing.world_id) == run_id
            ):
                del self._active_by_world[existing.world_id]
            return _copy(updated)

    def activate(self, run_id: str) -> EmbeddingRun:
        with self.materialization_lock:
            existing = self._runs.get(run_id)
            if existing is None:
                raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
            if existing.status is not EmbeddingRunStatus.COMPLETED:
                raise InvalidLifecycleTransitionError(
                    (
                        "activate requires a COMPLETED embedding run; "
                        f"{run_id!r} is {existing.status.value}"
                    ),
                    record_type="embedding_run",
                    record_id=run_id,
                    current_status=existing.status.value,
                    requested_status="activate",
                )
            if existing.world_id is None:
                raise ScopeResolutionError(
                    f"embedding run {run_id!r} has no world_id; cannot activate",
                    details={"run_id": run_id, "reason": "missing_world_id"},
                )
            self._active_by_world[existing.world_id] = run_id
            return _copy(existing)

    def get_active_run_id(self, world_id: str) -> str | None:
        with self.materialization_lock:
            return self._active_by_world.get(world_id)

    def get(self, run_id: str) -> EmbeddingRun | None:
        with self.materialization_lock:
            return self._peek(run_id)


class InMemorySemanticDocumentRepository:
    """Requires an embedding-run repository so provenance cannot drift.

    All mutate paths share ``embedding_runs.materialization_lock`` with run
    transitions and search eligibility (one materialization unit of work).
    """

    def __init__(self, embedding_runs: InMemoryEmbeddingRunRepository) -> None:
        self._docs: dict[str, SemanticDocument] = {}
        self._runs = embedding_runs

    def _assert_run_compatible_unlocked(self, doc: SemanticDocument) -> EmbeddingRun:
        run = self._runs._peek(doc.materialization_run_id)
        if run is None:
            raise DocumentNotFoundError(
                f"materialization run {doc.materialization_run_id!r} not found"
            )
        if doc.embedding_model != run.embedding_model:
            raise IdempotencyConflictError(
                f"document {doc.semantic_document_id!r} embedding_model mismatches run"
            )
        if doc.embedding_model_revision != run.embedding_model_revision:
            raise IdempotencyConflictError(
                f"document {doc.semantic_document_id!r} embedding_model_revision mismatches run"
            )
        if doc.embedding_dimensions != run.embedding_dimensions:
            raise IdempotencyConflictError(
                f"document {doc.semantic_document_id!r} embedding_dimensions mismatches run"
            )
        if doc.embedding_recipe != run.embedding_recipe:
            raise IdempotencyConflictError(
                f"document {doc.semantic_document_id!r} embedding_recipe mismatches run"
            )
        if run.world_id is not None and doc.world_id != run.world_id:
            raise IdempotencyConflictError(
                f"document {doc.semantic_document_id!r} world_id incompatible with run"
            )
        return run

    def upsert_batch(self, documents: list[SemanticDocument]) -> int:
        """All-or-nothing batch: preflight under lock, then insert only if every
        new document still belongs to a RUNNING run. Partial batches never stick.
        """
        documents = normalize_semantic_document_batch(documents)
        with self._runs.materialization_lock:
            # Lock order matches PostgreSQL: deterministic run_id order.
            run_ids = sorted({doc.materialization_run_id for doc in documents})
            for run_id in run_ids:
                if self._runs._peek(run_id) is None:
                    raise DocumentNotFoundError(f"materialization run {run_id!r} not found")

            to_insert: list[SemanticDocument] = []
            for doc in documents:
                self._assert_run_compatible_unlocked(doc)
                existing = self._docs.get(doc.semantic_document_id)
                if existing is not None:
                    if _fingerprint(existing) != _fingerprint(doc):
                        raise IdempotencyConflictError(
                            f"semantic document {doc.semantic_document_id!r} re-ingested with "
                            "different payload; re-embedding must create a new run and new "
                            "document ids (ADR-0003)"
                        )
                    continue
                run = self._runs._peek(doc.materialization_run_id)
                if run is None:
                    raise DocumentNotFoundError(
                        f"materialization run {doc.materialization_run_id!r} not found"
                    )
                if run.status is not EmbeddingRunStatus.RUNNING:
                    raise InvalidLifecycleTransitionError(
                        (
                            "new semantic documents require a RUNNING materialization "
                            f"run; {run.run_id!r} is {run.status.value}"
                        ),
                        record_type="embedding_run",
                        record_id=run.run_id,
                        current_status=run.status.value,
                        requested_status="accept_document",
                    )
                to_insert.append(doc)

            if not to_insert:
                return 0

            # Optional concurrency yield after the batch RUNNING observation and
            # before any insert — then re-confirm every run still RUNNING.
            self._runs._concurrency_yield_unlocked()
            for doc in to_insert:
                run = self._runs._peek(doc.materialization_run_id)
                if run is None:
                    raise DocumentNotFoundError(
                        f"materialization run {doc.materialization_run_id!r} not found"
                    )
                if run.status is not EmbeddingRunStatus.RUNNING:
                    raise InvalidLifecycleTransitionError(
                        (
                            "new semantic documents require a RUNNING materialization "
                            f"run; {run.run_id!r} is {run.status.value}"
                        ),
                        record_type="embedding_run",
                        record_id=run.run_id,
                        current_status=run.status.value,
                        requested_status="accept_document",
                    )

            for doc in to_insert:
                self._docs[doc.semantic_document_id] = _copy(doc)
            return len(to_insert)

    def get(self, semantic_document_id: str) -> SemanticDocument | None:
        with self._runs.materialization_lock:
            item = self._docs.get(semantic_document_id)
            return _copy(item) if item is not None else None

    def delete_run_documents(self, materialization_run_id: str) -> int:
        with self._runs.materialization_lock:
            run = self._runs._peek(materialization_run_id)
            if run is None:
                raise DocumentNotFoundError(f"embedding run {materialization_run_id!r} not found")
            if run.status not in (
                EmbeddingRunStatus.FAILED,
                EmbeddingRunStatus.SUPERSEDED,
            ):
                raise InvalidLifecycleTransitionError(
                    (
                        "delete_run_documents requires a FAILED or SUPERSEDED "
                        f"run; {materialization_run_id!r} is {run.status.value}"
                    ),
                    record_type="embedding_run",
                    record_id=materialization_run_id,
                    current_status=run.status.value,
                    requested_status="delete_documents",
                )
            doomed = [
                doc_id
                for doc_id, doc in self._docs.items()
                if doc.materialization_run_id == materialization_run_id
            ]
            for doc_id in doomed:
                del self._docs[doc_id]
            return len(doomed)

    def count(self, *, world_id: str | None = None) -> int:
        with self._runs.materialization_lock:
            if world_id is None:
                return len(self._docs)
            return sum(1 for doc in self._docs.values() if doc.world_id == world_id)

    def list_ids(self) -> list[str]:
        """Memory-adapter helper (not part of the port): all document ids, sorted."""
        with self._runs.materialization_lock:
            return sorted(self._docs)

    def _snapshot_docs_unlocked(self) -> list[SemanticDocument]:
        """Caller must hold ``materialization_lock``."""
        return [_copy(doc) for doc in self._docs.values()]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _tokenize(text: str) -> set[str]:
    return {tok for tok in text.casefold().split() if tok}


class InMemorySemanticSearch:
    """Brute-force candidate retrieval mirroring pgvector semantics at fixture scale.

    Filter semantics (fail-closed):
    - ``world_id`` is mandatory and exact.
    - retrieval is bound to one COMPLETED materialization run (explicit query
      pin or the world's active-run pointer); failed/superseded/running runs
      never contribute candidates.
    - eligibility resolve + document snapshot happen under the shared
      materialization unit-of-work lock.
    - a campaign-scoped query sees that campaign's docs plus world-universal docs;
      a world-level query (no campaign_scope) sees only world-universal docs.
    - ``visibility`` is required: ``player`` sees player docs only; ``gm`` sees all.
    """

    def __init__(
        self,
        documents: InMemorySemanticDocumentRepository,
        embedding_runs: InMemoryEmbeddingRunRepository,
    ) -> None:
        self._documents = documents
        self._runs = embedding_runs

    def _resolve_retrieval_run_unlocked(self, query: SemanticQuery) -> str:
        run_id = query.materialization_run_id
        if run_id is None:
            run_id = self._runs._active_run_id_unlocked(query.world_id)
        if run_id is None:
            raise ScopeResolutionError(
                f"no materialization run bound for world {query.world_id!r}",
                details={
                    "world_id": query.world_id,
                    "reason": "missing_active_materialization_run",
                },
            )
        run = self._runs._peek(run_id)
        if run is None:
            raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
        if run.status is not EmbeddingRunStatus.COMPLETED:
            raise ScopeResolutionError(
                (
                    f"retrieval requires a COMPLETED materialization run; "
                    f"{run_id!r} is {run.status.value}"
                ),
                details={
                    "world_id": query.world_id,
                    "run_id": run_id,
                    "status": run.status.value,
                    "reason": "materialization_run_not_retrieval_eligible",
                },
            )
        if run.world_id is not None and run.world_id != query.world_id:
            raise ScopeResolutionError(
                (
                    f"materialization run {run_id!r} world {run.world_id!r} "
                    f"does not match query world {query.world_id!r}"
                ),
                details={
                    "world_id": query.world_id,
                    "run_id": run_id,
                    "run_world_id": run.world_id,
                    "reason": "materialization_run_world_mismatch",
                },
            )
        return run_id

    def _eligible_unlocked(self, query: SemanticQuery, *, run_id: str) -> list[SemanticDocument]:
        result: list[SemanticDocument] = []
        for doc in self._documents._snapshot_docs_unlocked():
            if doc.materialization_run_id != run_id:
                continue
            if doc.world_id != query.world_id:
                continue
            if query.campaign_scope is not None:
                if doc.campaign_scope not in (None, query.campaign_scope):
                    continue
            elif doc.campaign_scope is not None:
                continue
            if query.visibility is Visibility.PLAYER and doc.visibility is not Visibility.PLAYER:
                continue
            if query.document_kind is not None and doc.document_kind is not query.document_kind:
                continue
            if (
                query.graph_revision_id is not None
                and doc.graph_revision_id != query.graph_revision_id
            ):
                continue
            result.append(doc)
        return result

    def search(self, query: SemanticQuery) -> list[SemanticCandidate]:
        with self._runs.materialization_lock:
            run_id = self._resolve_retrieval_run_unlocked(query)
            docs = self._eligible_unlocked(query, run_id=run_id)
            self._runs._concurrency_yield_unlocked()
            # Re-resolve after any test yield; production holds the lock and
            # sees a stable COMPLETED run through the whole eligibility snapshot.
            self._resolve_retrieval_run_unlocked(
                query.model_copy(update={"materialization_run_id": run_id})
            )
            candidates: list[SemanticCandidate] = []

            if query.text:
                exact = [
                    (doc.semantic_document_id, 1.0)
                    for doc in docs
                    if query.text.casefold() in doc.content.casefold()
                    or query.text == doc.semantic_document_id
                    or query.text == doc.graph_object_id
                ]
                candidates.extend(self._ranked(exact, CandidateChannel.EXACT, query.top_k))

            if query.text:
                query_tokens = _tokenize(query.text)
                lexical = []
                for doc in docs:
                    doc_tokens = _tokenize(doc.content)
                    if not query_tokens:
                        break
                    overlap = len(query_tokens & doc_tokens)
                    if overlap:
                        lexical.append((doc.semantic_document_id, overlap / len(query_tokens)))
                candidates.extend(self._ranked(lexical, CandidateChannel.LEXICAL, query.top_k))

            if query.embedding:
                dense = [
                    (doc.semantic_document_id, _cosine(query.embedding, doc.embedding))
                    for doc in docs
                    if doc.embedding is not None and len(doc.embedding) == len(query.embedding)
                ]
                candidates.extend(self._ranked(dense, CandidateChannel.DENSE, query.top_k))

            return candidates

    @staticmethod
    def _ranked(
        scored: list[tuple[str, float]], channel: CandidateChannel, top_k: int
    ) -> list[SemanticCandidate]:
        ordered = sorted(scored, key=lambda kv: (-kv[1], kv[0]))[:top_k]
        return [
            SemanticCandidate(semantic_document_id=doc_id, channel=channel, rank=rank, score=score)
            for rank, (doc_id, score) in enumerate(ordered, start=1)
        ]


class InMemoryExistingWorldAdoptionRepository:
    """Atomic in-memory existing-world adoption unit of work.

    The graph repository owns the per-world lock. Adoption uses that same lock
    so imported source/history rows, the first revision/head, and the terminal
    receipt are one reversible in-memory transaction. Promotion additionally
    holds every membership family lock across its re-proof and swap, so
    concurrent history writers are excluded for the whole boundary (the
    in-memory analog of the PostgreSQL adapter's table locks).
    """

    def __init__(
        self,
        world_graph_repository: InMemoryWorldGraphRepository,
        source_repository: InMemorySourceRepository,
        contribution_repository: InMemoryContributionRepository,
        identity_repository: InMemoryIdentityDecisionRepository,
        *,
        failure_hook: Callable[[str], None] | None = None,
        reviewed_initialization_lookup: Callable[[str], bool] | None = None,
    ) -> None:
        self._graph = world_graph_repository
        self._sources = source_repository
        self._contributions = contribution_repository
        self._identity = identity_repository
        self._receipts_by_world: dict[str, DurableExistingWorldAdoptionReceipt] = {}
        self._receipts_by_adoption: dict[str, DurableExistingWorldAdoptionReceipt] = {}
        self._failure_hook = failure_hook
        self._reviewed_initialization_lookup = reviewed_initialization_lookup

    @staticmethod
    def _validate_record(
        receipt: DurableExistingWorldAdoptionReceipt,
    ) -> DurableExistingWorldAdoptionReceipt:
        schema = getattr(receipt, "schema_version", None)
        if schema == EXISTING_WORLD_ADOPTION_RECEIPT_SCHEMA:
            receipt_type: type[DurableExistingWorldAdoptionReceipt] = (
                ExistingWorldAdoptionReceiptV1
            )
        elif schema == EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA:
            receipt_type = ExistingWorldAdoptionReceiptV2
        elif schema == EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA:
            receipt_type = ExistingWorldAdoptionReceiptV4
        elif schema == EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA:
            receipt_type = ExistingWorldAdoptionReceiptV3
        else:
            raise PersistenceIntegrityError(
                "existing-world adoption receipt failed reconstruction"
            )
        try:
            return receipt_type.model_validate(receipt.model_dump(mode="json"))
        except Exception:
            raise PersistenceIntegrityError(
                "existing-world adoption receipt failed reconstruction"
            ) from None

    def _snapshot_world(self, world_id: str) -> dict[str, Any]:
        artifact_ids = {
            artifact_id
            for artifact_id, artifact in self._sources._artifacts.items()
            if artifact.world_id == world_id
        }
        return {
            "artifacts": {
                artifact_id: _copy(self._sources._artifacts[artifact_id])
                for artifact_id in artifact_ids
            },
            "revisions": {
                revision_id: _copy(revision)
                for revision_id, revision in self._sources._revisions.items()
                if revision.source_artifact_id in artifact_ids
            },
            "contributions": {
                key: _copy(item)
                for key, item in self._contributions._items.items()
                if key[0] == world_id
            },
            "identity": {
                key: _copy(item)
                for key, item in self._identity._items.items()
                if key[0] == world_id
            },
            "revisions_graph": {
                key: copy.deepcopy(stored)
                for key, stored in self._graph._revisions.items()
                if key[0] == world_id
            },
            "head": copy.deepcopy(self._graph._heads.get(world_id)),
            "receipt": (
                _copy(self._receipts_by_world[world_id])
                if world_id in self._receipts_by_world
                else None
            ),
        }

    def _restore_world(self, world_id: str, snapshot: dict[str, Any]) -> None:
        current_artifact_ids = {
            artifact_id
            for artifact_id, artifact in self._sources._artifacts.items()
            if artifact.world_id == world_id
        }
        owned_artifact_ids = current_artifact_ids | set(snapshot["artifacts"])
        for artifact_id in current_artifact_ids:
            self._sources._artifacts.pop(artifact_id, None)
        self._sources._artifacts.update(snapshot["artifacts"])
        for revision_id, revision in list(self._sources._revisions.items()):
            if revision.source_artifact_id in owned_artifact_ids:
                self._sources._revisions.pop(revision_id, None)
        self._sources._revisions.update(snapshot["revisions"])
        for key in [key for key in self._contributions._items if key[0] == world_id]:
            self._contributions._items.pop(key, None)
        self._contributions._items.update(snapshot["contributions"])
        for key in [key for key in self._identity._items if key[0] == world_id]:
            self._identity._items.pop(key, None)
        self._identity._items.update(snapshot["identity"])
        for key in [key for key in self._graph._revisions if key[0] == world_id]:
            self._graph._revisions.pop(key, None)
        self._graph._revisions.update(snapshot["revisions_graph"])
        if snapshot["head"] is None:
            self._graph._heads.pop(world_id, None)
        else:
            self._graph._heads[world_id] = snapshot["head"]
        previous = self._receipts_by_world.pop(world_id, None)
        if previous is not None:
            self._receipts_by_adoption.pop(previous.adoption_id, None)
        if snapshot["receipt"] is not None:
            restored = snapshot["receipt"]
            self._receipts_by_world[world_id] = restored
            self._receipts_by_adoption[restored.adoption_id] = restored

    def _assert_pristine(self, world_id: str) -> None:
        if (
            self._reviewed_initialization_lookup is not None
            and self._reviewed_initialization_lookup(world_id)
        ):
            raise PersistenceIntegrityError(
                "existing-world adoption target is not pristine",
                details={
                    "reason": "non_pristine_target",
                    "family": "reviewed_world_initialization",
                },
            )
        if self._graph._heads.get(world_id) is not None:
            raise PersistenceIntegrityError(
                "existing-world adoption target is not pristine",
                details={"reason": "non_pristine_target", "family": "graph_head"},
            )
        if any(key[0] == world_id for key in self._graph._revisions):
            raise PersistenceIntegrityError(
                "existing-world adoption target is not pristine",
                details={"reason": "non_pristine_target", "family": "graph_revision"},
            )
        if any(key[0] == world_id for key in self._contributions._items):
            raise PersistenceIntegrityError(
                "existing-world adoption target is not pristine",
                details={"reason": "non_pristine_target", "family": "contribution"},
            )
        if any(key[0] == world_id for key in self._identity._items):
            raise PersistenceIntegrityError(
                "existing-world adoption target is not pristine",
                details={"reason": "non_pristine_target", "family": "identity_decision"},
            )
        if any(artifact.world_id == world_id for artifact in self._sources._artifacts.values()):
            raise PersistenceIntegrityError(
                "existing-world adoption target is not pristine",
                details={"reason": "non_pristine_target", "family": "source_artifact"},
            )

    def _put_artifact_locked(self, artifact: SourceArtifactRecord) -> None:
        existing = self._sources._artifacts.get(artifact.source_artifact_id)
        if existing is not None:
            if _fingerprint(existing) != _fingerprint(artifact):
                raise IdempotencyConflictError(
                    f"source artifact {artifact.source_artifact_id!r} replayed with "
                    "different payload; mutable lifecycle needs a typed operation"
                )
            return
        self._sources._artifacts[artifact.source_artifact_id] = _copy(artifact)

    def _put_revision_locked(self, revision: SourceRevision) -> None:
        existing = self._sources._revisions.get(revision.source_revision_id)
        if existing is not None:
            if _fingerprint(existing) != _fingerprint(revision):
                raise IdempotencyConflictError(
                    f"source revision {revision.source_revision_id!r} replayed with "
                    "different payload"
                )
            return
        self._sources._revisions[revision.source_revision_id] = _copy(revision)

    def _append_contribution_locked(self, contribution: DurableGraphContribution) -> None:
        key = (contribution.world_id, contribution.contribution_id)
        existing = self._contributions._items.get(key)
        if existing is not None:
            if _fingerprint(existing) != _fingerprint(contribution):
                raise IdempotencyConflictError(
                    f"contribution {contribution.contribution_id!r} replayed with different payload"
                )
            return
        self._contributions._items[key] = _copy(contribution)

    def _append_identity_locked(self, decision: DurableIdentityDecision) -> None:
        key = (decision.world_id, decision.decision_id)
        existing = self._identity._items.get(key)
        if existing is not None:
            if _fingerprint(existing) != _fingerprint(decision):
                raise IdempotencyConflictError(
                    f"identity decision {decision.decision_id!r} replayed with different payload"
                )
            return
        self._identity._items[key] = _copy(decision)

    def _reconstruct_unlocked(
        self, receipt: DurableExistingWorldAdoptionReceipt
    ) -> DurableExistingWorldAdoptionReceipt:
        verified = self._validate_record(receipt)
        stored = self._graph._revisions.get((verified.world_id, verified.published_revision_id))
        if stored is None:
            raise PersistenceIntegrityError(
                "existing-world adoption receipt references a missing revision"
            )
        if (
            stored.revision.graph_payload_sha256 != verified.graph_payload_sha256
            or stored.revision.graph_schema != verified.graph_schema
            or stored.revision.world_id != verified.world_id
        ):
            raise PersistenceIntegrityError(
                "existing-world adoption receipt disagrees with its published revision"
            )
        return _copy(verified)

    def get(self, world_id: str, adoption_id: str) -> DurableExistingWorldAdoptionReceipt | None:
        with self._graph._lock_for(world_id):
            receipt = self._receipts_by_world.get(world_id)
            if receipt is None or receipt.adoption_id != adoption_id:
                return None
            return self._reconstruct_unlocked(receipt)

    def get_for_world(self, world_id: str) -> DurableExistingWorldAdoptionReceipt | None:
        with self._graph._lock_for(world_id):
            receipt = self._receipts_by_world.get(world_id)
            if receipt is None:
                return None
            return self._reconstruct_unlocked(receipt)

    def promote_to_v3_receipt(
        self,
        world_id: str,
        *,
        expected: ExistingWorldAdoptionReceiptV2,
        promoted: ExistingWorldAdoptionReceiptV3,
        current_membership_sha256: Callable[[], str],
    ) -> ExistingWorldAdoptionReceiptV3:
        """Atomically replace the stored v2 receipt with its v3 form.

        One writer-excluding boundary: the per-world graph lock, then every
        membership family lock — sources, contributions, identity, always in
        that order — held across the receipt re-verification, the
        ``current_membership_sha256()`` re-proof, and the receipt swap. The
        family locks are the locks every membership writer acquires, so no
        history write can commit between the authoritative equality proof and
        the swap; this is the in-memory analog of the PostgreSQL adapter's
        ``SHARE ROW EXCLUSIVE`` table locks. (The family locks are re-entrant
        because the provider enumerates through these same repositories on
        this thread.) Inside the boundary: re-read and re-verify the current
        receipt, require fingerprint equality with ``expected`` and v2-fact
        preservation by ``promoted``, require the re-proof to equal the
        promoted checkpoint exactly, then swap only the receipt
        representation. An already-promoted receipt fingerprint-equal to
        ``promoted`` is an exact no-op; anything else fails with zero
        mutation.
        """
        with (
            self._graph._lock_for(world_id),
            self._sources._lock,
            self._contributions._lock,
            self._identity._lock,
        ):
            current = self._receipts_by_world.get(world_id)
            if current is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt promotion found no receipt",
                    details={"reason": "adoption_receipt_missing", "world_id": world_id},
                )
            verified = self._reconstruct_unlocked(current)
            if isinstance(verified, ExistingWorldAdoptionReceiptV4):
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt promotion requires a v2 receipt",
                    details={
                        "reason": "adoption_receipt_promotion_unsupported_schema",
                        "world_id": world_id,
                        "receipt_schema": verified.schema_version,
                    },
                )
            if isinstance(verified, ExistingWorldAdoptionReceiptV3):
                if _fingerprint(verified) == _fingerprint(promoted):
                    return _copy(verified)
                raise PersistenceIntegrityError(
                    "existing-world adoption promotion conflicts with the stored v3 receipt",
                    details={
                        "reason": "adoption_receipt_promotion_identity_mismatch",
                        "world_id": world_id,
                    },
                )
            if not isinstance(verified, ExistingWorldAdoptionReceiptV2):
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt promotion requires a v2 receipt",
                    details={
                        "reason": "adoption_receipt_promotion_unsupported_schema",
                        "world_id": world_id,
                        "receipt_schema": verified.schema_version,
                    },
                )
            if _fingerprint(verified) != _fingerprint(expected):
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt changed before promotion",
                    details={
                        "reason": "adoption_receipt_promotion_identity_mismatch",
                        "world_id": world_id,
                    },
                )
            if _v2_adoption_facts(verified) != _v2_adoption_facts(promoted):
                raise PersistenceIntegrityError(
                    "existing-world adoption v3 receipt must preserve the v2 adoption facts",
                    details={
                        "reason": "adoption_receipt_promotion_fact_drift",
                        "world_id": world_id,
                    },
                )
            observed_membership_sha256 = current_membership_sha256()
            if observed_membership_sha256 != promoted.membership_sha256:
                raise PersistenceIntegrityError(
                    "existing-world adoption membership changed before promotion",
                    details={
                        "reason": "adoption_promotion_membership_mismatch",
                        "world_id": world_id,
                        "adoption_id": promoted.adoption_id,
                        "expected_membership_sha256": promoted.membership_sha256,
                        "current_membership_sha256": observed_membership_sha256,
                    },
                )
            stored = _copy(promoted)
            self._receipts_by_world[world_id] = stored
            self._receipts_by_adoption[stored.adoption_id] = stored
            restored = self._reconstruct_unlocked(stored)
            if not isinstance(restored, ExistingWorldAdoptionReceiptV3):
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt failed reconstruction"
                )
            return restored

    def _load_adopted_membership(
        self,
        command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    ) -> LoadedAdoptedMembership:
        manifest = command.membership_manifest
        artifacts: dict[str, Any] = {}
        for artifact_id in manifest.source_artifact_ids:
            artifact = self._sources._artifacts.get(artifact_id)
            if artifact is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption repair adopted artifact missing",
                    details={
                        "reason": "adoption_repair_artifact_missing",
                        "artifact_id": artifact_id,
                    },
                )
            if artifact.world_id != command.world_id:
                raise PersistenceIntegrityError(
                    "existing-world adoption repair artifact world mismatch",
                    details={
                        "reason": "adoption_repair_artifact_world_mismatch",
                        "artifact_id": artifact_id,
                    },
                )
            artifacts[artifact_id] = artifact
        revisions: dict[str, Any] = {}
        for revision_id in manifest.source_revision_ids:
            revision = self._sources._revisions.get(revision_id)
            if revision is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption repair adopted revision missing",
                    details={
                        "reason": "adoption_repair_revision_missing",
                        "revision_id": revision_id,
                    },
                )
            revisions[revision_id] = revision
        contributions: dict[str, Any] = {}
        for contribution_id in manifest.contribution_ids:
            item = self._contributions._items.get((command.world_id, contribution_id))
            if item is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption repair adopted contribution missing",
                    details={
                        "reason": "adoption_repair_contribution_missing",
                        "contribution_id": contribution_id,
                    },
                )
            contributions[contribution_id] = item
        identity_decisions: dict[str, Any] = {}
        for decision_id in manifest.identity_decision_ids:
            item = self._identity._items.get((command.world_id, decision_id))
            if item is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption repair adopted identity decision missing",
                    details={
                        "reason": "adoption_repair_identity_missing",
                        "decision_id": decision_id,
                    },
                )
            identity_decisions[decision_id] = item
        return LoadedAdoptedMembership(
            artifacts=artifacts,
            revisions=revisions,
            contributions=contributions,
            identity_decisions=identity_decisions,
        )

    def repair_source_classification(
        self,
        command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
        *,
        dry_run: bool = False,
    ) -> ExistingWorldAdoptionReceiptV4:
        """Atomically repair the source classification of one already-adopted world.

        One writer-excluding boundary: the per-world graph lock, then every
        membership family lock — sources, contributions, identity, always in
        that order — held across the receipt re-verification, the pre-mutation
        proofs, the mutation, and the receipt swap. ``dry_run=True`` performs
        the same proofs and returns the would-be V4 receipt with zero writes.
        """
        world_id = command.world_id
        with (
            self._graph._lock_for(world_id),
            self._sources._lock,
            self._contributions._lock,
            self._identity._lock,
        ):
            current = self._receipts_by_world.get(world_id)
            if current is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption repair found no receipt",
                    details={"reason": "adoption_receipt_missing", "world_id": world_id},
                )
            verified = self._reconstruct_unlocked(current)
            stored_revision = self._graph._revisions.get(
                (verified.world_id, verified.published_revision_id)
            )
            if stored_revision is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt references a missing revision"
                )
            loaded = self._load_adopted_membership(command)
            prepared = prepare_source_classification_repair(
                command=command,
                stored=verified,
                loaded=loaded,
                published_graph_payload=stored_revision.graph_payload,
            )
            if isinstance(prepared, ExistingWorldAdoptionReceiptV4):
                return _copy(prepared)
            if dry_run:
                return prepared.v4_receipt.model_copy(deep=True)
            snapshot = self._snapshot_world(world_id)
            try:
                for target in prepared.artifacts_to_write:
                    self._sources._artifacts[target.source_artifact_id] = _copy(target)
                if self._failure_hook is not None:
                    self._failure_hook("repaired_artifacts")
                observed_m1 = membership_from_loaded(
                    self._load_adopted_membership(command),
                    command.membership_manifest,
                )
                if observed_m1 != command.effective_membership_sha256:
                    raise PersistenceIntegrityError(
                        "existing-world adoption repair effective membership mismatch",
                        details={
                            "reason": "adoption_repair_effective_mismatch",
                            "world_id": world_id,
                            "expected_membership_sha256": (
                                command.effective_membership_sha256
                            ),
                            "observed_membership_sha256": observed_m1,
                        },
                    )
                stored = _copy(prepared.v4_receipt)
                self._receipts_by_world[world_id] = stored
                self._receipts_by_adoption[stored.adoption_id] = stored
                if self._failure_hook is not None:
                    self._failure_hook("receipt")
                restored = self._reconstruct_unlocked(stored)
                if not isinstance(restored, ExistingWorldAdoptionReceiptV4):
                    raise PersistenceIntegrityError(
                        "existing-world adoption receipt failed reconstruction"
                    )
                return restored
            except BaseException:
                self._restore_world(world_id, snapshot)
                raise

    def adopt(
        self, command: DurableExistingWorldAdoptionCommand
    ) -> DurableExistingWorldAdoptionReceipt:
        validated = bind_existing_world_adoption_command(command)
        bundle = validated.bundle
        world_id = bundle.world_id
        with self._graph._lock_for(world_id):
            existing = self._receipts_by_world.get(world_id)
            if existing is not None:
                verified = self._reconstruct_unlocked(existing)
                if verified.bundle_sha256 == validated.bundle_sha256:
                    return verified
                raise IdempotencyConflictError(
                    "existing-world adoption identity conflicts with the requested bundle"
                )
            other = self._receipts_by_adoption.get(bundle.adoption_id)
            if other is not None:
                raise IdempotencyConflictError(
                    f"adoption {bundle.adoption_id!r} already exists for another world"
                )
            self._assert_pristine(world_id)
            snapshot = self._snapshot_world(world_id)
            try:
                for artifact in bundle.source_artifacts:
                    self._put_artifact_locked(artifact)
                for revision in bundle.source_revisions:
                    self._put_revision_locked(revision)
                if self._failure_hook is not None:
                    self._failure_hook("source_records")
                for contribution in bundle.contributions:
                    self._append_contribution_locked(contribution)
                if self._failure_hook is not None:
                    self._failure_hook("contributions")
                for decision in bundle.identity_decisions:
                    self._append_identity_locked(decision)
                if self._failure_hook is not None:
                    self._failure_hook("identity_decisions")
                    self._failure_hook("source_history")
                graph_command = PublishRevisionCommand(
                    world_id=world_id,
                    parent_revision_id=None,
                    expected_parent_revision_id=None,
                    operation_ids=[bundle.adoption_id],
                    graph_schema=bundle.graph_schema,
                    graph_payload=bundle.graph_payload,
                    created_at=validated.requested_adopted_at,
                )
                revision = self._graph._publish_revision_locked(graph_command)
                if revision.revision_id != validated.expected_published_revision_id:
                    raise PersistenceIntegrityError(
                        "published adoption revision id disagrees with the command"
                    )
                if revision.graph_payload_sha256 != validated.graph_payload_sha256:
                    raise PersistenceIntegrityError(
                        "published adoption payload digest disagrees with the command"
                    )
                if self._failure_hook is not None:
                    self._failure_hook("graph")
                receipt = terminal_existing_world_adoption_receipt(
                    validated,
                    published_revision_id=revision.revision_id,
                )
                self._receipts_by_world[world_id] = receipt
                self._receipts_by_adoption[bundle.adoption_id] = receipt
                if self._failure_hook is not None:
                    self._failure_hook("receipt")
                return self._reconstruct_unlocked(receipt)
            except BaseException:
                self._restore_world(world_id, snapshot)
                raise


class InMemoryReviewedWorldInitializationRepository:
    """Atomic in-memory reviewed first-world initialization unit of work."""

    def __init__(
        self,
        world_graph_repository: InMemoryWorldGraphRepository,
        source_repository: InMemorySourceRepository,
        contribution_repository: InMemoryContributionRepository,
        identity_repository: InMemoryIdentityDecisionRepository | None = None,
        *,
        failure_hook: Callable[[str], None] | None = None,
        adoption_lookup: Callable[[str], bool] | None = None,
    ) -> None:
        self._graph = world_graph_repository
        self._sources = source_repository
        self._contributions = contribution_repository
        self._identity = identity_repository
        self._receipts_by_world: dict[str, ReviewedWorldInitializationReceiptV1] = {}
        self._receipts_by_initialization: dict[str, ReviewedWorldInitializationReceiptV1] = (
            {}
        )
        self._failure_hook = failure_hook
        self._adoption_lookup = adoption_lookup

    def _assert_pristine(self, world_id: str) -> None:
        if self._adoption_lookup is not None and self._adoption_lookup(world_id):
            raise PersistenceIntegrityError(
                "reviewed-world initialization target is not pristine",
                details={"reason": "non_pristine_target", "family": "existing_world_adoption"},
            )
        if self._graph._heads.get(world_id) is not None:
            raise PersistenceIntegrityError(
                "reviewed-world initialization target is not pristine",
                details={"reason": "non_pristine_target", "family": "graph_head"},
            )
        if any(key[0] == world_id for key in self._graph._revisions):
            raise PersistenceIntegrityError(
                "reviewed-world initialization target is not pristine",
                details={"reason": "non_pristine_target", "family": "graph_revision"},
            )
        if any(key[0] == world_id for key in self._contributions._items):
            raise PersistenceIntegrityError(
                "reviewed-world initialization target is not pristine",
                details={"reason": "non_pristine_target", "family": "contribution"},
            )
        if self._identity is not None and any(
            key[0] == world_id for key in self._identity._items
        ):
            raise PersistenceIntegrityError(
                "reviewed-world initialization target is not pristine",
                details={"reason": "non_pristine_target", "family": "identity_decision"},
            )
        if any(artifact.world_id == world_id for artifact in self._sources._artifacts.values()):
            raise PersistenceIntegrityError(
                "reviewed-world initialization target is not pristine",
                details={"reason": "non_pristine_target", "family": "source_artifact"},
            )
        if world_id in self._receipts_by_world:
            raise PersistenceIntegrityError(
                "reviewed-world initialization target is not pristine",
                details={
                    "reason": "non_pristine_target",
                    "family": "reviewed_world_initialization",
                },
            )

    def _snapshot_world(self, world_id: str) -> dict[str, Any]:
        artifact_ids = {
            artifact_id
            for artifact_id, artifact in self._sources._artifacts.items()
            if artifact.world_id == world_id
        }
        return {
            "artifacts": {
                artifact_id: _copy(self._sources._artifacts[artifact_id])
                for artifact_id in artifact_ids
            },
            "revisions": {
                revision_id: _copy(revision)
                for revision_id, revision in self._sources._revisions.items()
                if revision.source_artifact_id in artifact_ids
            },
            "contributions": {
                key: _copy(item)
                for key, item in self._contributions._items.items()
                if key[0] == world_id
            },
            "revisions_graph": {
                key: copy.deepcopy(stored)
                for key, stored in self._graph._revisions.items()
                if key[0] == world_id
            },
            "head": copy.deepcopy(self._graph._heads.get(world_id)),
            "receipt": (
                _copy(self._receipts_by_world[world_id])
                if world_id in self._receipts_by_world
                else None
            ),
        }

    def _restore_world(self, world_id: str, snapshot: dict[str, Any]) -> None:
        current_artifact_ids = {
            artifact_id
            for artifact_id, artifact in self._sources._artifacts.items()
            if artifact.world_id == world_id
        }
        owned_artifact_ids = current_artifact_ids | set(snapshot["artifacts"])
        for artifact_id in current_artifact_ids:
            self._sources._artifacts.pop(artifact_id, None)
        self._sources._artifacts.update(snapshot["artifacts"])
        for revision_id, revision in list(self._sources._revisions.items()):
            if revision.source_artifact_id in owned_artifact_ids:
                self._sources._revisions.pop(revision_id, None)
        self._sources._revisions.update(snapshot["revisions"])
        for key in [key for key in self._contributions._items if key[0] == world_id]:
            self._contributions._items.pop(key, None)
        self._contributions._items.update(snapshot["contributions"])
        for key in [key for key in self._graph._revisions if key[0] == world_id]:
            self._graph._revisions.pop(key, None)
        self._graph._revisions.update(snapshot["revisions_graph"])
        if snapshot["head"] is None:
            self._graph._heads.pop(world_id, None)
        else:
            self._graph._heads[world_id] = snapshot["head"]
        previous = self._receipts_by_world.pop(world_id, None)
        if previous is not None:
            self._receipts_by_initialization.pop(previous.initialization_id, None)
        if snapshot["receipt"] is not None:
            restored = snapshot["receipt"]
            self._receipts_by_world[world_id] = restored
            self._receipts_by_initialization[restored.initialization_id] = restored

    def _put_artifact_locked(self, artifact: SourceArtifactRecord) -> None:
        existing = self._sources._artifacts.get(artifact.source_artifact_id)
        if existing is not None:
            if _fingerprint(existing) != _fingerprint(artifact):
                raise IdempotencyConflictError(
                    f"source artifact {artifact.source_artifact_id!r} replayed with "
                    "different payload; mutable lifecycle needs a typed operation"
                )
            return
        self._sources._artifacts[artifact.source_artifact_id] = _copy(artifact)

    def _put_revision_locked(self, revision: SourceRevision) -> None:
        existing = self._sources._revisions.get(revision.source_revision_id)
        if existing is not None:
            if _fingerprint(existing) != _fingerprint(revision):
                raise IdempotencyConflictError(
                    f"source revision {revision.source_revision_id!r} replayed with "
                    "different payload"
                )
            return
        self._sources._revisions[revision.source_revision_id] = _copy(revision)

    def _append_contribution_locked(self, contribution: DurableGraphContribution) -> None:
        key = (contribution.world_id, contribution.contribution_id)
        existing = self._contributions._items.get(key)
        if existing is not None:
            if _fingerprint(existing) != _fingerprint(contribution):
                raise IdempotencyConflictError(
                    f"contribution {contribution.contribution_id!r} replayed with different payload"
                )
            return
        self._contributions._items[key] = _copy(contribution)

    def _reconstruct_unlocked(
        self, receipt: ReviewedWorldInitializationReceiptV1
    ) -> ReviewedWorldInitializationReceiptV1:
        try:
            verified = ReviewedWorldInitializationReceiptV1.model_validate(
                receipt.model_dump(mode="json")
            )
        except Exception:
            raise PersistenceIntegrityError(
                "reviewed-world initialization receipt failed reconstruction"
            ) from None
        stored = self._graph._revisions.get((verified.world_id, verified.published_revision_id))
        if stored is None:
            raise PersistenceIntegrityError(
                "reviewed-world initialization receipt references a missing revision"
            )
        if (
            stored.revision.graph_payload_sha256 != verified.published_graph_payload_sha256
            or stored.revision.graph_schema != verified.published_graph_schema
            or stored.revision.world_id != verified.world_id
            or stored.revision.parent_revision_id is not None
        ):
            raise PersistenceIntegrityError(
                "reviewed-world initialization receipt disagrees with its published revision"
            )
        return _copy(verified)

    def get(
        self, world_id: str, initialization_id: str
    ) -> ReviewedWorldInitializationReceiptV1 | None:
        with self._graph._lock_for(world_id):
            receipt = self._receipts_by_world.get(world_id)
            if receipt is None or receipt.initialization_id != initialization_id:
                return None
            return self._reconstruct_unlocked(receipt)

    def get_for_world(self, world_id: str) -> ReviewedWorldInitializationReceiptV1 | None:
        with self._graph._lock_for(world_id):
            receipt = self._receipts_by_world.get(world_id)
            if receipt is None:
                return None
            return self._reconstruct_unlocked(receipt)

    def initialize(
        self,
        command: ReviewedWorldInitializationCommandV1,
        *,
        graph_payload: dict[str, Any],
        graph_payload_sha256: str,
        accepted_assertion_ids: Sequence[str],
    ) -> ReviewedWorldInitializationReceiptV1:
        validated = bind_reviewed_world_initialization_command(command)
        identity = reviewed_world_initialization_replay_identity(validated)
        command_sha256 = identity.current_command_sha256
        world_id = validated.world_id
        if canonical_sha256(graph_payload) != graph_payload_sha256:
            raise PersistenceIntegrityError(
                "reviewed-world initialization graph payload digest disagrees with the command"
            )
        with self._graph._lock_for(world_id):
            existing = self._receipts_by_world.get(world_id)
            verified_existing = (
                self._reconstruct_unlocked(existing) if existing is not None else None
            )
            matched = replay_conflict_if_present(
                verified_existing,
                initialization_id=validated.initialization_id,
                identity=identity,
                world_id=world_id,
                other_world_receipt=lambda: self._receipts_by_initialization.get(
                    validated.initialization_id
                ),
            )
            if matched is not None:
                return matched
            self._assert_pristine(world_id)
            snapshot = self._snapshot_world(world_id)
            try:
                for artifact in validated.source_artifacts:
                    self._put_artifact_locked(artifact)
                for revision in validated.source_revisions:
                    self._put_revision_locked(revision)
                if self._failure_hook is not None:
                    self._failure_hook("source_records")
                self._append_contribution_locked(validated.reviewed_contribution)
                if self._failure_hook is not None:
                    self._failure_hook("contributions")
                graph_command = PublishRevisionCommand(
                    world_id=world_id,
                    parent_revision_id=None,
                    expected_parent_revision_id=None,
                    operation_ids=[validated.initialization_id],
                    graph_schema=GRAPH_SCHEMA_V6,
                    graph_payload=copy.deepcopy(graph_payload),
                    created_at=validated.requested_initialized_at,
                )
                revision = self._graph._publish_revision_locked(graph_command)
                if revision.graph_payload_sha256 != graph_payload_sha256:
                    raise PersistenceIntegrityError(
                        "published initialization payload digest disagrees with the command"
                    )
                if revision.parent_revision_id is not None:
                    raise PersistenceIntegrityError(
                        "published initialization revision must have a null parent"
                    )
                if self._failure_hook is not None:
                    self._failure_hook("graph")
                try:
                    materialization = FirstWorldMaterialization(
                        world_id=validated.world_id,
                        initialization_id=validated.initialization_id,
                        reviewed_contribution_id=(
                            validated.reviewed_contribution.contribution_id
                        ),
                        reviewed_contribution_sha256=contribution_v2_payload_sha256(
                            validated.reviewed_contribution
                        ),
                        graph_schema=GRAPH_SCHEMA_V6,
                        graph_payload=graph_payload,
                        graph_payload_sha256=graph_payload_sha256,
                        accepted_assertion_ids=tuple(accepted_assertion_ids),
                    )
                except Exception:
                    raise PersistenceIntegrityError(
                        "reviewed-world initialization materialization binding failed"
                    ) from None
                receipt = terminal_reviewed_world_initialization_receipt(
                    validated,
                    command_sha256=command_sha256,
                    materialization=materialization,
                    published_revision_id=revision.revision_id,
                )
                self._receipts_by_world[world_id] = receipt
                self._receipts_by_initialization[validated.initialization_id] = receipt
                if self._failure_hook is not None:
                    self._failure_hook("receipt")
                return self._reconstruct_unlocked(receipt)
            except BaseException:
                self._restore_world(world_id, snapshot)
                raise
