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


def make_doc(
    doc_id: str,
    *,
    world_id: str = "world:demo",
    campaign_scope: str | None = None,
    visibility: Visibility = Visibility.GM,
    content: str = "placeholder",
    embedding: list[float] | None = None,
    run_id: str = "erun:1",
) -> SemanticDocument:
    vector = embedding or [0.0] * 8
    return SemanticDocument(
        semantic_document_id=doc_id,
        document_kind=SemanticDocumentKind.GRAPH_OBJECT,
        world_id=world_id,
        campaign_scope=campaign_scope,
        visibility=visibility,
        content=content,
        content_sha256=f"{doc_id}-sha256",
        embedding_model="test-model",
        embedding_model_revision="rev-1",
        embedding_dimensions=len(vector),
        embedding_recipe="raw-v1",
        materialization_run_id=run_id,
        created_at=NOW,
        embedding=vector,
    )


@pytest.fixture
def store() -> InMemorySemanticDocumentRepository:
    return InMemorySemanticDocumentRepository()


def test_upsert_idempotent_but_provenance_strict(
    store: InMemorySemanticDocumentRepository,
) -> None:
    doc = make_doc("sdoc:1")
    assert store.upsert_batch([doc]) == 1
    assert store.upsert_batch([doc]) == 0

    changed = doc.model_copy(update={"content_sha256": "different", "content": "changed"})
    with pytest.raises(IdempotencyConflictError):
        store.upsert_batch([changed])


def test_reembedding_creates_new_run_not_overwrite(
    store: InMemorySemanticDocumentRepository,
) -> None:
    store.upsert_batch([make_doc("sdoc:1", run_id="erun:1")])
    store.upsert_batch([make_doc("sdoc:2", run_id="erun:2")])
    assert store.count() == 2
    assert store.delete_run_documents("erun:1") == 1
    assert store.get("sdoc:2") is not None


def test_dense_search_orders_by_cosine(store: InMemorySemanticDocumentRepository) -> None:
    store.upsert_batch(
        [
            make_doc("sdoc:far", embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            make_doc("sdoc:near", embedding=[0.0, 0.95, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ]
    )
    search = InMemorySemanticSearch(store)
    results = search.search(
        SemanticQuery(world_id="world:demo", embedding=[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
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

    world_level = dense_ids(SemanticQuery(world_id="world:demo", embedding=list(UNIT_VEC)))
    assert set(world_level) == {"sdoc:universal", "sdoc:player"}

    campaign_a = dense_ids(
        SemanticQuery(world_id="world:demo", campaign_scope="camp:a", embedding=list(UNIT_VEC))
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
    results = search.search(SemanticQuery(world_id="world:demo", text="Sun Ledger", top_k=5))
    exact = [c for c in results if c.channel is CandidateChannel.EXACT]
    lexical = [c for c in results if c.channel is CandidateChannel.LEXICAL]
    assert [c.semantic_document_id for c in exact] == ["sdoc:astor"]
    assert lexical[0].semantic_document_id == "sdoc:astor"
    assert lexical[0].score == 1.0


def test_embedding_run_lifecycle() -> None:
    runs = InMemoryEmbeddingRunRepository()
    run = EmbeddingRun(
        run_id="erun:1",
        embedding_model="test-model",
        embedding_model_revision="rev-1",
        embedding_dimensions=8,
        embedding_recipe="raw-v1",
        created_at=NOW,
    )
    runs.begin(run)
    assert runs.begin(run).run_id == "erun:1"

    drifted = run.model_copy(update={"embedding_dimensions": 16})
    with pytest.raises(IdempotencyConflictError):
        runs.begin(drifted)

    completed = runs.complete("erun:1", completed_at=NOW)
    assert completed.status.value == "completed"
    with pytest.raises(DocumentNotFoundError):
        runs.complete("erun:missing", completed_at=NOW)
