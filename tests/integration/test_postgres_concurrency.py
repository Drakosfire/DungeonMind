"""Real multi-connection races against PostgreSQL adapters."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

import pytest

from dungeonmind.contracts import (
    Admissibility,
    CallerScope,
    ContributionSourceKind,
    EmbeddingRun,
    GraphContribution,
    MindTurnRequest,
    MindTurnResponse,
    SemanticDocument,
    SemanticDocumentKind,
    SemanticQuery,
    SurfaceContext,
    Visibility,
)
from dungeonmind.domain.errors import (
    IdempotencyConflictError,
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


def _wait_for_postgres_lock_wait(database_url: str, *, timeout: float = 5.0) -> None:
    """Poll until another backend is waiting on a Lock (FOR UPDATE contention)."""
    from dungeonmind.infrastructure.postgres import PostgresDatabase

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with PostgresDatabase(database_url).connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
                  AND wait_event_type = 'Lock'
                """
            ).fetchone()
            if row is not None and int(row["n"]) >= 1:
                return
        time.sleep(0.01)
    raise AssertionError("PostgreSQL lock wait was not observed before timeout")


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
    """Pause after FOR UPDATE + RUNNING observe; prove complete blocks until insert ends."""
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

    observed = threading.Event()
    before_complete_lock = threading.Event()
    complete_finished = threading.Event()
    outcomes: list[str] = []
    timestamps: dict[str, float] = {}

    def after_observe() -> None:
        observed.set()
        assert before_complete_lock.wait(timeout=5), "complete did not reach FOR UPDATE"
        # Prove the competitor is blocked in PostgreSQL, not merely descheduled.
        _wait_for_postgres_lock_wait(migrated_database)
        assert not complete_finished.is_set(), (
            "complete finished while insert still held the run lock — "
            "would allow an invalid insert-after-complete linearization"
        )

    docs_a._after_run_lock_observe = after_observe
    runs_b._before_run_lock = before_complete_lock.set

    def do_insert() -> None:
        try:
            docs_a.upsert_batch([_doc("sdoc:late")])
            outcomes.append("inserted")
            timestamps["insert"] = time.monotonic()
        except InvalidLifecycleTransitionError:
            outcomes.append("rejected")
            timestamps["insert"] = time.monotonic()

    def do_complete() -> None:
        assert observed.wait(timeout=5)
        # Blocks here on the run row lock until insert commits.
        runs_b.complete("erun:race", completed_at=NOW)
        timestamps["complete"] = time.monotonic()
        complete_finished.set()
        outcomes.append("completed")

    t_insert = threading.Thread(target=do_insert)
    t_complete = threading.Thread(target=do_complete)
    t_insert.start()
    t_complete.start()
    t_insert.join(timeout=15)
    t_complete.join(timeout=15)
    assert not t_insert.is_alive() and not t_complete.is_alive()

    assert "inserted" in outcomes
    assert "completed" in outcomes
    assert docs_a.get("sdoc:late") is not None
    assert timestamps["complete"] >= timestamps["insert"]
    status = runs_a.get("erun:race")
    assert status is not None
    assert status.status.value == "completed"


@pytest.mark.integration
def test_insert_rejects_when_complete_wins_first(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresEmbeddingRunRepository,
        PostgresSemanticDocumentRepository,
    )

    del pg
    runs = PostgresEmbeddingRunRepository(PostgresDatabase(migrated_database))
    docs = PostgresSemanticDocumentRepository(PostgresDatabase(migrated_database))
    runs.begin(
        EmbeddingRun(
            run_id="erun:complete-first",
            embedding_model="test-model",
            embedding_model_revision="rev-1",
            embedding_dimensions=8,
            embedding_recipe="raw-v1",
            world_id="world:demo",
            created_at=NOW,
        )
    )
    runs.complete("erun:complete-first", completed_at=NOW)
    with pytest.raises(InvalidLifecycleTransitionError):
        docs.upsert_batch([_doc("sdoc:too-late", run_id="erun:complete-first")])
    assert docs.get("sdoc:too-late") is None


