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
from datetime import datetime
from typing import TypeVar

from ...contracts.contribution import ContributionStatus, GraphContribution
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
    DocumentNotFoundError,
    IdempotencyConflictError,
    ImmutableRevisionConflictError,
    InvalidLifecycleTransitionError,
    RevisionNotFoundError,
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
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock_for(self, world_id: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(world_id, threading.Lock())

    def get_head(self, world_id: str) -> WorldGraphHead | None:
        head = self._heads.get(world_id)
        return _copy(head) if head is not None else None

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision | None:
        stored = self._revisions.get((world_id, revision_id))
        return _copy(stored) if stored is not None else None

    def publish_revision(self, command: PublishRevisionCommand) -> WorldGraphRevision:
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
        self._lock = threading.Lock()

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
        item = self._items.get((world_id, contribution_id))
        return _copy(item) if item is not None else None

    def list_for_world(
        self, world_id: str, *, status: ContributionStatus | None = None
    ) -> list[GraphContribution]:
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
            updated = existing.model_copy(deep=True)
            updated.status = status
            if superseded_by is not None:
                updated.diagnostics = {**updated.diagnostics, "superseded_by": superseded_by}
            self._items[key] = updated
            return _copy(updated)


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
                for key in ("world_id", "campaign_id", "caller_id", "tenant_id"):
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


class InMemorySemanticDocumentRepository:
    """Requires an embedding-run repository so provenance cannot drift."""

    def __init__(self, embedding_runs: "InMemoryEmbeddingRunRepository") -> None:
        self._docs: dict[str, SemanticDocument] = {}
        self._runs = embedding_runs
        self._lock = threading.Lock()

    def _assert_run_compatible(self, doc: SemanticDocument) -> None:
        run = self._runs.get(doc.materialization_run_id)
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

    def upsert_batch(self, documents: list[SemanticDocument]) -> int:
        stored = 0
        with self._lock:
            for doc in documents:
                self._assert_run_compatible(doc)
                existing = self._docs.get(doc.semantic_document_id)
                if existing is not None:
                    if _fingerprint(existing) != _fingerprint(doc):
                        raise IdempotencyConflictError(
                            f"semantic document {doc.semantic_document_id!r} re-ingested with "
                            "different payload; re-embedding must create a new run and new "
                            "document ids (ADR-0003)"
                        )
                    continue
                self._docs[doc.semantic_document_id] = _copy(doc)
                stored += 1
        return stored

    def get(self, semantic_document_id: str) -> SemanticDocument | None:
        item = self._docs.get(semantic_document_id)
        return _copy(item) if item is not None else None

    def delete_run_documents(self, materialization_run_id: str) -> int:
        with self._lock:
            doomed = [
                doc_id
                for doc_id, doc in self._docs.items()
                if doc.materialization_run_id == materialization_run_id
            ]
            for doc_id in doomed:
                del self._docs[doc_id]
            return len(doomed)

    def count(self, *, world_id: str | None = None) -> int:
        if world_id is None:
            return len(self._docs)
        return sum(1 for doc in self._docs.values() if doc.world_id == world_id)

    def list_ids(self) -> list[str]:
        """Memory-adapter helper (not part of the port): all document ids, sorted."""
        return sorted(self._docs)


class InMemoryEmbeddingRunRepository:
    """Monotonic lifecycle: RUNNING→COMPLETED|FAILED; COMPLETED|FAILED→SUPERSEDED."""

    def __init__(self) -> None:
        self._runs: dict[str, EmbeddingRun] = {}
        self._lock = threading.Lock()

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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
            return _copy(updated)

    def get(self, run_id: str) -> EmbeddingRun | None:
        item = self._runs.get(run_id)
        return _copy(item) if item is not None else None


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
    - a campaign-scoped query sees that campaign's docs plus world-universal docs;
      a world-level query (no campaign_scope) sees only world-universal docs.
    - ``visibility`` is required: ``player`` sees player docs only; ``gm`` sees all.
    """

    def __init__(self, documents: InMemorySemanticDocumentRepository) -> None:
        self._documents = documents

    def _eligible(self, query: SemanticQuery) -> list[SemanticDocument]:
        result: list[SemanticDocument] = []
        for doc_id in self._documents.list_ids():
            doc = self._documents.get(doc_id)
            if doc is None:  # pragma: no cover - defensive
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
        docs = self._eligible(query)
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
                    lexical.append((doc.semantic_document_id, overlap / len(query_tokens)))
            candidates.extend(
                self._ranked(lexical, CandidateChannel.LEXICAL, query.top_k)
            )

        if query.embedding:
            dense = [
                (doc.semantic_document_id, _cosine(query.embedding, doc.embedding))
                for doc in docs
                if doc.embedding is not None and len(doc.embedding) == len(query.embedding)
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
