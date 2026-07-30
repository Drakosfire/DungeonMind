"""PostgreSQL embedding lifecycle, batch atomicity, channels, filters, fusion."""

from __future__ import annotations

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
from dungeonmind.domain.errors import (
    IdempotencyConflictError,
    InvalidLifecycleTransitionError,
    PersistenceIntegrityError,
)
from dungeonmind.domain.fusion import reciprocal_rank_fusion

NOW = datetime(2026, 7, 29, tzinfo=UTC)
GRAPH_REV = "rev:" + "ab" * 16
UNIT_VEC = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def _begin(
    runs,
    *,
    run_id: str = "erun:1",
    world_id: str | None = "world:demo",
) -> None:
    runs.begin(
        EmbeddingRun(
            run_id=run_id,
            embedding_model="test-model",
            embedding_model_revision="rev-1",
            embedding_dimensions=8,
            embedding_recipe="raw-v1",
            world_id=world_id,
            created_at=NOW,
        )
    )


def _doc(
    doc_id: str,
    *,
    run_id: str = "erun:1",
    world_id: str = "world:demo",
    campaign_scope: str | None = None,
    visibility: Visibility = Visibility.GM,
    content: str = "placeholder",
    embedding: list[float] | None = None,
) -> SemanticDocument:
    vector = embedding if embedding is not None else [0.0] * 8
    return SemanticDocument(
        semantic_document_id=doc_id,
        document_kind=SemanticDocumentKind.GRAPH_OBJECT,
        world_id=world_id,
        campaign_scope=campaign_scope,
        graph_object_id=f"obj:{doc_id}",
        graph_revision_id=GRAPH_REV,
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


@pytest.mark.integration
def test_lifecycle_and_deletion_gates(pg) -> None:
    runs, docs = pg.embedding_runs, pg.semantic_documents
    _begin(runs)
    docs.upsert_batch([_doc("sdoc:1")])
    with pytest.raises(InvalidLifecycleTransitionError):
        docs.delete_run_documents("erun:1")
    runs.complete("erun:1", completed_at=NOW)
    with pytest.raises(InvalidLifecycleTransitionError):
        docs.delete_run_documents("erun:1")
    runs.activate("erun:1")
    with pytest.raises(InvalidLifecycleTransitionError):
        docs.delete_run_documents("erun:1")

    _begin(runs, run_id="erun:2")
    docs.upsert_batch([_doc("sdoc:2", run_id="erun:2")])
    runs.fail("erun:2", completed_at=NOW)
    assert docs.delete_run_documents("erun:2") == 1
    assert docs.get("sdoc:2") is None


@pytest.mark.integration
def test_batch_atomicity(pg) -> None:
    runs, docs = pg.embedding_runs, pg.semantic_documents
    _begin(runs, run_id="erun:batch")
    existing = _doc("sdoc:existing", run_id="erun:batch", content="kept")
    assert docs.upsert_batch([existing]) == 1
    new_doc = _doc("sdoc:new-a", run_id="erun:batch", content="nope")
    conflicting = existing.model_copy(
        update={"content": "changed", "content_sha256": "diff"}
    )
    with pytest.raises(IdempotencyConflictError):
        docs.upsert_batch([new_doc, conflicting])
    assert docs.get("sdoc:new-a") is None
    assert docs.get("sdoc:existing").content == "kept"  # type: ignore[union-attr]


@pytest.mark.integration
def test_channels_filters_and_fusion(pg) -> None:
    runs, docs, search = pg.embedding_runs, pg.semantic_documents, pg.semantic_search
    _begin(runs)
    docs.upsert_batch(
        [
            _doc(
                "sdoc:astor",
                content="Mere Astor safeguards the Sun Ledger",
                embedding=[0.0, 0.95, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0],
            ),
            _doc(
                "sdoc:vael",
                content="The city of Vael",
                embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ),
            _doc(
                "sdoc:camp",
                campaign_scope="camp:a",
                content="campaign secret",
                embedding=list(UNIT_VEC),
            ),
            _doc(
                "sdoc:player",
                visibility=Visibility.PLAYER,
                content="player rumor Sun Ledger",
                embedding=list(UNIT_VEC),
            ),
        ]
    )
    runs.complete("erun:1", completed_at=NOW)
    runs.activate("erun:1")

    results = search.search(
        SemanticQuery(
            world_id="world:demo",
            visibility=Visibility.GM,
            text="Sun Ledger",
            embedding=[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            top_k=5,
        )
    )
    exact = [c for c in results if c.channel is CandidateChannel.EXACT]
    lexical = [c for c in results if c.channel is CandidateChannel.LEXICAL]
    dense = [c for c in results if c.channel is CandidateChannel.DENSE]
    assert "sdoc:astor" in {c.semantic_document_id for c in exact}
    assert lexical[0].semantic_document_id in {"sdoc:astor", "sdoc:player"}
    assert dense[0].semantic_document_id == "sdoc:astor"

    world_level = {
        c.semantic_document_id
        for c in search.search(
            SemanticQuery(
                world_id="world:demo",
                visibility=Visibility.GM,
                embedding=list(UNIT_VEC),
            )
        )
        if c.channel is CandidateChannel.DENSE
    }
    assert "sdoc:camp" not in world_level
    assert "sdoc:player" in world_level

    player_only = {
        c.semantic_document_id
        for c in search.search(
            SemanticQuery(
                world_id="world:demo",
                visibility=Visibility.PLAYER,
                embedding=list(UNIT_VEC),
            )
        )
        if c.channel is CandidateChannel.DENSE
    }
    assert player_only == {"sdoc:player"}

    exact_ids = [c.semantic_document_id for c in exact]
    lexical_ids = [c.semantic_document_id for c in lexical]
    dense_ids = [c.semantic_document_id for c in dense]
    fused = reciprocal_rank_fusion([exact_ids, lexical_ids, dense_ids])
    assert fused
    assert fused[0][0] == "sdoc:astor"


@pytest.mark.integration
def test_visibility_column_drift_fails_closed_on_search(
    migrated_database: str, pg
) -> None:
    from dungeonmind.infrastructure.postgres.database import SCHEMA, PostgresDatabase

    runs, docs, search = pg.embedding_runs, pg.semantic_documents, pg.semantic_search
    _begin(runs, run_id="erun:drift")
    docs.upsert_batch(
        [
            _doc(
                "sdoc:gm-only",
                run_id="erun:drift",
                visibility=Visibility.GM,
                content="secret",
                embedding=list(UNIT_VEC),
            )
        ]
    )
    runs.complete("erun:drift", completed_at=NOW)
    runs.activate("erun:drift")

    db = PostgresDatabase(migrated_database)
    with db.transaction() as conn:
        conn.execute(
            f"UPDATE {SCHEMA}.semantic_documents SET visibility = 'player' "
            "WHERE semantic_document_id = %s",
            ("sdoc:gm-only",),
        )

    with pytest.raises(PersistenceIntegrityError, match="visibility"):
        docs.get("sdoc:gm-only")

    with pytest.raises(PersistenceIntegrityError):
        search.search(
            SemanticQuery(
                world_id="world:demo",
                visibility=Visibility.PLAYER,
                embedding=list(UNIT_VEC),
            )
        )


@pytest.mark.integration
def test_batch_duplicate_ids_normalized(pg) -> None:
    runs, docs = pg.embedding_runs, pg.semantic_documents
    _begin(runs, run_id="erun:dup")
    doc = _doc("sdoc:dup", run_id="erun:dup", content="once")
    assert docs.upsert_batch([doc, doc]) == 1
    with pytest.raises(IdempotencyConflictError):
        docs.upsert_batch(
            [
                doc,
                doc.model_copy(update={"content": "other", "content_sha256": "x"}),
            ]
        )
