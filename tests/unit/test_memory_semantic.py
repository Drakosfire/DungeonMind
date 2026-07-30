"""Semantic document provenance, filter semantics, and channel behavior."""

from datetime import UTC, datetime

import pytest

from dungeonmind.contracts import (
    CandidateChannel,
    EmbeddingRun,
    SemanticDocument,
    SemanticDocumentKind,
    SemanticQuery,
    Visibility,
)
from dungeonmind.domain.errors import DocumentNotFoundError, IdempotencyConflictError
from dungeonmind.infrastructure.memory import (
    InMemoryEmbeddingRunRepository,
    InMemorySemanticDocumentRepository,
    InMemorySemanticSearch,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
UNIT_VEC = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
GRAPH_REV = "rev:" + "ab" * 16


def _begin_run(
    runs: InMemoryEmbeddingRunRepository,
    *,
    run_id: str = "erun:1",
    dimensions: int = 8,
    model: str = "test-model",
    revision: str = "rev-1",
    recipe: str = "raw-v1",
    world_id: str | None = None,
) -> EmbeddingRun:
    return runs.begin(
        EmbeddingRun(
            run_id=run_id,
            embedding_model=model,
            embedding_model_revision=revision,
            embedding_dimensions=dimensions,
            embedding_recipe=recipe,
            world_id=world_id,
            created_at=NOW,
        )
    )


def make_doc(
    doc_id: str,
    *,
    world_id: str = "world:demo",
    campaign_scope: str | None = None,
    visibility: Visibility = Visibility.GM,
    content: str = "placeholder",
    embedding: list[float] | None = None,
    run_id: str = "erun:1",
    graph_object_id: str | None = None,
    graph_revision_id: str = GRAPH_REV,
    document_kind: SemanticDocumentKind = SemanticDocumentKind.GRAPH_OBJECT,
    source_revision_id: str | None = None,
    source_artifact_id: str | None = None,
    embedding_model: str = "test-model",
    embedding_model_revision: str = "rev-1",
    embedding_recipe: str = "raw-v1",
) -> SemanticDocument:
    vector = embedding or [0.0] * 8
    return SemanticDocument(
        semantic_document_id=doc_id,
        document_kind=document_kind,
        world_id=world_id,
        campaign_scope=campaign_scope,
        graph_object_id=(
            graph_object_id or f"obj:{doc_id}"
            if document_kind is SemanticDocumentKind.GRAPH_OBJECT
            else graph_object_id
        ),
        graph_revision_id=(
            graph_revision_id if document_kind is SemanticDocumentKind.GRAPH_OBJECT else None
        ),
        source_revision_id=source_revision_id,
        source_artifact_id=source_artifact_id,
        visibility=visibility,
        content=content,
        content_sha256=f"{doc_id}-sha256",
        embedding_model=embedding_model,
        embedding_model_revision=embedding_model_revision,
        embedding_dimensions=len(vector),
        embedding_recipe=embedding_recipe,
        materialization_run_id=run_id,
        created_at=NOW,
        embedding=vector,
    )


@pytest.fixture
def runs() -> InMemoryEmbeddingRunRepository:
    repo = InMemoryEmbeddingRunRepository()
    _begin_run(repo)
    return repo


@pytest.fixture
def store(runs: InMemoryEmbeddingRunRepository) -> InMemorySemanticDocumentRepository:
    return InMemorySemanticDocumentRepository(runs)


def test_upsert_idempotent_but_canonical_strict(
    store: InMemorySemanticDocumentRepository,
) -> None:
    doc = make_doc("sdoc:1")
    assert store.upsert_batch([doc]) == 1
    assert store.upsert_batch([doc]) == 0

    changed = doc.model_copy(update={"content_sha256": "different", "content": "changed"})
    with pytest.raises(IdempotencyConflictError):
        store.upsert_batch([changed])

    visibility_drift = doc.model_copy(update={"visibility": Visibility.PLAYER})
    with pytest.raises(IdempotencyConflictError):
        store.upsert_batch([visibility_drift])


def test_reembedding_creates_new_run_not_overwrite(
    runs: InMemoryEmbeddingRunRepository,
    store: InMemorySemanticDocumentRepository,
) -> None:
    _begin_run(runs, run_id="erun:2")
    store.upsert_batch([make_doc("sdoc:1", run_id="erun:1")])
    store.upsert_batch([make_doc("sdoc:2", run_id="erun:2")])
    assert store.count() == 2
    assert store.delete_run_documents("erun:1") == 1
    assert store.get("sdoc:2") is not None


def test_source_chunk_requires_exact_source_revision() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SemanticDocument(
            semantic_document_id="sdoc:chunk",
            document_kind=SemanticDocumentKind.SOURCE_CHUNK,
            world_id="world:demo",
            source_artifact_id="src:1",
            content="chunk",
            content_sha256="ab" * 32,
            embedding_model="test-model",
            embedding_model_revision="rev-1",
            embedding_dimensions=8,
            embedding_recipe="raw-v1",
            materialization_run_id="erun:1",
            created_at=NOW,
        )


def test_source_chunk_with_source_revision_accepted(
    store: InMemorySemanticDocumentRepository,
) -> None:
    doc = SemanticDocument(
        semantic_document_id="sdoc:chunk",
        document_kind=SemanticDocumentKind.SOURCE_CHUNK,
        world_id="world:demo",
        source_revision_id="srev:1",
        source_artifact_id="src:1",
        content="chunk text",
        content_sha256="ab" * 32,
        embedding_model="test-model",
        embedding_model_revision="rev-1",
        embedding_dimensions=8,
        embedding_recipe="raw-v1",
        materialization_run_id="erun:1",
        created_at=NOW,
        embedding=[0.0] * 8,
    )
    assert store.upsert_batch([doc]) == 1


def test_graph_object_without_graph_revision_rejected() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SemanticDocument(
            semantic_document_id="sdoc:1",
            document_kind=SemanticDocumentKind.GRAPH_OBJECT,
            world_id="world:demo",
            graph_object_id="obj:1",
            content="x",
            content_sha256="ab" * 32,
            embedding_model="m",
            embedding_model_revision="r",
            embedding_dimensions=8,
            embedding_recipe="raw",
            materialization_run_id="erun:1",
            created_at=NOW,
        )


def test_mismatched_run_metadata_rejected(
    runs: InMemoryEmbeddingRunRepository,
    store: InMemorySemanticDocumentRepository,
) -> None:
    with pytest.raises(IdempotencyConflictError):
        store.upsert_batch([make_doc("sdoc:1", embedding_model="other-model")])
    with pytest.raises(IdempotencyConflictError):
        store.upsert_batch([make_doc("sdoc:2", embedding_model_revision="other")])
    with pytest.raises(IdempotencyConflictError):
        store.upsert_batch([make_doc("sdoc:3", embedding_recipe="other")])
    with pytest.raises(IdempotencyConflictError):
        store.upsert_batch(
            [
                make_doc(
                    "sdoc:4",
                    embedding=[0.0] * 4,
                )
            ]
        )


def test_missing_run_rejected() -> None:
    runs = InMemoryEmbeddingRunRepository()
    store = InMemorySemanticDocumentRepository(runs)
    with pytest.raises(DocumentNotFoundError):
        store.upsert_batch([make_doc("sdoc:1")])


def test_dense_search_orders_by_cosine(store: InMemorySemanticDocumentRepository) -> None:
    store.upsert_batch(
        [
            make_doc("sdoc:far", embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            make_doc("sdoc:near", embedding=[0.0, 0.95, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ]
    )
    search = InMemorySemanticSearch(store)
    results = search.search(
        SemanticQuery(
            world_id="world:demo",
            visibility=Visibility.GM,
            embedding=[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
    )
    dense = [c for c in results if c.channel is CandidateChannel.DENSE]
    assert [c.semantic_document_id for c in dense] == ["sdoc:near", "sdoc:far"]
    assert dense[0].score > dense[1].score


def test_scope_and_visibility_filters_fail_closed(
    store: InMemorySemanticDocumentRepository,
) -> None:
    store.upsert_batch(
        [
            make_doc("sdoc:universal", content="shared lore", embedding=list(UNIT_VEC)),
            make_doc(
                "sdoc:camp-a", campaign_scope="camp:a", content="alpha lore",
                embedding=list(UNIT_VEC),
            ),
            make_doc(
                "sdoc:camp-b", campaign_scope="camp:b", content="beta lore",
                embedding=list(UNIT_VEC),
            ),
            make_doc(
                "sdoc:player", visibility=Visibility.PLAYER, content="rumor",
                embedding=list(UNIT_VEC),
            ),
            make_doc(
                "sdoc:other-world", world_id="world:other", content="foreign",
                embedding=list(UNIT_VEC),
            ),
        ]
    )
    search = InMemorySemanticSearch(store)

    def dense_ids(query: SemanticQuery) -> list[str]:
        return [
            c.semantic_document_id
            for c in search.search(query)
            if c.channel is CandidateChannel.DENSE
        ]

    world_level = dense_ids(
        SemanticQuery(
            world_id="world:demo", visibility=Visibility.GM, embedding=list(UNIT_VEC)
        )
    )
    assert set(world_level) == {"sdoc:universal", "sdoc:player"}

    campaign_a = dense_ids(
        SemanticQuery(
            world_id="world:demo",
            campaign_scope="camp:a",
            visibility=Visibility.GM,
            embedding=list(UNIT_VEC),
        )
    )
    assert set(campaign_a) == {"sdoc:universal", "sdoc:camp-a", "sdoc:player"}

    player_only = dense_ids(
        SemanticQuery(
            world_id="world:demo", visibility=Visibility.PLAYER, embedding=list(UNIT_VEC)
        )
    )
    assert set(player_only) == {"sdoc:player"}


def test_exact_and_lexical_channels(store: InMemorySemanticDocumentRepository) -> None:
    store.upsert_batch(
        [
            make_doc("sdoc:astor", content="Mere Astor safeguards the Sun Ledger"),
            make_doc("sdoc:vael", content="The city of Vael"),
        ]
    )
    search = InMemorySemanticSearch(store)
    results = search.search(
        SemanticQuery(
            world_id="world:demo", visibility=Visibility.GM, text="Sun Ledger", top_k=5
        )
    )
    exact = [c for c in results if c.channel is CandidateChannel.EXACT]
    lexical = [c for c in results if c.channel is CandidateChannel.LEXICAL]
    assert [c.semantic_document_id for c in exact] == ["sdoc:astor"]
    assert lexical[0].semantic_document_id == "sdoc:astor"
    assert lexical[0].score == 1.0
