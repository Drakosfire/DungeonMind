"""Real multi-connection races against PostgreSQL adapters."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest

from dungeonmind.contracts import (
    Admissibility,
    CallerScope,
    EmbeddingRun,
    MindTurnRequest,
    MindTurnResponse,
    SemanticDocument,
    SemanticDocumentKind,
    SemanticQuery,
    SurfaceContext,
    Visibility,
)
from dungeonmind.domain.errors import (
    InvalidLifecycleTransitionError,
    ScopeResolutionError,
    StaleParentRevisionError,
)
from tests.conftest import FIXED_NOW, make_publish

NOW = datetime(2026, 7, 29, tzinfo=UTC)
GRAPH_REV = "rev:" + "ab" * 16
UNIT_VEC = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def _doc(doc_id: str, *, run_id: str = "erun:race") -> SemanticDocument:
    return SemanticDocument(
        semantic_document_id=doc_id,
        document_kind=SemanticDocumentKind.GRAPH_OBJECT,
        world_id="world:demo",
        graph_object_id=f"obj:{doc_id}",
        graph_revision_id=GRAPH_REV,
        visibility=Visibility.GM,
        content="race lore",
        content_sha256=f"{doc_id}-sha",
        embedding_model="test-model",
        embedding_model_revision="rev-1",
        embedding_dimensions=8,
        embedding_recipe="raw-v1",
        materialization_run_id=run_id,
        created_at=NOW,
        embedding=list(UNIT_VEC),
    )


@pytest.mark.integration
def test_two_publishers_same_parent(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresWorldGraphRepository,
    )

    del pg  # truncate only
    world_id = "world:race-publish"
    a = PostgresWorldGraphRepository(PostgresDatabase(migrated_database))
    b = PostgresWorldGraphRepository(PostgresDatabase(migrated_database))

    errors: list[BaseException] = []
    winners: list[str] = []
    barrier = threading.Barrier(2)

    def publish(repo: PostgresWorldGraphRepository, payload: dict) -> None:
        try:
            barrier.wait(timeout=5)
            rev = repo.publish_revision(
                make_publish(world_id=world_id, payload=payload, created_at=FIXED_NOW)
            )
            winners.append(rev.revision_id)
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=publish, args=(a, {"n": 1}))
    t2 = threading.Thread(target=publish, args=(b, {"n": 2}))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert not t1.is_alive() and not t2.is_alive()

    assert len(winners) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], StaleParentRevisionError)
    head = a.get_head(world_id)
    assert head is not None
    assert head.head_revision_id == winners[0]


@pytest.mark.integration
def test_insert_vs_complete_race(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresEmbeddingRunRepository,
        PostgresSemanticDocumentRepository,
    )

    del pg
    runs_a = PostgresEmbeddingRunRepository(PostgresDatabase(migrated_database))
    docs_a = PostgresSemanticDocumentRepository(PostgresDatabase(migrated_database))
    runs_b = PostgresEmbeddingRunRepository(PostgresDatabase(migrated_database))

    runs_a.begin(
        EmbeddingRun(
            run_id="erun:race",
            embedding_model="test-model",
            embedding_model_revision="rev-1",
            embedding_dimensions=8,
            embedding_recipe="raw-v1",
            world_id="world:demo",
            created_at=NOW,
        )
    )
    docs_a.upsert_batch([_doc("sdoc:seed")])

    insert_started = threading.Event()
    outcomes: list[str] = []

    def do_insert() -> None:
        insert_started.set()
        try:
            docs_a.upsert_batch([_doc("sdoc:late")])
            outcomes.append("inserted")
        except InvalidLifecycleTransitionError:
            outcomes.append("rejected")

    def do_complete() -> None:
        assert insert_started.wait(timeout=5)
        try:
            runs_b.complete("erun:race", completed_at=NOW)
            outcomes.append("completed")
        except Exception as exc:
            outcomes.append(f"complete-error:{type(exc).__name__}")

    t_insert = threading.Thread(target=do_insert)
    t_complete = threading.Thread(target=do_complete)
    t_insert.start()
    t_complete.start()
    t_insert.join(timeout=15)
    t_complete.join(timeout=15)
    assert not t_insert.is_alive() and not t_complete.is_alive()

    status = runs_a.get("erun:race")
    assert status is not None
    if docs_a.get("sdoc:late") is not None:
        assert status.status.value == "completed"
    else:
        assert "rejected" in outcomes or status.status.value == "completed"
        if status.status.value == "completed":
            assert docs_a.get("sdoc:late") is None


@pytest.mark.integration
def test_search_vs_supersede_race(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresEmbeddingRunRepository,
        PostgresSemanticDocumentRepository,
        PostgresSemanticSearch,
    )

    del pg
    db_url = migrated_database
    runs = PostgresEmbeddingRunRepository(PostgresDatabase(db_url))
    docs = PostgresSemanticDocumentRepository(PostgresDatabase(db_url))
    search = PostgresSemanticSearch(PostgresDatabase(db_url))
    runs_b = PostgresEmbeddingRunRepository(PostgresDatabase(db_url))

    runs.begin(
        EmbeddingRun(
            run_id="erun:search",
            embedding_model="test-model",
            embedding_model_revision="rev-1",
            embedding_dimensions=8,
            embedding_recipe="raw-v1",
            world_id="world:demo",
            created_at=NOW,
        )
    )
    docs.upsert_batch([_doc("sdoc:search", run_id="erun:search")])
    runs.complete("erun:search", completed_at=NOW)
    runs.activate("erun:search")

    barrier = threading.Barrier(2)
    results: list[object] = []

    def do_search() -> None:
        barrier.wait(timeout=5)
        try:
            hits = search.search(
                SemanticQuery(
                    world_id="world:demo",
                    visibility=Visibility.GM,
                    embedding=list(UNIT_VEC),
                )
            )
            results.append(("ok", len(hits)))
        except ScopeResolutionError as exc:
            results.append(("scope", exc))

    def do_supersede() -> None:
        barrier.wait(timeout=5)
        runs_b.supersede("erun:search", completed_at=NOW)
        results.append(("superseded", None))

    t1 = threading.Thread(target=do_search)
    t2 = threading.Thread(target=do_supersede)
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)
    assert not t1.is_alive() and not t2.is_alive()
    assert any(kind == "superseded" for kind, _ in results)
    assert runs.get_active_run_id("world:demo") is None
    with pytest.raises(ScopeResolutionError):
        search.search(
            SemanticQuery(
                world_id="world:demo",
                visibility=Visibility.GM,
                embedding=list(UNIT_VEC),
            )
        )


@pytest.mark.integration
def test_two_exact_turn_retries_one_row(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresMindThreadRepository,
    )

    del pg
    a = PostgresMindThreadRepository(PostgresDatabase(migrated_database))
    b = PostgresMindThreadRepository(PostgresDatabase(migrated_database))
    thread_id = "thr:race"
    a.create_thread(
        thread_id,
        world_id="world:demo",
        campaign_id="camp:1",
        caller_id="user:1",
        tenant_id="tenant:a",
        created_at=NOW,
    )

    req = MindTurnRequest(
        request_id="req:race",
        thread_id=thread_id,
        caller_scope=CallerScope(caller_id="user:1", tenant_id="tenant:a"),
        world_id="world:demo",
        campaign_id="camp:1",
        admissibility=Admissibility.GM,
        surface_context=SurfaceContext(surface_id="surface:plan"),
        message="hello",
    )
    resp = MindTurnResponse(
        request_id=req.request_id,
        turn_id="turn:race",
        thread_id=thread_id,
        world_id="world:demo",
        campaign_id="camp:1",
        revision_id=GRAPH_REV,
        answer="ok",
    )

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def append(repo: PostgresMindThreadRepository) -> None:
        try:
            barrier.wait(timeout=5)
            repo.append_turn(req, resp)
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=append, args=(a,))
    t2 = threading.Thread(target=append, args=(b,))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)
    assert not t1.is_alive() and not t2.is_alive()
    assert errors == []
    assert len(a.list_turns(thread_id)) == 1
