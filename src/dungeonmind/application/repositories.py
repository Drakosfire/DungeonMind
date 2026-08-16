"""Repository protocols (ports).

Every durable store DungeonMind touches is defined here as a transport-neutral
Protocol and implemented by adapters (in-memory for tests/dev, PostgreSQL in
PR B). The contracts these ports exchange are the versioned wire contracts;
ports never leak adapter-specific types (no SQL rows, no driver cursors).

Failure model (from ``domain.errors``):
- publish: ``StaleParentRevisionError``, ``ImmutableRevisionConflictError``
- idempotent creates with conflicting payload: ``IdempotencyConflictError``
- reads of unknown ids return ``None`` (transport maps to 404 where relevant)
"""

from datetime import datetime
from typing import Protocol

from ..contracts.contribution import ContributionStatus, GraphContribution
from ..contracts.contribution_review import (
    ContributionReviewState,
)
from ..contracts.evidence import SourceArtifactRecord, SourceRevision
from ..contracts.existing_world_adoption import (
    ExistingWorldAdoptionCommandV1,
    ExistingWorldAdoptionReceiptV1,
)
from ..contracts.graph import (
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from ..contracts.identity import IdentityDecisionRecord
from ..contracts.mind_turn import MindTurnRequest, MindTurnResponse
from ..contracts.retrieval import GraphRetrievalSession
from ..contracts.review_publication import (
    FinalizedReviewPublication,
    FinalizedReviewPublicationCommand,
)
from ..contracts.semantic import (
    EmbeddingRun,
    SemanticCandidate,
    SemanticDocument,
    SemanticQuery,
)
from ..domain.canonical import canonical_json
from ..domain.errors import IdempotencyConflictError


def normalize_semantic_document_batch(
    documents: list[SemanticDocument],
) -> list[SemanticDocument]:
    """Collapse duplicate ``semantic_document_id`` entries within one batch.

    Identical duplicates count as one document. Differing duplicates raise
    ``IdempotencyConflictError``. Order of first occurrence is preserved.
    """
    seen: dict[str, SemanticDocument] = {}
    ordered: list[SemanticDocument] = []
    for doc in documents:
        prior = seen.get(doc.semantic_document_id)
        if prior is not None:
            if canonical_json(prior.model_dump(mode="json")) != canonical_json(
                doc.model_dump(mode="json")
            ):
                raise IdempotencyConflictError(
                    f"semantic document {doc.semantic_document_id!r} appears in the "
                    "same batch with conflicting payloads"
                )
            continue
        seen[doc.semantic_document_id] = doc
        ordered.append(doc)
    return ordered


class WorldGraphRepository(Protocol):
    """One supergraph per world; immutable revisions; one atomically advanced head."""

    def get_head(self, world_id: str) -> WorldGraphHead | None: ...

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision | None: ...

    def publish_revision(self, command: PublishRevisionCommand) -> WorldGraphRevision:
        """Validate, write the immutable revision, then advance the head in one
        atomic compare-and-swap. A failed publish leaves the prior head readable.
        Raises ``StaleParentRevisionError`` / ``ImmutableRevisionConflictError``."""
        ...

    def rollback_head(
        self, world_id: str, target_revision_id: str, *, updated_at: datetime
    ) -> WorldGraphHead:
        """Repoint the head to an existing, validated revision. Auditable;
        never deletes the abandoned revision. Raises ``RevisionNotFoundError``."""
        ...


class ContributionRepository(Protocol):
    """The governed write ledger. Append is idempotent by contribution_id."""

    def append(self, contribution: GraphContribution) -> GraphContribution: ...

    def get(self, world_id: str, contribution_id: str) -> GraphContribution | None: ...

    def list_for_world(
        self, world_id: str, *, status: ContributionStatus | None = None
    ) -> list[GraphContribution]: ...

    def update_status(
        self,
        world_id: str,
        contribution_id: str,
        status: ContributionStatus,
        *,
        superseded_by: str | None = None,
    ) -> GraphContribution: ...


class ContributionReviewRepository(Protocol):
    """Atomic durable bundle of one finalized contribution review."""

    def finalize(self, state: ContributionReviewState) -> ContributionReviewState: ...

    def get(self, world_id: str, review_id: str) -> ContributionReviewState | None: ...

    def get_for_plan(
        self, world_id: str, source_plan_id: str
    ) -> ContributionReviewState | None: ...


class FinalizedReviewPublicationRepository(Protocol):
    """Atomic terminal publication unit of work.

    The adapter owns review cross-verification, immutable graph revision
    reconciliation, head CAS, and publication-record persistence in one store
    transaction or one shared in-memory lock.
    """

    def publish(
        self,
        command: FinalizedReviewPublicationCommand,
    ) -> FinalizedReviewPublication: ...

    def get(
        self,
        world_id: str,
        operation_id: str,
    ) -> FinalizedReviewPublication | None: ...

    def get_for_review(
        self,
        world_id: str,
        review_id: str,
    ) -> FinalizedReviewPublication | None: ...


class ExistingWorldAdoptionRepository(Protocol):
    """Atomic existing-world adoption unit of work.

    The adapter binds command hashes to the command bundle before any replay,
    pristine-target, or mutation branch. It then owns imported source/history
    persistence, first-revision/head publication, and the terminal receipt in
    one store transaction or one shared in-memory lock. A globally unique
    ``adoption_id`` already claimed by another world is an identity conflict.
    """

    def adopt(self, command: ExistingWorldAdoptionCommandV1) -> ExistingWorldAdoptionReceiptV1: ...

    def get(self, world_id: str, adoption_id: str) -> ExistingWorldAdoptionReceiptV1 | None: ...

    def get_for_world(self, world_id: str) -> ExistingWorldAdoptionReceiptV1 | None: ...


class IdentityDecisionRepository(Protocol):
    """Durable, replayable identity decisions. Append is idempotent by decision_id."""

    def append(self, decision: IdentityDecisionRecord) -> IdentityDecisionRecord: ...

    def get(self, world_id: str, decision_id: str) -> IdentityDecisionRecord | None: ...

    def list_for_world(self, world_id: str) -> list[IdentityDecisionRecord]: ...


class SourceRepository(Protocol):
    """Source identity store. Bodies may live elsewhere; identity never does."""

    def put_artifact(self, artifact: SourceArtifactRecord) -> SourceArtifactRecord: ...

    def get_artifact(self, source_artifact_id: str) -> SourceArtifactRecord | None: ...

    def put_revision(self, revision: SourceRevision) -> SourceRevision: ...

    def get_revision(self, source_revision_id: str) -> SourceRevision | None: ...

    def list_revisions(self, source_artifact_id: str) -> list[SourceRevision]: ...


class RetrievalSessionRepository(Protocol):
    """Turn-scoped, read-only session ledgers. Create is idempotent by session_id."""

    def create(self, session: GraphRetrievalSession) -> GraphRetrievalSession: ...

    def get(self, session_id: str) -> GraphRetrievalSession | None: ...

    def save(self, session: GraphRetrievalSession) -> GraphRetrievalSession: ...


class MindThreadRepository(Protocol):
    """Conversation threads for continuity. Threads are context, never truth.

    v1 policy: caller-private and cross-surface. ``create_thread`` binds
    (thread_id, tenant_id, caller_id, world_id, campaign_id, created_at) and is
    idempotent only for an identical binding — including ``created_at``
    (immutable caller-provided timestamp; drift is conflict). Surface is
    per-turn, not bound. ``append_turn`` is retry-safe by ``turn_id`` and
    enforces caller/world/campaign/tenant correlation.
    """

    def create_thread(
        self,
        thread_id: str,
        *,
        world_id: str,
        campaign_id: str | None,
        caller_id: str,
        tenant_id: str | None,
        created_at: datetime,
    ) -> str: ...

    def append_turn(self, request: MindTurnRequest, response: MindTurnResponse) -> None: ...

    def list_turns(self, thread_id: str) -> list[tuple[MindTurnRequest, MindTurnResponse]]: ...


class SemanticDocumentRepository(Protocol):
    """Provenance-complete store for derived semantic documents.

    Insertions must verify materialization-run compatibility (model, revision,
    dimensions, recipe, world) before accepting a document. New documents may
    be inserted only while the materialization run is ``RUNNING``; exact
    replays remain idempotent after the run becomes terminal.

    ``upsert_batch`` is all-or-nothing: duplicate IDs inside the batch are
    normalized first (identical → one; conflicting → ``IdempotencyConflictError``),
    referenced runs are locked in deterministic ``run_id`` order, every document
    is preflighted, then every genuinely new document is inserted in one commit.
    If any document fails, no new document from that batch remains.

    ``delete_run_documents`` is allowed only for ``FAILED`` or ``SUPERSEDED``
    runs — never for ``RUNNING`` or ``COMPLETED`` (active or otherwise).
    """

    def upsert_batch(self, documents: list[SemanticDocument]) -> int: ...

    def get(self, semantic_document_id: str) -> SemanticDocument | None: ...

    def delete_run_documents(self, materialization_run_id: str) -> int: ...

    def count(self, *, world_id: str | None = None) -> int: ...


class SemanticSearchPort(Protocol):
    """Candidate retrieval over semantic documents. Never evidence; never truth.

    Retrieval is bound to one ``COMPLETED``, non-superseded materialization
    run (explicit ``SemanticQuery.materialization_run_id`` or the world's
    active-run pointer). Failed and superseded runs never contribute candidates.
    """

    def search(self, query: SemanticQuery) -> list[SemanticCandidate]: ...


class EmbeddingRunRepository(Protocol):
    """Materialization run provenance with a monotonic lifecycle state machine.

    ``begin`` is idempotent on immutable creation fields. Lifecycle transitions:
    RUNNING → COMPLETED | FAILED; COMPLETED | FAILED → SUPERSEDED.
    Terminal retries do not rewrite timestamps.

    ``activate`` marks a ``COMPLETED`` run as the world's active retrieval
    profile. Superseding an active run clears the pointer.
    """

    def begin(self, run: EmbeddingRun) -> EmbeddingRun: ...

    def complete(self, run_id: str, *, completed_at: datetime) -> EmbeddingRun: ...

    def fail(self, run_id: str, *, completed_at: datetime) -> EmbeddingRun: ...

    def supersede(self, run_id: str, *, completed_at: datetime) -> EmbeddingRun: ...

    def activate(self, run_id: str) -> EmbeddingRun: ...

    def get_active_run_id(self, world_id: str) -> str | None: ...

    def get(self, run_id: str) -> EmbeddingRun | None: ...
