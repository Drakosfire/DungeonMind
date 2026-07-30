"""End-to-end proof over the curated fixture: publish → exact read → search."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dungeonmind.contracts import (
    CandidateChannel,
    EmbeddingRun,
    SemanticDocument,
    SemanticDocumentKind,
    SemanticQuery,
    SourceArtifact,
    SourceDomain,
    Visibility,
)
from dungeonmind.domain import canonical_sha256, sha256_text
from dungeonmind.infrastructure.memory import (
    InMemoryEmbeddingRunRepository,
    InMemorySemanticDocumentRepository,
    InMemorySemanticSearch,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)

from ..conftest import FIXED_NOW, make_publish

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "curated_world_v1.json"


@pytest.fixture
def fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _to_document(entry: dict[str, object], *, graph_revision_id: str) -> SemanticDocument:
    content = str(entry["content"])
    embedding = [float(v) for v in entry["embedding"]]  # type: ignore[index]
    return SemanticDocument(
        semantic_document_id=str(entry["semantic_document_id"]),
        document_kind=SemanticDocumentKind(str(entry["document_kind"])),
        world_id="world:demo-atlas",
        campaign_scope=entry["campaign_scope"],  # type: ignore[arg-type]
        graph_object_id=str(entry["graph_object_id"]),
        graph_revision_id=graph_revision_id,
        visibility=Visibility(str(entry["visibility"])),
        content=content,
        content_sha256=sha256_text(content),
        embedding_model="fixture-8dim",
        embedding_model_revision="v1",
        embedding_dimensions=len(embedding),
        embedding_recipe="fixture-raw",
        materialization_run_id="erun:fixture-1",
        created_at=datetime(2026, 7, 29, tzinfo=UTC),
        embedding=embedding,
    )


def test_publish_read_and_search(fixture: dict[str, object]) -> None:
    world_repo = InMemoryWorldGraphRepository()
    payload = fixture["graph_payload"]
    envelope = world_repo.publish_revision(
        make_publish(
            world_id=str(fixture["world_id"]),
            payload=payload,  # type: ignore[arg-type]
            created_at=FIXED_NOW,
        )
    )

    head = world_repo.get_head(str(fixture["world_id"]))
    assert head is not None and head.head_revision_id == envelope.revision_id

    stored = world_repo.get_revision(str(fixture["world_id"]), envelope.revision_id)
    assert stored is not None
    assert stored.graph_payload == payload
    assert stored.revision.graph_payload_sha256 == canonical_sha256(payload)

    source_repo = InMemorySourceRepository()
    for artifact in fixture["source_artifacts"]:  # type: ignore[union-attr]
        source_repo.put_artifact(
            SourceArtifact(
                source_artifact_id=artifact["source_artifact_id"],
                source_domain=SourceDomain(artifact["source_domain"]),
                world_id=artifact["world_id"],
                created_at=FIXED_NOW,
            )
        )
    assert source_repo.get_artifact("src:atlas-notes") is not None

    run_repo = InMemoryEmbeddingRunRepository()
    run_repo.begin(
        EmbeddingRun(
            run_id="erun:fixture-1",
            embedding_model="fixture-8dim",
            embedding_model_revision="v1",
            embedding_dimensions=8,
            embedding_recipe="fixture-raw",
            world_id=str(fixture["world_id"]),
            created_at=FIXED_NOW,
        )
    )
    doc_repo = InMemorySemanticDocumentRepository(run_repo)
    docs = [
        _to_document(entry, graph_revision_id=envelope.revision_id)
        for entry in fixture["semantic_documents"]  # type: ignore[union-attr]
    ]
    assert doc_repo.upsert_batch(docs) == len(docs)

    search = InMemorySemanticSearch(doc_repo)
    for query in fixture["queries"]:  # type: ignore[union-attr]
        results = search.search(
            SemanticQuery(
                world_id=str(fixture["world_id"]),
                visibility=Visibility.GM,
                embedding=[float(v) for v in query["embedding"]],
            )
        )
        dense = [c for c in results if c.channel is CandidateChannel.DENSE]
        assert dense[0].semantic_document_id == query["expect_dense_first"], query["name"]

    player_results = search.search(
        SemanticQuery(
            world_id=str(fixture["world_id"]),
            campaign_scope="camp:demo",
            visibility=Visibility.PLAYER,
            embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
    )
    assert [c.semantic_document_id for c in player_results] == ["sdoc:rumor-tide-courts"]

    world_level_player = search.search(
        SemanticQuery(
            world_id=str(fixture["world_id"]),
            visibility=Visibility.PLAYER,
            embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
    )
    assert world_level_player == []  # campaign-scoped rumor must not leak into world reads

    campaign_results = search.search(
        SemanticQuery(
            world_id=str(fixture["world_id"]),
            campaign_scope="camp:demo",
            visibility=Visibility.GM,
            embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
    )
    campaign_ids = {c.semantic_document_id for c in campaign_results}
    assert "sdoc:rumor-tide-courts" in campaign_ids
    assert "sdoc:obj-city-vael" in campaign_ids
