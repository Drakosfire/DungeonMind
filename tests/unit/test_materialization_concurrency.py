"""Deterministic concurrency proofs for the shared materialization UoW lock."""

from __future__ import annotations

import threading
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
from dungeonmind.domain.errors import InvalidLifecycleTransitionError, ScopeResolutionError
from dungeonmind.infrastructure.memory import (
    InMemoryEmbeddingRunRepository,
    InMemorySemanticDocumentRepository,
    InMemorySemanticSearch,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
GRAPH_REV = "rev:" + "ab" * 16
UNIT_VEC = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def _doc(doc_id: str = "sdoc:race", *, run_id: str = "erun:1") -> SemanticDocument:
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


def _begin(runs: InMemoryEmbeddingRunRepository, *, run_id: str = "erun:1") -> None:
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


def test_insert_rejects_when_run_completes_after_running_observe() -> None:
    """Pause after observing RUNNING; complete the run; resume must not insert."""
    runs = InMemoryEmbeddingRunRepository()
    store = InMemorySemanticDocumentRepository(runs)
    _begin(runs)

    observed = threading.Event()
    completed = threading.Event()

    def yield_for_complete() -> None:
        observed.set()
        assert completed.wait(timeout=2.0), "complete thread did not finish"

    runs._concurrency_yield = yield_for_complete

    def do_complete() -> None:
        assert observed.wait(timeout=2.0)
        runs.complete("erun:1", completed_at=NOW)
        completed.set()

    completer = threading.Thread(target=do_complete)
    completer.start()
    with pytest.raises(InvalidLifecycleTransitionError) as exc:
        store.upsert_batch([_doc()])
    completer.join(timeout=2.0)
    assert not completer.is_alive()
    assert exc.value.details["current_status"] == "completed"
    assert store.get("sdoc:race") is None


def test_search_rejects_when_run_superseded_after_completed_resolve() -> None:
    """Pause after resolving COMPLETED; supersede; resume must return no candidates."""
    runs = InMemoryEmbeddingRunRepository()
    store = InMemorySemanticDocumentRepository(runs)
    search = InMemorySemanticSearch(store, runs)
    _begin(runs)
    store.upsert_batch([_doc()])
    runs.complete("erun:1", completed_at=NOW)
    runs.activate("erun:1")

    observed = threading.Event()
    superseded = threading.Event()

    def yield_for_supersede() -> None:
        observed.set()
        assert superseded.wait(timeout=2.0), "supersede thread did not finish"

    runs._concurrency_yield = yield_for_supersede

    def do_supersede() -> None:
        assert observed.wait(timeout=2.0)
        runs.supersede("erun:1", completed_at=NOW)
        superseded.set()

    racer = threading.Thread(target=do_supersede)
    racer.start()
    with pytest.raises(ScopeResolutionError, match="COMPLETED"):
        search.search(
            SemanticQuery(
                world_id="world:demo",
                visibility=Visibility.GM,
                materialization_run_id="erun:1",
                embedding=list(UNIT_VEC),
            )
        )
    racer.join(timeout=2.0)
    assert not racer.is_alive()

    # Control: without a mid-flight supersede, the completed run returns docs.
    runs2 = InMemoryEmbeddingRunRepository()
    store2 = InMemorySemanticDocumentRepository(runs2)
    search2 = InMemorySemanticSearch(store2, runs2)
    _begin(runs2)
    store2.upsert_batch([_doc()])
    runs2.complete("erun:1", completed_at=NOW)
    dense = [
        c.semantic_document_id
        for c in search2.search(
            SemanticQuery(
                world_id="world:demo",
                visibility=Visibility.GM,
                materialization_run_id="erun:1",
                embedding=list(UNIT_VEC),
            )
        )
        if c.channel is CandidateChannel.DENSE
    ]
    assert dense == ["sdoc:race"]
