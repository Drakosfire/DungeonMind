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

from collections.abc import Callable
from datetime import datetime
from typing import Protocol, TypeAlias

from ..contracts.contribution import (
    ContributionStatus,
    GraphContribution,
    GraphContributionV2,
)
from ..contracts.contribution_review import (
    ContributionReviewState,
)
from ..contracts.contribution_review_v2 import (
    ContributionReviewStateV2,
)
from ..contracts.evidence import SourceArtifactRecord, SourceRevision
from ..contracts.existing_world_adoption import (
    ExistingWorldAdoptionCommandV1,
    ExistingWorldAdoptionCommandV2,
    ExistingWorldAdoptionReceiptV1,
    ExistingWorldAdoptionReceiptV2,
    ExistingWorldAdoptionReceiptV3,
    ExistingWorldAdoptionReceiptV4,
)
from ..contracts.existing_world_adoption_repair import (
    ExistingWorldAdoptionSourceClassificationRepairCommandV1,
)
from ..contracts.graph import (
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from ..contracts.identity import IdentityDecisionRecord, IdentityDecisionRecordV2
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

DurableGraphContribution: TypeAlias = GraphContribution | GraphContributionV2
DurableIdentityDecision: TypeAlias = IdentityDecisionRecord | IdentityDecisionRecordV2
DurableContributionReviewState: TypeAlias = (
    ContributionReviewState | ContributionReviewStateV2
)
DurableExistingWorldAdoptionCommand: TypeAlias = (
    ExistingWorldAdoptionCommandV1 | ExistingWorldAdoptionCommandV2
)
DurableExistingWorldAdoptionReceipt: TypeAlias = (
    ExistingWorldAdoptionReceiptV1
    | ExistingWorldAdoptionReceiptV2
    | ExistingWorldAdoptionReceiptV3
    | ExistingWorldAdoptionReceiptV4
)


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

    def append(self, contribution: DurableGraphContribution) -> DurableGraphContribution: ...

    def get(self, world_id: str, contribution_id: str) -> DurableGraphContribution | None: ...

    def list_for_world(
        self, world_id: str, *, status: ContributionStatus | None = None
    ) -> list[DurableGraphContribution]: ...

    def update_status(
        self,
        world_id: str,
        contribution_id: str,
        status: ContributionStatus,
        *,
        superseded_by: str | None = None,
    ) -> DurableGraphContribution: ...


class ContributionReviewRepository(Protocol):
    """Atomic durable bundle of one finalized contribution review.

    Both review generations are stored: v1 states carry ``GraphContribution``
    payloads for ``dm_union_graph_v3`` reviews; v2 states carry
    ``GraphContributionV2`` payloads for ``dm_union_graph_v6`` reviews.  The
    adapter reconstructs whichever generation the durable record names.
    """

    def finalize(
        self, state: DurableContributionReviewState
    ) -> DurableContributionReviewState: ...

    def get(
        self, world_id: str, review_id: str
    ) -> DurableContributionReviewState | None: ...

    def get_for_plan(
        self, world_id: str, source_plan_id: str
    ) -> DurableContributionReviewState | None: ...


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

    def adopt(
        self, command: DurableExistingWorldAdoptionCommand
    ) -> DurableExistingWorldAdoptionReceipt: ...

    def get(
        self, world_id: str, adoption_id: str
    ) -> DurableExistingWorldAdoptionReceipt | None: ...

    def get_for_world(self, world_id: str) -> DurableExistingWorldAdoptionReceipt | None: ...

    def promote_to_v3_receipt(
        self,
        world_id: str,
        *,
        expected: ExistingWorldAdoptionReceiptV2,
        promoted: ExistingWorldAdoptionReceiptV3,
        current_membership_sha256: Callable[[], str],
    ) -> ExistingWorldAdoptionReceiptV3:
        """Atomically replace one v2 receipt with its v3 membership-checkpoint form.

        Under one serialization boundary that excludes concurrent history
        writers (PostgreSQL: the world row lock plus ``SHARE ROW EXCLUSIVE``
        table locks on the four membership families, because history writers
        commit through independent transactions without the world row lock;
        in-memory: the per-world graph lock plus every membership family
        repository's lock held across the re-proof and swap), the adapter
        re-reads and re-verifies the current receipt, then:

        - current fingerprint-equals ``expected`` and ``promoted`` preserves
          every v2 adoption fact → persist ``promoted`` (only the versioned
          receipt representation changes; no history/graph mutation);
        - current is already v3 and fingerprint-equals ``promoted`` → exact
          no-op success returning the stored receipt;
        - anything else (missing, v1, fingerprint divergence, fact drift) →
          ``PersistenceIntegrityError`` with zero mutation.

        The adapter MUST invoke ``current_membership_sha256()`` inside that
        same boundary — after the locks are held, before the receipt swap —
        and require exact equality with ``promoted.membership_sha256``. A
        mismatch means adopted history changed after the caller's pre-boundary
        proof and raises ``PersistenceIntegrityError``
        (``adoption_promotion_membership_mismatch``) with zero mutation. The
        caller's own pre-boundary check is a fast-fail optimization only; this
        in-boundary re-proof is the authoritative equality check, so a writer
        committing in the gap cannot leave a stale checkpoint installed.
        """
        ...

    def repair_source_classification(
        self,
        command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    ) -> ExistingWorldAdoptionReceiptV4:
        """Atomically repair the source classification of one already-adopted world.

        Under one serialization boundary that excludes concurrent history
        writers (PostgreSQL: the world row lock plus ``SHARE ROW EXCLUSIVE``
        table locks on the four membership families), the adapter:

        1. re-reads and fingerprint-verifies the stored adoption receipt;
        2. requires V3 corrupted-fix-forward state or exact V4 replay — no V1/V2;
        3. requires all non-membership V3 adoption facts to match the sealed
           bundle and referenced D_A exactly;
        4. requires the exact adopted graph revision still exists and matches
           receipt schema/payload digest;
        5. loads the exact adopted-member rows using the sealed manifest IDs,
           not "all current world rows" and not Buddy files;
        6. requires every adopted source revision, contribution, and identity
           decision to be fingerprint-equal to its sealed bundle record;
        7. for each adopted source artifact:
           - if not named by the repair intent: current must equal sealed original;
           - if named: current must equal either sealed original or the exact
             derived target artifact;
           - any third state is corruption and aborts;
        8. computes the currently observed adopted-member digest;
        9. for a V3 fix-forward, requires stored ``membership_sha256`` to equal
           that observed current digest. This proves the out-of-band receipt
           rewrite is at least internally bound to the currently observed
           adopted rows; otherwise the incident is more complex than this
           repair and must stop;
        10. requires no requested correction targets a non-adopted artifact.

        Only after all pre-mutation proofs succeed:

        - for each target artifact already equal to the exact effective model:
          no-op;
        - for each target artifact still equal to the sealed original: update
          exactly its full relational identity columns, payload, and record
          fingerprint to the derived target model;
        - do not call a generic mutable SourceArtifact API;
        - do not mutate source revisions, contributions, identity decisions,
          evidence refs, graph revisions, or graph head.

        Then recompute the exact adopted-member effective digest M1 inside the
        same transaction and replace the corrupted V3 receipt with V4:

        - ``V4.membership_sha256`` = M0 from exact sealed bundle
        - ``V4.effective_membership_sha256`` = M1 from exact target adopted
          membership
        - ``V4.membership_manifest`` = exact IDs from sealed bundle
        - ``V4.source_classification_repair`` = exact repair record

        Every v1/v2/v3 adoption fact other than the versioned representation
        must be preserved.

        If the stored receipt is already the exact V4 repair for the same
        sealed bundle and intent, return it with zero writes. If V4 exists but
        repair identity/target differs, fail with idempotency/integrity
        conflict. No second repair is authorized.
        """
        ...


class IdentityDecisionRepository(Protocol):
    """Durable, replayable identity decisions. Append is idempotent by decision_id."""

    def append(self, decision: DurableIdentityDecision) -> DurableIdentityDecision: ...

    def get(self, world_id: str, decision_id: str) -> DurableIdentityDecision | None: ...

    def list_for_world(self, world_id: str) -> list[DurableIdentityDecision]: ...


class SourceRepository(Protocol):
    """Source identity store. Bodies may live elsewhere; identity never does."""

    def put_artifact(self, artifact: SourceArtifactRecord) -> SourceArtifactRecord: ...

    def get_artifact(self, source_artifact_id: str) -> SourceArtifactRecord | None: ...

    def list_artifacts_for_world(self, world_id: str) -> list[SourceArtifactRecord]:
        """Read-only per-world artifact membership enumeration.

        Every returned record passes the adapter's read-time integrity
        verification, same as ``get_artifact``. Ordered by artifact id.
        """
        ...

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
