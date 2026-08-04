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
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from ...application.repositories import normalize_semantic_document_batch
from ...contracts.contribution import ContributionStatus, GraphContribution
from ...contracts.contribution_review import (
    ContributionReviewRecord,
    ContributionReviewState,
)
from ...contracts.evidence import SourceArtifact, SourceRevision
from ...contracts.graph import (
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from ...contracts.identity import IdentityDecisionRecord
from ...contracts.mind_turn import MindTurnRequest, MindTurnResponse
from ...contracts.retrieval import GraphRetrievalSession
from ...contracts.review_publication import (
    FinalizedReviewPublication,
    FinalizedReviewPublicationCommand,
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
        self._items: dict[tuple[str, str], GraphContribution] = {}
        self._finalized_review_ids: set[tuple[str, str]] = set()
        self._lock = threading.RLock()

    def append(self, contribution: GraphContribution) -> GraphContribution:
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
            self._items[key] = _copy(contribution)
            return _copy(contribution)

    def get(self, world_id: str, contribution_id: str) -> GraphContribution | None:
        with self._lock:
            item = self._items.get((world_id, contribution_id))
            return _copy(item) if item is not None else None

    def list_for_world(
        self, world_id: str, *, status: ContributionStatus | None = None
    ) -> list[GraphContribution]:
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
    ) -> GraphContribution:
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
        self._records: dict[tuple[str, str], ContributionReviewRecord] = {}
        self._lock = contributions._lock
        self._failure_hook = failure_hook

    def _reconstruct_unlocked(
        self, record: ContributionReviewRecord
    ) -> ContributionReviewState:
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
            return ContributionReviewState(
                record=_copy(record),
                candidate_contribution=_copy(candidate),
                reviewed_contribution=_copy(reviewed),
            )
        except Exception:
            raise PersistenceIntegrityError(
                f"review {record.review_id!r} failed reconstruction"
            ) from None

    def finalize(self, state: ContributionReviewState) -> ContributionReviewState:
        try:
            validated = ContributionReviewState.model_validate(
                state.model_dump(mode="json")
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
                if (
                    prior.world_id == record.world_id
                    and prior.operation_id == record.operation_id
                ):
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

    def get(self, world_id: str, review_id: str) -> ContributionReviewState | None:
        with self._lock:
            record = self._records.get((world_id, review_id))
            return None if record is None else self._reconstruct_unlocked(record)

    def get_for_plan(
        self, world_id: str, source_plan_id: str
    ) -> ContributionReviewState | None:
        with self._lock:
            record = next(
                (
                    item
                    for (record_world, _), item in self._records.items()
                    if record_world == world_id
                    and item.plan_ref.source_plan_id == source_plan_id
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
            return FinalizedReviewPublicationCommand.model_validate(
                command.model_dump(mode="json")
            )
        except Exception:
            raise PersistenceIntegrityError(
                "finalized publication command failed validation"
            ) from None

    @staticmethod
    def _validate_review_binding(
        command: FinalizedReviewPublicationCommand,
        state: ContributionReviewState,
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
        state: ContributionReviewState,
    ) -> None:
        record = state.record
        if (
            publication.world_id != record.world_id
            or publication.review_id != record.review_id
            or publication.reviewed_contribution_id != record.reviewed_contribution_id
            or publication.reviewed_contribution_sha256
            != record.reviewed_contribution_sha256
            or publication.review_intent_sha256 != record.review_intent_sha256
            or publication.confirmation_id != record.confirmation_id
            or publication.operation_id != record.operation_id
            or publication.expected_parent_revision_id
            != record.plan_ref.expected_parent_revision_id
            or publication.parent_graph_payload_sha256
            != record.plan_ref.base_graph_payload_sha256
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
            or publication.reviewed_contribution_sha256
            != command.reviewed_contribution_sha256
            or publication.review_intent_sha256 != command.review_intent_sha256
            or publication.confirmation_id != command.confirmation_id
            or publication.operation_id != command.operation_id
            or publication.expected_parent_revision_id
            != command.expected_parent_revision_id
            or publication.parent_graph_payload_sha256
            != command.parent_graph_payload_sha256
            or publication.published_revision_id
            != command.expected_published_revision_id
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
            return FinalizedReviewPublication.model_validate(
                publication.model_dump(mode="json")
            )
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
            for key, value in self._records_by_review.items():
                if key == (world_id, review_id):
                    matches[_fingerprint(value)] = value
        if operation_id is not None:
            for key, value in self._records_by_operation.items():
                if key == (world_id, operation_id):
                    matches[_fingerprint(value)] = value
        if revision_id is not None:
            for key, value in self._records_by_revision.items():
                if key == (world_id, revision_id):
                    matches[_fingerprint(value)] = value
        if len(matches) > 1:
            raise PersistenceIntegrityError(
                "multiple finalized publication identities conflict"
            )
        return next(iter(matches.values()), None)

    def _reconstruct_unlocked(
        self,
        publication: FinalizedReviewPublication,
    ) -> FinalizedReviewPublication:
        verified = self._validate_record(publication)
        state = self._reviews.get(verified.world_id, verified.review_id)
        if state is None:
            raise PersistenceIntegrityError(
                "finalized publication references a missing review"
            )
        self._validate_record_review(verified, state)
        stored = self._graph._revisions.get(
            (verified.world_id, verified.published_revision_id)
        )
        if stored is None:
            raise PersistenceIntegrityError(
                "finalized publication references a missing revision"
            )
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
            return (
                None
                if publication is None
                else self._reconstruct_unlocked(publication)
            )

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
            return (
                None
                if publication is None
                else self._reconstruct_unlocked(publication)
            )

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

            old_revisions = {
                key: _copy(value) for key, value in self._graph._revisions.items()
            }
            old_heads = {key: _copy(value) for key, value in self._graph._heads.items()}
            old_records = (
                dict(self._records_by_review),
                dict(self._records_by_operation),
                dict(self._records_by_revision),
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
                self._graph._revisions = old_revisions
                self._graph._heads = old_heads
                (
                    self._records_by_review,
                    self._records_by_operation,
                    self._records_by_revision,
                ) = old_records
                raise


class InMemoryIdentityDecisionRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], IdentityDecisionRecord] = {}
        self._lock = threading.Lock()

    def append(self, decision: IdentityDecisionRecord) -> IdentityDecisionRecord:
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

    def get(self, world_id: str, decision_id: str) -> IdentityDecisionRecord | None:
        item = self._items.get((world_id, decision_id))
        return _copy(item) if item is not None else None

    def list_for_world(self, world_id: str) -> list[IdentityDecisionRecord]:
        items = [d for (w, _), d in self._items.items() if w == world_id]
        items.sort(key=lambda d: d.decision_id)
        return [_copy(d) for d in items]


class InMemorySourceRepository:
    def __init__(self) -> None:
        self._artifacts: dict[str, SourceArtifact] = {}
        self._revisions: dict[str, SourceRevision] = {}
        self._lock = threading.Lock()

    def put_artifact(self, artifact: SourceArtifact) -> SourceArtifact:
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

    def get_artifact(self, source_artifact_id: str) -> SourceArtifact | None:
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
                    f"request world_id {request.world_id!r} != thread world "
                    f"{binding['world_id']!r}"
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
                    if (
                        _fingerprint(existing_req) == _fingerprint(request)
                        and _fingerprint(existing_resp) == _fingerprint(response)
                    ):
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
            if existing.world_id is not None and self._active_by_world.get(
                existing.world_id
            ) == run_id:
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
                f"document {doc.semantic_document_id!r} embedding_model_revision "
                "mismatches run"
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
                raise DocumentNotFoundError(
                    f"embedding run {materialization_run_id!r} not found"
                )
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

    def _eligible_unlocked(
        self, query: SemanticQuery, *, run_id: str
    ) -> list[SemanticDocument]:
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
                candidates.extend(
                    self._ranked(exact, CandidateChannel.EXACT, query.top_k)
                )

            if query.text:
                query_tokens = _tokenize(query.text)
                lexical = []
                for doc in docs:
                    doc_tokens = _tokenize(doc.content)
                    if not query_tokens:
                        break
                    overlap = len(query_tokens & doc_tokens)
                    if overlap:
                        lexical.append(
                            (doc.semantic_document_id, overlap / len(query_tokens))
                        )
                candidates.extend(
                    self._ranked(lexical, CandidateChannel.LEXICAL, query.top_k)
                )

            if query.embedding:
                dense = [
                    (doc.semantic_document_id, _cosine(query.embedding, doc.embedding))
                    for doc in docs
                    if doc.embedding is not None
                    and len(doc.embedding) == len(query.embedding)
                ]
                candidates.extend(
                    self._ranked(dense, CandidateChannel.DENSE, query.top_k)
                )

            return candidates

    @staticmethod
    def _ranked(
        scored: list[tuple[str, float]], channel: CandidateChannel, top_k: int
    ) -> list[SemanticCandidate]:
        ordered = sorted(scored, key=lambda kv: (-kv[1], kv[0]))[:top_k]
        return [
            SemanticCandidate(
                semantic_document_id=doc_id, channel=channel, rank=rank, score=score
            )
            for rank, (doc_id, score) in enumerate(ordered, start=1)
        ]