@pytest.mark.integration
def test_search_vs_supersede_race(migrated_database: str, pg) -> None:
    """Pause after COMPLETED resolve under lock; prove supersede waits for snapshot."""
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

    observed = threading.Event()
    before_supersede_lock = threading.Event()
    supersede_finished = threading.Event()
    results: list[tuple[str, object]] = []
    timestamps: dict[str, float] = {}

    def after_observe() -> None:
        observed.set()
        assert before_supersede_lock.wait(timeout=5)
        _wait_for_postgres_lock_wait(db_url)
        assert not supersede_finished.is_set(), (
            "supersede finished while search still held the run lock"
        )

    search._after_run_lock_observe = after_observe
    runs_b._before_run_lock = before_supersede_lock.set

    def do_search() -> None:
        try:
            hits = search.search(
                SemanticQuery(
                    world_id="world:demo",
                    visibility=Visibility.GM,
                    embedding=list(UNIT_VEC),
                )
            )
            results.append(("ok", len(hits)))
            timestamps["search"] = time.monotonic()
        except ScopeResolutionError as exc:
            results.append(("scope", exc))
            timestamps["search"] = time.monotonic()

    def do_supersede() -> None:
        assert observed.wait(timeout=5)
        # Blocks on the run row lock until search commits its snapshot.
        runs_b.supersede("erun:search", completed_at=NOW)
        timestamps["supersede"] = time.monotonic()
        supersede_finished.set()
        results.append(("superseded", None))

    t1 = threading.Thread(target=do_search)
    t2 = threading.Thread(target=do_supersede)
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)
    assert not t1.is_alive() and not t2.is_alive()
    assert any(kind == "ok" for kind, _ in results)
    assert any(kind == "superseded" for kind, _ in results)
    assert timestamps["supersede"] >= timestamps["search"]
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


@pytest.mark.integration
def test_concurrent_exact_contribution_create(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresContributionRepository,
        PostgresDatabase,
    )

    del pg
    a = PostgresContributionRepository(PostgresDatabase(migrated_database))
    b = PostgresContributionRepository(PostgresDatabase(migrated_database))
    contrib = GraphContribution(
        contribution_id="contrib:race-exact",
        world_id="world:demo",
        source_kind=ContributionSourceKind.MANUAL_IMPORT,
        produced_at=NOW,
    )
    barrier = threading.Barrier(2)
    results: list[GraphContribution] = []
    errors: list[BaseException] = []

    def append(repo: PostgresContributionRepository) -> None:
        try:
            barrier.wait(timeout=5)
            results.append(repo.append(contrib))
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=append, args=(a,))
    t2 = threading.Thread(target=append, args=(b,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert errors == []
    assert len(results) == 2
    assert results[0] == results[1] == contrib
    assert a.get("world:demo", "contrib:race-exact") == contrib


@pytest.mark.integration
def test_concurrent_conflicting_contribution_create(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresContributionRepository,
        PostgresDatabase,
    )

    del pg
    a = PostgresContributionRepository(PostgresDatabase(migrated_database))
    b = PostgresContributionRepository(PostgresDatabase(migrated_database))
    left = GraphContribution(
        contribution_id="contrib:race-conflict",
        world_id="world:demo",
        source_kind=ContributionSourceKind.MANUAL_IMPORT,
        produced_at=NOW,
        authored_by="left",
    )
    right = left.model_copy(update={"authored_by": "right"})
    barrier = threading.Barrier(2)
    successes: list[str] = []
    errors: list[BaseException] = []

    def append(repo: PostgresContributionRepository, item: GraphContribution) -> None:
        try:
            barrier.wait(timeout=5)
            repo.append(item)
            successes.append(item.authored_by or "")
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=append, args=(a, left))
    t2 = threading.Thread(target=append, args=(b, right))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], IdempotencyConflictError)
    stored = a.get("world:demo", "contrib:race-conflict")
    assert stored is not None
    assert stored.authored_by == successes[0]


