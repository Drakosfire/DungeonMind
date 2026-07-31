"""Curated Mind Turn fixture loading and idempotent seeding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ...application.graph_snapshot import UnionGraphV1SnapshotReader
from ...application.repositories import (
    EmbeddingRunRepository,
    MindThreadRepository,
    SemanticDocumentRepository,
    SourceRepository,
    WorldGraphRepository,
)
from ...contracts.evidence import SourceArtifact, SourceDomain, SourceRevision, SourceStatus
from ...contracts.graph import PublishRevisionCommand
from ...contracts.semantic import (
    EmbeddingRun,
    SemanticDocument,
    SemanticDocumentKind,
)
from ...contracts.vocabulary import Visibility
from ...domain.canonical import sha256_text
from ...domain.errors import IdempotencyConflictError
from .query_embedding import FixtureQueryEmbeddingProvider

FIXTURE_FILENAME = "curated_mind_turn_v1.json"
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / FIXTURE_FILENAME
)


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
) -> CuratedMindTurnFixture:
    fixture_path = path or DEFAULT_FIXTURE_PATH
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    if raw.get("fixture_version") != "curated_mind_turn_v1":
        raise ValueError(
            f"unexpected fixture_version {raw.get('fixture_version')!r}; "
            "expected 'curated_mind_turn_v1'"
        )
    # Fail closed on graph shape before any write.
    UnionGraphV1SnapshotReader().parse(
        graph_schema=str(raw["graph_schema"]),
        graph_payload=raw["graph_payload"],
    )
    return CuratedMindTurnFixture(raw=raw, path=fixture_path)


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
    run_meta = loaded.raw["embedding_run"]
    run_id = str(run_meta["run_id"])

    threads.create_thread(
        str(binding["thread_id"]),
        world_id=world_id,
        campaign_id=binding.get("campaign_id"),
        caller_id=str(binding["caller_id"]),
        tenant_id=binding.get("tenant_id"),
        created_at=loaded.thread_created_at(),
    )

    head = world_graph.get_head(world_id)
    if head is None:
        published = world_graph.publish_revision(
            PublishRevisionCommand(
                world_id=world_id,
                parent_revision_id=None,
                expected_parent_revision_id=None,
                operation_ids=["op:curated-mind-turn-seed"],
                graph_schema=loaded.graph_schema,
                graph_payload=loaded.graph_payload,
                created_at=created_at,
            )
        )
        revision_id = published.revision_id
        status = "published"
    else:
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
        revision_id = head.head_revision_id
        status = "reused"

    for artifact in loaded.raw["source_artifacts"]:
        sources.put_artifact(
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
    for revision in loaded.raw["source_revisions"]:
        sources.put_revision(
            SourceRevision(
                source_revision_id=str(revision["source_revision_id"]),
                source_artifact_id=str(revision["source_artifact_id"]),
                content_sha256=str(revision["content_sha256"]),
                body_storage=revision.get("body_storage") or "external",  # type: ignore[arg-type]
                locator=revision.get("locator"),
                created_at=created_at,
            )
        )

    existing_run = embedding_runs.get(run_id)
    if existing_run is None:
        embedding_runs.begin(
            EmbeddingRun(
                run_id=run_id,
                embedding_model=str(run_meta["embedding_model"]),
                embedding_model_revision=str(run_meta["embedding_model_revision"]),
                embedding_dimensions=int(run_meta["embedding_dimensions"]),
                embedding_recipe=str(run_meta["embedding_recipe"]),
                world_id=world_id,
                created_at=created_at,
            )
        )
    docs: list[SemanticDocument] = []
    for entry in loaded.raw["semantic_documents"]:
        content = str(entry["content"])
        embedding = [float(v) for v in entry["embedding"]]
        docs.append(
            SemanticDocument(
                semantic_document_id=str(entry["semantic_document_id"]),
                document_kind=SemanticDocumentKind(str(entry["document_kind"])),
                world_id=world_id,
                campaign_scope=entry.get("campaign_scope"),
                graph_object_id=str(entry["graph_object_id"]),
                graph_revision_id=revision_id,
                visibility=Visibility(str(entry["visibility"])),
                content=content,
                content_sha256=sha256_text(content),
                embedding_model=str(run_meta["embedding_model"]),
                embedding_model_revision=str(run_meta["embedding_model_revision"]),
                embedding_dimensions=int(run_meta["embedding_dimensions"]),
                embedding_recipe=str(run_meta["embedding_recipe"]),
                materialization_run_id=run_id,
                created_at=created_at,
                embedding=embedding,
            )
        )
    # Documents may only insert while RUNNING; exact replays after terminal are OK.
    current = embedding_runs.get(run_id)
    assert current is not None
    if current.status.value == "running":
        semantic_documents.upsert_batch(docs)
        embedding_runs.complete(run_id, completed_at=completed_at)
    else:
        # Idempotent replay of document upserts against a completed run.
        semantic_documents.upsert_batch(docs)
    embedding_runs.activate(run_id)

    return CuratedMindTurnSeedResult(
        world_id=world_id,
        revision_id=revision_id,
        embedding_run_id=run_id,
        thread_id=str(binding["thread_id"]),
        status=status,
    )
