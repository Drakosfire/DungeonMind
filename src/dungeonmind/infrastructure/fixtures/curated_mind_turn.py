"""Curated Mind Turn fixture loading and idempotent seeding."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ...application.graph_snapshot import (
    GraphSnapshotReader,
    VersionedUnionGraphSnapshotReader,
)
from ...application.repositories import (
    EmbeddingRunRepository,
    MindThreadRepository,
    SemanticDocumentRepository,
    SourceRepository,
    WorldGraphRepository,
)
from ...application.semantic_profiles import SemanticProfileRegistry
from ...contracts.evidence import SourceArtifact, SourceDomain, SourceRevision, SourceStatus
from ...contracts.graph import PublishRevisionCommand
from ...contracts.projection import Admissibility
from ...contracts.semantic import (
    EmbeddingRun,
    SemanticDocument,
    SemanticDocumentKind,
)
from ...contracts.vocabulary import Visibility
from ...domain.canonical import canonical_json, canonical_sha256, sha256_text
from ...domain.errors import IdempotencyConflictError
from ...domain.revision_ids import compute_revision_id
from .query_embedding import FixtureQueryEmbeddingProvider

FIXTURE_FILENAME = "curated_mind_turn_v1.json"
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / FIXTURE_FILENAME
)
SEED_OPERATION_IDS = ["op:curated-mind-turn-seed"]


@dataclass(frozen=True)
class CuratedMindTurnSeedResult:
    world_id: str
    revision_id: str
    embedding_run_id: str
    thread_id: str
    status: str


@dataclass(frozen=True)
class CuratedMindTurnFixture:
    raw: dict[str, Any]
    path: Path
    graph_reader: GraphSnapshotReader = field(
        default_factory=VersionedUnionGraphSnapshotReader
    )

    @property
    def world_id(self) -> str:
        return str(self.raw["world_id"])

    @property
    def graph_schema(self) -> str:
        return str(self.raw["graph_schema"])

    @property
    def graph_payload(self) -> dict[str, Any]:
        payload = self.raw["graph_payload"]
        assert isinstance(payload, dict)
        return payload

    @property
    def authorized_demo_binding(self) -> dict[str, Any]:
        binding = self.raw["authorized_demo_binding"]
        assert isinstance(binding, dict)
        return binding

    @property
    def query_embedder(self) -> FixtureQueryEmbeddingProvider:
        vectors = self.raw.get("query_embeddings") or {}
        assert isinstance(vectors, dict)
        return FixtureQueryEmbeddingProvider(
            {str(k): [float(x) for x in v] for k, v in vectors.items()}
        )

    def created_at(self) -> datetime:
        return datetime.fromisoformat(
            str(self.raw["fixed_timestamps"]["created_at"]).replace("Z", "+00:00")
        )

    def completed_at(self) -> datetime:
        return datetime.fromisoformat(
            str(self.raw["fixed_timestamps"]["completed_at"]).replace("Z", "+00:00")
        )

    def thread_created_at(self) -> datetime:
        return datetime.fromisoformat(
            str(self.raw["fixed_timestamps"]["thread_created_at"]).replace("Z", "+00:00")
        )


def load_curated_mind_turn_fixture(
    path: Path | None = None,
    *,
    expected_fixture_version: str = "curated_mind_turn_v1",
    profile_registry: SemanticProfileRegistry | None = None,
    graph_reader: GraphSnapshotReader | None = None,
) -> CuratedMindTurnFixture:
    fixture_path = path or DEFAULT_FIXTURE_PATH
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    if raw.get("fixture_version") != expected_fixture_version:
        raise ValueError(
            f"unexpected fixture_version {raw.get('fixture_version')!r}; "
            f"expected {expected_fixture_version!r}"
        )
    reader = graph_reader or VersionedUnionGraphSnapshotReader(
        profile_registry=profile_registry
    )
    # Fail closed on graph shape (and v3 profile resolution) before any write.
    reader.parse(
        graph_schema=str(raw["graph_schema"]),
        graph_payload=raw["graph_payload"],
    )
    return CuratedMindTurnFixture(raw=raw, path=fixture_path, graph_reader=reader)


def _build_source_artifacts(
    loaded: CuratedMindTurnFixture, *, created_at: datetime
) -> list[SourceArtifact]:
    artifacts: list[SourceArtifact] = []
    for artifact in loaded.raw["source_artifacts"]:
        artifacts.append(
            SourceArtifact(
                source_artifact_id=str(artifact["source_artifact_id"]),
                source_domain=SourceDomain(str(artifact["source_domain"])),
                world_id=str(artifact["world_id"]),
                campaign_id=artifact.get("campaign_id"),
                session_id=artifact.get("session_id"),
                current_revision_id=artifact.get("current_revision_id"),
                authority=str(artifact.get("authority") or "primary"),
                visibility=Visibility(str(artifact.get("visibility") or "gm")),
                status=SourceStatus(str(artifact.get("status") or "active")),
                created_at=created_at,
            )
        )
    return artifacts


def _build_source_revisions(
    loaded: CuratedMindTurnFixture, *, created_at: datetime
) -> list[SourceRevision]:
    revisions: list[SourceRevision] = []
    for revision in loaded.raw["source_revisions"]:
        revisions.append(
            SourceRevision(
                source_revision_id=str(revision["source_revision_id"]),
                source_artifact_id=str(revision["source_artifact_id"]),
                content_sha256=str(revision["content_sha256"]),
                body_storage=revision.get("body_storage") or "external",  # type: ignore[arg-type]
                locator=revision.get("locator"),
                created_at=created_at,
            )
        )
    return revisions


def _build_embedding_run(
    loaded: CuratedMindTurnFixture, *, created_at: datetime
) -> EmbeddingRun:
    run_meta = loaded.raw["embedding_run"]
    return EmbeddingRun(
        run_id=str(run_meta["run_id"]),
        embedding_model=str(run_meta["embedding_model"]),
        embedding_model_revision=str(run_meta["embedding_model_revision"]),
        embedding_dimensions=int(run_meta["embedding_dimensions"]),
        embedding_recipe=str(run_meta["embedding_recipe"]),
        world_id=loaded.world_id,
        created_at=created_at,
    )


def _build_semantic_documents(
    loaded: CuratedMindTurnFixture,
    *,
    revision_id: str,
    run: EmbeddingRun,
    created_at: datetime,
) -> list[SemanticDocument]:
    docs: list[SemanticDocument] = []
    for entry in loaded.raw["semantic_documents"]:
        content = str(entry["content"])
        embedding = [float(v) for v in entry["embedding"]]
        docs.append(
            SemanticDocument(
                semantic_document_id=str(entry["semantic_document_id"]),
                document_kind=SemanticDocumentKind(str(entry["document_kind"])),
                world_id=loaded.world_id,
                campaign_scope=entry.get("campaign_scope"),
                graph_object_id=str(entry["graph_object_id"]),
                graph_revision_id=revision_id,
                visibility=Visibility(str(entry["visibility"])),
                content=content,
                content_sha256=sha256_text(content),
                embedding_model=run.embedding_model,
                embedding_model_revision=run.embedding_model_revision,
                embedding_dimensions=run.embedding_dimensions,
                embedding_recipe=run.embedding_recipe,
                materialization_run_id=run.run_id,
                created_at=created_at,
                embedding=embedding,
            )
        )
    return docs


def _resolve_seed_revision(
    *,
    world_graph: WorldGraphRepository,
    loaded: CuratedMindTurnFixture,
) -> tuple[str, str]:
    """Return ``(revision_id, status)`` after preflighting head compatibility.

    Performs no writes.
    """
    world_id = loaded.world_id
    expected_revision_id = compute_revision_id(
        world_id=world_id,
        parent_revision_id=None,
        operation_ids=SEED_OPERATION_IDS,
        graph_schema=loaded.graph_schema,
        graph_payload_sha256=canonical_sha256(loaded.graph_payload),
    )
    head = world_graph.get_head(world_id)
    if head is None:
        return expected_revision_id, "published"
    stored = world_graph.get_revision(world_id, head.head_revision_id)
    if stored is None:
        raise IdempotencyConflictError(
            f"world {world_id!r} head {head.head_revision_id!r} is unreadable"
        )
    if (
        stored.revision.graph_schema != loaded.graph_schema
        or stored.graph_payload != loaded.graph_payload
    ):
        raise IdempotencyConflictError(
            f"world {world_id!r} already has a different graph head; "
            "refusing to replace or roll back"
        )
    return head.head_revision_id, "reused"



def _preflight_fixture_consistency(
    loaded: CuratedMindTurnFixture,
    *,
    artifacts: list[SourceArtifact],
    revisions: list[SourceRevision],
    run: EmbeddingRun,
    docs: list[SemanticDocument],
) -> None:
    """Validate cross-record fixture consistency before any write."""
    binding = loaded.authorized_demo_binding
    for key in ("caller_id", "world_id", "thread_id", "admissibility", "surface_id"):
        if key not in binding or binding[key] in (None, ""):
            raise ValueError(f"authorized_demo_binding missing required field {key!r}")
    Admissibility(str(binding["admissibility"]))
    if binding.get("world_id") != loaded.world_id:
        raise ValueError("authorized_demo_binding.world_id disagrees with fixture world_id")

    parsed = loaded.graph_reader.parse(
        graph_schema=loaded.graph_schema,
        graph_payload=loaded.graph_payload,
    )
    artifact_ids = {item.source_artifact_id for item in artifacts}
    revision_by_id = {item.source_revision_id: item for item in revisions}
    for revision in revisions:
        if revision.source_artifact_id not in artifact_ids:
            raise ValueError(
                f"source revision {revision.source_revision_id!r} references "
                f"undeclared artifact {revision.source_artifact_id!r}"
            )
    for evidence in parsed.evidence.values():
        if evidence.source_artifact_id not in artifact_ids:
            raise ValueError(
                f"graph evidence {evidence.evidence_ref_id!r} references "
                f"undeclared artifact {evidence.source_artifact_id!r}"
            )
        if evidence.source_revision_id:
            revision = revision_by_id.get(evidence.source_revision_id)
            if revision is None:
                raise ValueError(
                    f"graph evidence {evidence.evidence_ref_id!r} references "
                    f"undeclared source revision {evidence.source_revision_id!r}"
                )
            if revision.source_artifact_id != evidence.source_artifact_id:
                raise ValueError(
                    f"graph evidence {evidence.evidence_ref_id!r} revision "
                    f"{evidence.source_revision_id!r} belongs to a different artifact"
                )
    object_ids = set(parsed.objects)
    for doc in docs:
        if doc.graph_object_id not in object_ids:
            raise ValueError(
                f"semantic document {doc.semantic_document_id!r} references "
                f"unknown graph object {doc.graph_object_id!r}"
            )
        if len(doc.embedding or []) != run.embedding_dimensions:
            raise ValueError(
                f"semantic document {doc.semantic_document_id!r} embedding length "
                f"disagrees with run dimensions {run.embedding_dimensions}"
            )
    for query, vector in (loaded.raw.get("query_embeddings") or {}).items():
        if len(vector) != run.embedding_dimensions:
            raise ValueError(
                f"query embedding for {query!r} length disagrees with run dimensions "
                f"{run.embedding_dimensions}"
            )


def _preflight_existing_record_conflicts(
    *,
    sources: SourceRepository,
    embedding_runs: EmbeddingRunRepository,
    semantic_documents: SemanticDocumentRepository,
    artifacts: list[SourceArtifact],
    revisions: list[SourceRevision],
    run: EmbeddingRun,
    docs: list[SemanticDocument],
) -> None:
    """Reject conflicting durable records before the first seed write."""
    for artifact in artifacts:
        existing = sources.get_artifact(artifact.source_artifact_id)
        if existing is not None and canonical_json(
            existing.model_dump(mode="json")
        ) != canonical_json(artifact.model_dump(mode="json")):
            raise IdempotencyConflictError(
                f"source artifact {artifact.source_artifact_id!r} already exists "
                "with a different payload"
            )
    for revision in revisions:
        existing = sources.get_revision(revision.source_revision_id)
        if existing is not None and canonical_json(
            existing.model_dump(mode="json")
        ) != canonical_json(revision.model_dump(mode="json")):
            raise IdempotencyConflictError(
                f"source revision {revision.source_revision_id!r} already exists "
                "with a different payload"
            )
    existing_run = embedding_runs.get(run.run_id)
    if existing_run is not None:
        comparable = {
            "run_id": existing_run.run_id,
            "embedding_model": existing_run.embedding_model,
            "embedding_model_revision": existing_run.embedding_model_revision,
            "embedding_dimensions": existing_run.embedding_dimensions,
            "embedding_recipe": existing_run.embedding_recipe,
            "world_id": existing_run.world_id,
        }
        expected = {
            "run_id": run.run_id,
            "embedding_model": run.embedding_model,
            "embedding_model_revision": run.embedding_model_revision,
            "embedding_dimensions": run.embedding_dimensions,
            "embedding_recipe": run.embedding_recipe,
            "world_id": run.world_id,
        }
        if comparable != expected:
            raise IdempotencyConflictError(
                f"embedding run {run.run_id!r} already exists with a different identity"
            )
    for doc in docs:
        existing = semantic_documents.get(doc.semantic_document_id)
        if existing is None:
            continue
        # Compare durable identity without raw float drift from pgvector float32.
        existing_identity = {
            "semantic_document_id": existing.semantic_document_id,
            "document_kind": existing.document_kind.value,
            "world_id": existing.world_id,
            "campaign_scope": existing.campaign_scope,
            "graph_object_id": existing.graph_object_id,
            "graph_revision_id": existing.graph_revision_id,
            "visibility": existing.visibility.value,
            "content_sha256": existing.content_sha256,
            "embedding_model": existing.embedding_model,
            "embedding_model_revision": existing.embedding_model_revision,
            "embedding_dimensions": existing.embedding_dimensions,
            "embedding_recipe": existing.embedding_recipe,
            "materialization_run_id": existing.materialization_run_id,
            "embedding_f32": [
                float(struct.unpack("f", struct.pack("f", float(v)))[0])
                for v in (existing.embedding or [])
            ],
        }
        expected_identity = {
            "semantic_document_id": doc.semantic_document_id,
            "document_kind": doc.document_kind.value,
            "world_id": doc.world_id,
            "campaign_scope": doc.campaign_scope,
            "graph_object_id": doc.graph_object_id,
            "graph_revision_id": doc.graph_revision_id,
            "visibility": doc.visibility.value,
            "content_sha256": doc.content_sha256,
            "embedding_model": doc.embedding_model,
            "embedding_model_revision": doc.embedding_model_revision,
            "embedding_dimensions": doc.embedding_dimensions,
            "embedding_recipe": doc.embedding_recipe,
            "materialization_run_id": doc.materialization_run_id,
            "embedding_f32": [
                float(struct.unpack("f", struct.pack("f", float(v)))[0])
                for v in (doc.embedding or [])
            ],
        }
        if existing_identity != expected_identity:
            raise IdempotencyConflictError(
                f"semantic document {doc.semantic_document_id!r} already exists "
                "with a different payload"
            )


def seed_curated_mind_turn(
    *,
    world_graph: WorldGraphRepository,
    sources: SourceRepository,
    embedding_runs: EmbeddingRunRepository,
    semantic_documents: SemanticDocumentRepository,
    threads: MindThreadRepository,
    fixture: CuratedMindTurnFixture | None = None,
) -> CuratedMindTurnSeedResult:
    """Idempotently seed the curated Mind Turn world, run, docs, and thread."""
    loaded = fixture or load_curated_mind_turn_fixture()
    binding = loaded.authorized_demo_binding
    world_id = loaded.world_id
    created_at = loaded.created_at()
    completed_at = loaded.completed_at()
    thread_id = str(binding["thread_id"])

    # Preconstruct/validate every contract model and preflight conflicts first.
    artifacts = _build_source_artifacts(loaded, created_at=created_at)
    revisions = _build_source_revisions(loaded, created_at=created_at)
    run = _build_embedding_run(loaded, created_at=created_at)
    revision_id, status = _resolve_seed_revision(world_graph=world_graph, loaded=loaded)
    docs = _build_semantic_documents(
        loaded,
        revision_id=revision_id,
        run=run,
        created_at=created_at,
    )
    _preflight_fixture_consistency(
        loaded,
        artifacts=artifacts,
        revisions=revisions,
        run=run,
        docs=docs,
    )
    _preflight_existing_record_conflicts(
        sources=sources,
        embedding_runs=embedding_runs,
        semantic_documents=semantic_documents,
        artifacts=artifacts,
        revisions=revisions,
        run=run,
        docs=docs,
    )

    # Writes begin only after validation and conflict preflight succeed.
    threads.create_thread(
        thread_id,
        world_id=world_id,
        campaign_id=binding.get("campaign_id"),
        caller_id=str(binding["caller_id"]),
        tenant_id=binding.get("tenant_id"),
        created_at=loaded.thread_created_at(),
    )

    if status == "published":
        published = world_graph.publish_revision(
            PublishRevisionCommand(
                world_id=world_id,
                parent_revision_id=None,
                expected_parent_revision_id=None,
                operation_ids=list(SEED_OPERATION_IDS),
                graph_schema=loaded.graph_schema,
                graph_payload=loaded.graph_payload,
                created_at=created_at,
            )
        )
        if published.revision_id != revision_id:
            raise IdempotencyConflictError(
                "published revision_id disagreed with precomputed fixture revision",
                details={
                    "expected": revision_id,
                    "actual": published.revision_id,
                },
            )

    for artifact in artifacts:
        sources.put_artifact(artifact)
    for revision in revisions:
        sources.put_revision(revision)

    existing_run = embedding_runs.get(run.run_id)
    if existing_run is None:
        embedding_runs.begin(run)

    current = embedding_runs.get(run.run_id)
    assert current is not None
    if current.status.value == "running":
        semantic_documents.upsert_batch(docs)
        embedding_runs.complete(run.run_id, completed_at=completed_at)
    else:
        semantic_documents.upsert_batch(docs)
    embedding_runs.activate(run.run_id)

    return CuratedMindTurnSeedResult(
        world_id=world_id,
        revision_id=revision_id,
        embedding_run_id=run.run_id,
        thread_id=thread_id,
        status=status,
    )