@pytest.mark.integration
def test_concurrent_exact_thread_create(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresMindThreadRepository,
    )

    del pg
    a = PostgresMindThreadRepository(PostgresDatabase(migrated_database))
    b = PostgresMindThreadRepository(PostgresDatabase(migrated_database))
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def create(repo: PostgresMindThreadRepository) -> None:
        try:
            barrier.wait(timeout=5)
            repo.create_thread(
                "thr:race-create",
                world_id="world:demo",
                campaign_id="camp:1",
                caller_id="user:1",
                tenant_id="tenant:a",
                created_at=NOW,
            )
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=create, args=(a,))
    t2 = threading.Thread(target=create, args=(b,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert errors == []


@pytest.mark.integration
def test_concurrent_conflicting_semantic_document_across_runs(
    migrated_database: str, pg
) -> None:
    """Same semantic_document_id under two RUNNING runs → one insert, one conflict."""
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresEmbeddingRunRepository,
        PostgresSemanticDocumentRepository,
    )

    del pg
    runs = PostgresEmbeddingRunRepository(PostgresDatabase(migrated_database))
    docs_a = PostgresSemanticDocumentRepository(PostgresDatabase(migrated_database))
    docs_b = PostgresSemanticDocumentRepository(PostgresDatabase(migrated_database))
    for run_id in ("erun:race-a", "erun:race-b"):
        runs.begin(
            EmbeddingRun(
                run_id=run_id,
                embedding_model="test-model",
                embedding_model_revision="rev-1",
                embedding_dimensions=8,
                embedding_recipe="raw-v1",
                world_id="world:demo",
                created_at=NOW,
            )
        )

    barrier = threading.Barrier(2)
    successes: list[str] = []
    errors: list[BaseException] = []

    def upsert(repo: PostgresSemanticDocumentRepository, run_id: str) -> None:
        try:
            barrier.wait(timeout=5)
            count = repo.upsert_batch([_doc("sdoc:cross-run", run_id=run_id)])
            successes.append(run_id if count == 1 else f"{run_id}:noop")
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=upsert, args=(docs_a, "erun:race-a"))
    t2 = threading.Thread(target=upsert, args=(docs_b, "erun:race-b"))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)
    assert not t1.is_alive() and not t2.is_alive()
    assert len(successes) == 1
    assert successes[0] in {"erun:race-a", "erun:race-b"}
    assert len(errors) == 1
    assert isinstance(errors[0], IdempotencyConflictError)
    stored = docs_a.get("sdoc:cross-run")
    assert stored is not None
    assert stored.materialization_run_id == successes[0]


@pytest.mark.integration
def test_concurrent_family_corrected_retry_converges(
    migrated_database: str, pg
) -> None:
    from dungeonmind.application.reviewed_world_initialization import (
        initialize_reviewed_world,
        reviewed_world_initialization_command_sha256,
    )
    from dungeonmind.contracts.evidence import SourceDomain
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresReviewedWorldInitializationRepository,
    )
    from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
        graph_reader,
        make_first_world_family_command,
    )

    del pg  # truncate only
    historical = make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    corrected = make_first_world_family_command(
        evidence_domain=SourceDomain.WORLDBUILDING
    )
    hold_historical = threading.Event()
    historical_locked = threading.Event()

    def hook(stage: str) -> None:
        if stage == "source_records":
            historical_locked.set()
            assert hold_historical.wait(timeout=5)

    historical_repo = PostgresReviewedWorldInitializationRepository(
        PostgresDatabase(migrated_database),
        failure_hook=hook,
    )
    corrected_inner = PostgresReviewedWorldInitializationRepository(
        PostgresDatabase(migrated_database)
    )

    class _CountInitialize:
        def __init__(self) -> None:
            self.initialize_calls = 0

        def get(self, world_id: str, initialization_id: str):
            return corrected_inner.get(world_id, initialization_id)

        def get_for_world(self, world_id: str):
            return corrected_inner.get_for_world(world_id)

        def initialize(self, command, **kwargs):
            self.initialize_calls += 1
            return corrected_inner.initialize(command, **kwargs)

    corrected_repo = _CountInitialize()
    stored_box: list[object] = []
    results: list[object] = []
    errors: list[BaseException] = []

    def write_historical() -> None:
        try:
            stored_box.append(
                initialize_reviewed_world(
                    historical,
                    initialization_repository=historical_repo,
                    graph_reader=graph_reader(),
                )
            )
        except BaseException as exc:
            errors.append(exc)

    def retry_corrected() -> None:
        try:
            results.append(
                initialize_reviewed_world(
                    corrected,
                    initialization_repository=corrected_repo,  # type: ignore[arg-type]
                    graph_reader=graph_reader(),
                )
            )
        except BaseException as exc:
            errors.append(exc)

    t_hist = threading.Thread(target=write_historical)
    t_hist.start()
    assert historical_locked.wait(timeout=5)
    t_corr = threading.Thread(target=retry_corrected)
    t_corr.start()
    _wait_for_postgres_lock_wait(migrated_database)
    hold_historical.set()
    t_hist.join(timeout=15)
    t_corr.join(timeout=15)
    assert not t_hist.is_alive() and not t_corr.is_alive()
    assert errors == []
    assert len(stored_box) == 1
    assert results == stored_box
    assert corrected_repo.initialize_calls == 1
    stored = stored_box[0]
    reloaded = corrected_inner.get_for_world(historical.world_id)
    assert reloaded == stored
    assert reloaded is not None
    assert reloaded.command_sha256 == reviewed_world_initialization_command_sha256(
        historical
    )
