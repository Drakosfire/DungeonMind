"""Semantic retrieval contracts (schemas ``dm_semantic_document_v1``,
``dm_embedding_run_v1``).

Semantic documents and their embeddings are derived data: always rebuildable
from durable source and graph records (ADR-0003). Every document carries full
provenance — model identity and revision, recipe, dimensions, materialization
run — and re-embedding creates a new run rather than overwriting provenance.
A similarity score is a candidate-retrieval signal, never factual support.

``EmbeddingRun.completed_at`` is the lifecycle terminal timestamp for every
terminal status (COMPLETED, FAILED, SUPERSEDED), not only successful completion.

Active-materialization semantics (PR A.1):
- New semantic documents may be inserted only while their run is ``RUNNING``.
- Exact document replays remain idempotent after the run becomes terminal.
- Candidate retrieval uses only a ``COMPLETED``, non-superseded run, bound
  either by ``SemanticQuery.materialization_run_id`` or by the world's
  active-run pointer set during query planning.
- Document deletion is allowed only for ``FAILED`` or ``SUPERSEDED`` runs.
- In-memory adapters serialize run transitions, document mutate/delete,
  active-pointer changes, and retrieval eligibility under one materialization
  unit-of-work lock (PostgreSQL reproduces this with transactions / row locks).
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import DungeonMindModel
from .vocabulary import Visibility

SEMANTIC_DOCUMENT_SCHEMA = "dm_semantic_document_v1"
EMBEDDING_RUN_SCHEMA = "dm_embedding_run_v1"


class SemanticDocumentKind(StrEnum):
    SOURCE_CHUNK = "source_chunk"
    GRAPH_OBJECT = "graph_object"
    # assertion embeddings are a named later experiment, not v1.


class EmbeddingRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class EmbeddingRun(DungeonMindModel):
    """Provenance for one materialization of embeddings.

    Immutable creation fields (``run_id``, model identity, recipe, dimensions,
    corpus/projection fingerprints, ``world_id``, ``created_at``) are separate
    from mutable lifecycle (``status``, ``completed_at``).
    """

    schema_version: Literal["dm_embedding_run_v1"] = EMBEDDING_RUN_SCHEMA
    run_id: str
    embedding_model: str
    embedding_model_revision: str
    embedding_dimensions: int = Field(gt=0)
    embedding_recipe: str
    # Fingerprint of the exact corpus/projection embedded, when applicable.
    corpus_fingerprint: str | None = None
    benchmark_projection_id: str | None = None
    world_id: str | None = None
    status: EmbeddingRunStatus = EmbeddingRunStatus.RUNNING
    created_at: datetime
    # Terminal timestamp for COMPLETED / FAILED / SUPERSEDED. Absent while RUNNING.
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def _lifecycle_timestamps(self) -> Self:
        terminal = {
            EmbeddingRunStatus.COMPLETED,
            EmbeddingRunStatus.FAILED,
            EmbeddingRunStatus.SUPERSEDED,
        }
        if self.status is EmbeddingRunStatus.RUNNING and self.completed_at is not None:
            raise ValueError("RUNNING embedding runs must not have completed_at")
        if self.status in terminal and self.completed_at is None:
            raise ValueError(
                f"{self.status.value} embedding runs require completed_at "
                "(lifecycle terminal timestamp)"
            )
        return self


class SemanticDocument(DungeonMindModel):
    """One embeddable, retrievable unit with complete provenance.

    Kind-specific immutable input identity:
    - ``SOURCE_CHUNK`` requires ``source_revision_id`` (exact body revision).
    - ``GRAPH_OBJECT`` requires ``graph_object_id`` and ``graph_revision_id``.
    """

    schema_version: Literal["dm_semantic_document_v1"] = SEMANTIC_DOCUMENT_SCHEMA
    semantic_document_id: str
    document_kind: SemanticDocumentKind
    world_id: str
    campaign_scope: str | None = Field(default=None, min_length=1)
    graph_revision_id: str | None = None
    graph_object_id: str | None = None
    assertion_id: str | None = None
    source_artifact_id: str | None = None
    source_revision_id: str | None = None
    session_id: str | None = None
    visibility: Visibility = Visibility.GM
    content: str
    content_sha256: str
    embedding_model: str
    embedding_model_revision: str
    embedding_dimensions: int = Field(gt=0)
    embedding_recipe: str
    materialization_run_id: str
    created_at: datetime
    # The vector itself: derived data, rebuildable from content + model + recipe.
    # Optional at the contract level so stores can separate row vs. index storage.
    embedding: list[float] | None = None

    @model_validator(mode="after")
    def _kind_and_embedding_invariants(self) -> Self:
        if self.document_kind is SemanticDocumentKind.GRAPH_OBJECT:
            if not self.graph_object_id:
                raise ValueError("graph_object documents require graph_object_id")
            if not self.graph_revision_id:
                raise ValueError("graph_object documents require graph_revision_id")
        if (
            self.document_kind is SemanticDocumentKind.SOURCE_CHUNK
            and not self.source_revision_id
        ):
            raise ValueError(
                "source_chunk documents require source_revision_id "
                "(exact immutable source body identity)"
            )
        if self.embedding is not None and len(self.embedding) != self.embedding_dimensions:
            raise ValueError(
                "embedding_dimensions must equal len(embedding) when embedding is present"
            )
        return self


class SemanticQuery(DungeonMindModel):
    """A bounded, metadata-filtered semantic search request.

    ``visibility`` is required with no default. Absence never means unrestricted
    GM access — callers must state the reader class explicitly.

    ``materialization_run_id`` binds retrieval to one embedding run. When
    omitted, the search port resolves the world's active completed run.
    Failed, superseded, and still-running runs never participate in candidates.
    """

    world_id: str
    campaign_scope: str | None = None
    document_kind: SemanticDocumentKind | None = None
    visibility: Visibility
    graph_revision_id: str | None = None
    # Explicit run binding for query planning; else active-run pointer.
    materialization_run_id: str | None = None
    text: str | None = None
    # Precomputed by the caller's embedding provider; adapters never embed.
    embedding: list[float] | None = None
    top_k: int = Field(default=10, ge=1, le=100)


class CandidateChannel(StrEnum):
    EXACT = "exact"  # explicit ID / alias / name resolution
    LEXICAL = "lexical"  # full-text / BM25-like
    DENSE = "dense"  # vector similarity


class SemanticCandidate(DungeonMindModel):
    """One candidate from one channel. ``score`` is a retrieval signal only."""

    semantic_document_id: str
    channel: CandidateChannel
    rank: int = Field(ge=1)
    score: float
    diagnostics: dict[str, str] = {}
