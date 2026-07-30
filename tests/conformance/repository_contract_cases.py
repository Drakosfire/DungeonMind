"""Shared repository/search contract cases for memory and PostgreSQL adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from dungeonmind.contracts import (
    Admissibility,
    CallerScope,
    CandidateChannel,
    ContributionSourceKind,
    EmbeddingRun,
    EmbeddingRunStatus,
    GraphContribution,
    IdentityDecisionKind,
    IdentityDecisionRecord,
    MindTurnRequest,
    MindTurnResponse,
    SemanticDocument,
    SemanticDocumentKind,
    SemanticQuery,
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SurfaceContext,
    Visibility,
)
from dungeonmind.domain.errors import (
    IdempotencyConflictError,
    InvalidLifecycleTransitionError,
    ScopeResolutionError,
    StaleParentRevisionError,
)
from tests.conftest import FIXED_LATER, FIXED_NOW, WORLD_ID, make_publish

NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
GRAPH_REV = "rev:" + "ab" * 16
UNIT_VEC = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


@dataclass(frozen=True)
class RepositoryBundle:
    world_graph: Any
    contributions: Any
    identity: Any
    sources: Any
    sessions: Any
    threads: Any
    runs: Any
    documents: Any
    search: Any


def _contribution(
    contribution_id: str,
    *,
    world_id: str = WORLD_ID,
    status: str | None = None,
) -> GraphContribution:
    kwargs: dict[str, object] = {
        "contribution_id": contribution_id,
        "world_id": world_id,
        "source_kind": ContributionSourceKind.MANUAL_IMPORT,
        "produced_at": NOW,
    }
    if status is not None:
        from dungeonmind.contracts import ContributionStatus

        kwargs["status"] = ContributionStatus(status)
    return GraphContribution(**kwargs)  # type: ignore[arg-type]


def _begin_run(
    runs: Any,
    *,
    run_id: str = "erun:1",
    world_id: str | None = "world:demo",
    dimensions: int = 8,
) -> EmbeddingRun:
    return runs.begin(
        EmbeddingRun(
            run_id=run_id,
            embedding_model="test-model",
            embedding_model_revision="rev-1",
            embedding_dimensions=dimensions,
            embedding_recipe="raw-v1",
            world_id=world_id,
            created_at=NOW,
        )
    )


def _make_doc(
    doc_id: str,
    *,
    world_id: str = "world:demo",
    campaign_scope: str | None = None,
    visibility: Visibility = Visibility.GM,
    content: str = "placeholder",
    embedding: list[float] | None = None,
    run_id: str = "erun:1",
    embedding_model: str = "test-model",
    embedding_model_revision: str = "rev-1",
    embedding_recipe: str = "raw-v1",
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
        embedding_model=embedding_model,
        embedding_model_revision=embedding_model_revision,
        embedding_dimensions=len(vector),
        embedding_recipe=embedding_recipe,
        materialization_run_id=run_id,
        created_at=NOW,
        embedding=vector,
    )


def _thread_request(
    *,
    thread_id: str = "thr:1",
    world_id: str = "world:demo",
    campaign_id: str | None = "camp:1",
    tenant_id: str | None = "tenant:a",
    caller_id: str = "user:1",
    request_id: str = "req:1",
    surface_id: str = "surface:plan",
) -> MindTurnRequest:
    return MindTurnRequest(
        request_id=request_id,
        thread_id=thread_id,
        caller_scope=CallerScope(caller_id=caller_id, tenant_id=tenant_id),
        world_id=world_id,
        campaign_id=campaign_id,
        admissibility=Admissibility.GM,
        surface_context=SurfaceContext(surface_id=surface_id),
        message="hello",
    )


def _thread_response(
    request: MindTurnRequest, *, turn_id: str = "turn:1"
) -> MindTurnResponse:
    return MindTurnResponse(
        request_id=request.request_id,
        turn_id=turn_id,
        thread_id=request.thread_id,
        world_id=request.world_id,
        campaign_id=request.campaign_id,
        revision_id=GRAPH_REV,
        answer="ok",
    )


def exact_replay_contribution(bundle: RepositoryBundle) -> None:
    contrib = _contribution("contrib:exact")
    first = bundle.contributions.append(contrib)
    second = bundle.contributions.append(contrib)
    assert first == second
    assert bundle.contributions.get(WORLD_ID, "contrib:exact") == contrib


def conflicting_replay_contribution(bundle: RepositoryBundle) -> None:
    contrib = _contribution("contrib:conflict")
    bundle.contributions.append(contrib)
    with pytest.raises(IdempotencyConflictError):
        bundle.contributions.append(
            contrib.model_copy(update={"authored_by": "other"})
        )


def unknown_graph_head_returns_none(bundle: RepositoryBundle) -> None:
    assert bundle.world_graph.get_head("world:does-not-exist") is None
    assert (
        bundle.world_graph.get_revision("world:does-not-exist", "rev:missing") is None
    )


def list_contributions_ordered_by_id(bundle: RepositoryBundle) -> None:
    for cid in ("contrib:c", "contrib:a", "contrib:b"):
        bundle.contributions.append(_contribution(cid))
    listed = bundle.contributions.list_for_world(WORLD_ID)
    assert [c.contribution_id for c in listed] == [
        "contrib:a",
        "contrib:b",
        "contrib:c",
    ]


def thread_binding_and_created_at(bundle: RepositoryBundle) -> None:
    bundle.threads.create_thread(
        "thr:bind",
        world_id="world:demo",
        campaign_id="camp:1",
        caller_id="user:1",
        tenant_id="tenant:a",
        created_at=NOW,
    )
    bundle.threads.create_thread(
        "thr:bind",
        world_id="world:demo",
        campaign_id="camp:1",
        caller_id="user:1",
        tenant_id="tenant:a",
        created_at=NOW,
    )
    with pytest.raises(IdempotencyConflictError):
        bundle.threads.create_thread(
            "thr:bind",
            world_id="world:demo",
            campaign_id="camp:1",
            caller_id="user:1",
            tenant_id="tenant:a",
            created_at=NOW + timedelta(seconds=1),
        )
    with pytest.raises(IdempotencyConflictError):
        bundle.threads.create_thread(
            "thr:bind",
            world_id="world:other",
            campaign_id="camp:1",
            caller_id="user:1",
            tenant_id="tenant:a",
            created_at=NOW,
        )


def thread_append_retry(bundle: RepositoryBundle) -> None:
    bundle.threads.create_thread(
        "thr:retry",
        world_id="world:demo",
        campaign_id="camp:1",
        caller_id="user:1",
        tenant_id="tenant:a",
        created_at=NOW,
    )
    req = _thread_request(thread_id="thr:retry")
    resp = _thread_response(req)
    bundle.threads.append_turn(req, resp)
    bundle.threads.append_turn(req, resp)
    assert len(bundle.threads.list_turns("thr:retry")) == 1
    with pytest.raises(IdempotencyConflictError):
        bundle.threads.append_turn(
            req, resp.model_copy(update={"answer": "different"})
        )


def embedding_lifecycle_monotonic(bundle: RepositoryBundle) -> None:
    run = _begin_run(bundle.runs, run_id="erun:life", world_id="world:demo")
    assert run.status is EmbeddingRunStatus.RUNNING
    assert bundle.runs.begin(run).status is EmbeddingRunStatus.RUNNING

    completed = bundle.runs.complete("erun:life", completed_at=NOW)
    assert completed.status is EmbeddingRunStatus.COMPLETED
    again = bundle.runs.complete("erun:life", completed_at=LATER)
    assert again.completed_at == NOW

    with pytest.raises(InvalidLifecycleTransitionError):
        bundle.runs.fail("erun:life", completed_at=LATER)

    superseded = bundle.runs.supersede("erun:life", completed_at=LATER)
    assert superseded.status is EmbeddingRunStatus.SUPERSEDED

    _begin_run(bundle.runs, run_id="erun:fail-path", world_id="world:demo")
    failed = bundle.runs.fail("erun:fail-path", completed_at=NOW)
    assert failed.status is EmbeddingRunStatus.FAILED
    assert bundle.runs.fail("erun:fail-path", completed_at=LATER).completed_at == NOW


def semantic_batch_atomicity(bundle: RepositoryBundle) -> None:
    _begin_run(bundle.runs, run_id="erun:batch", world_id="world:demo")
    existing = _make_doc("sdoc:existing", run_id="erun:batch", content="kept")
    assert bundle.documents.upsert_batch([existing]) == 1

    new_doc = _make_doc("sdoc:new-a", run_id="erun:batch", content="should not stick")
    conflicting = existing.model_copy(
        update={"content": "changed", "content_sha256": "different-sha"}
    )
    with pytest.raises(IdempotencyConflictError):
        bundle.documents.upsert_batch([new_doc, conflicting])

    assert bundle.documents.get("sdoc:new-a") is None
    assert bundle.documents.get("sdoc:existing") is not None
    assert bundle.documents.get("sdoc:existing").content == "kept"  # type: ignore[union-attr]


def semantic_batch_duplicate_ids(bundle: RepositoryBundle) -> None:
    """Duplicate IDs in one batch: identical collapse; conflicting raise."""
    _begin_run(bundle.runs, run_id="erun:dupes", world_id="world:demo")
    doc = _make_doc("sdoc:dupe", run_id="erun:dupes", content="once")
    assert bundle.documents.upsert_batch([doc, doc]) == 1
    assert bundle.documents.get("sdoc:dupe") is not None

    conflict = doc.model_copy(
        update={"content": "other", "content_sha256": "other-sha"}
    )
    with pytest.raises(IdempotencyConflictError):
        bundle.documents.upsert_batch([doc, conflict])
    assert bundle.documents.get("sdoc:dupe").content == "once"  # type: ignore[union-attr]


def active_run_search_and_supersede(bundle: RepositoryBundle) -> None:
    _begin_run(bundle.runs, run_id="erun:active", world_id="world:demo")
    bundle.documents.upsert_batch(
        [_make_doc("sdoc:live", run_id="erun:active", embedding=list(UNIT_VEC), content="live")]
    )
    bundle.runs.complete("erun:active", completed_at=NOW)
    bundle.runs.activate("erun:active")
    assert bundle.runs.get_active_run_id("world:demo") == "erun:active"

    hits = bundle.search.search(
        SemanticQuery(
            world_id="world:demo",
            visibility=Visibility.GM,
            embedding=list(UNIT_VEC),
        )
    )
    dense = [c for c in hits if c.channel is CandidateChannel.DENSE]
    assert [c.semantic_document_id for c in dense] == ["sdoc:live"]

    bundle.runs.supersede("erun:active", completed_at=LATER)
    assert bundle.runs.get_active_run_id("world:demo") is None
    with pytest.raises(ScopeResolutionError):
        bundle.search.search(
            SemanticQuery(
                world_id="world:demo",
                visibility=Visibility.GM,
                embedding=list(UNIT_VEC),
            )
        )


def scope_visibility_filtering(bundle: RepositoryBundle) -> None:
    _begin_run(bundle.runs, run_id="erun:scope", world_id="world:demo")
    _begin_run(bundle.runs, run_id="erun:other", world_id="world:other")
    bundle.documents.upsert_batch(
        [
            _make_doc(
                "sdoc:universal",
                run_id="erun:scope",
                content="shared lore",
                embedding=list(UNIT_VEC),
            ),
            _make_doc(
                "sdoc:camp-a",
                run_id="erun:scope",
                campaign_scope="camp:a",
                content="alpha lore",
                embedding=list(UNIT_VEC),
            ),
            _make_doc(
                "sdoc:camp-b",
                run_id="erun:scope",
                campaign_scope="camp:b",
                content="beta lore",
                embedding=list(UNIT_VEC),
            ),
            _make_doc(
                "sdoc:player",
                run_id="erun:scope",
                visibility=Visibility.PLAYER,
                content="rumor",
                embedding=list(UNIT_VEC),
            ),
            _make_doc(
                "sdoc:other-world",
                run_id="erun:other",
                world_id="world:other",
                content="foreign",
                embedding=list(UNIT_VEC),
            ),
        ]
    )
    bundle.runs.complete("erun:scope", completed_at=NOW)
    bundle.runs.activate("erun:scope")

    def dense_ids(query: SemanticQuery) -> set[str]:
        return {
            c.semantic_document_id
            for c in bundle.search.search(query)
            if c.channel is CandidateChannel.DENSE
        }

    assert dense_ids(
        SemanticQuery(
            world_id="world:demo", visibility=Visibility.GM, embedding=list(UNIT_VEC)
        )
    ) == {"sdoc:universal", "sdoc:player"}

    assert dense_ids(
        SemanticQuery(
            world_id="world:demo",
            campaign_scope="camp:a",
            visibility=Visibility.GM,
            embedding=list(UNIT_VEC),
        )
    ) == {"sdoc:universal", "sdoc:camp-a", "sdoc:player"}

    assert dense_ids(
        SemanticQuery(
            world_id="world:demo",
            visibility=Visibility.PLAYER,
            embedding=list(UNIT_VEC),
        )
    ) == {"sdoc:player"}


def graph_publish_genesis_and_stale_parent(bundle: RepositoryBundle) -> None:
    rev1 = bundle.world_graph.publish_revision(
        make_publish(payload={"v": 1}, created_at=FIXED_NOW)
    )
    head = bundle.world_graph.get_head(WORLD_ID)
    assert head is not None
    assert head.head_revision_id == rev1.revision_id

    rev2 = bundle.world_graph.publish_revision(
        make_publish(parent=rev1.revision_id, payload={"v": 2}, created_at=FIXED_LATER)
    )
    assert rev2.parent_revision_id == rev1.revision_id
    assert bundle.world_graph.get_head(WORLD_ID).head_revision_id == rev2.revision_id  # type: ignore[union-attr]

    with pytest.raises(StaleParentRevisionError):
        bundle.world_graph.publish_revision(
            make_publish(parent=None, expected=None, payload={"v": 3})
        )
    assert bundle.world_graph.get_head(WORLD_ID).head_revision_id == rev2.revision_id  # type: ignore[union-attr]
    assert bundle.world_graph.get_revision(WORLD_ID, rev1.revision_id) is not None


def identity_and_source_roundtrip(bundle: RepositoryBundle) -> None:
    decision = IdentityDecisionRecord(
        decision_id="idec:1",
        world_id=WORLD_ID,
        decision_kind=IdentityDecisionKind.ALIAS_ADD,
        subject_object_ids=["obj:1"],
        alias="Astor",
        created_at=NOW,
    )
    bundle.identity.append(decision)
    bundle.identity.append(decision)
    with pytest.raises(IdempotencyConflictError):
        bundle.identity.append(decision.model_copy(update={"alias": "Other"}))
    assert bundle.identity.get(WORLD_ID, "idec:1") == decision

    artifact = SourceArtifact(
        source_artifact_id="src:1",
        source_domain=SourceDomain.WORLDBUILDING,
        world_id=WORLD_ID,
        created_at=NOW,
    )
    bundle.sources.put_artifact(artifact)
    revision = SourceRevision(
        source_revision_id="srev:1",
        source_artifact_id="src:1",
        content_sha256="ab" * 32,
        locator="r2://bucket/key",
        created_at=NOW,
    )
    bundle.sources.put_revision(revision)
    assert bundle.sources.get_revision("srev:1") == revision


CASES: list[tuple[str, Callable[[RepositoryBundle], None]]] = [
    ("exact_replay_contribution", exact_replay_contribution),
    ("conflicting_replay_contribution", conflicting_replay_contribution),
    ("unknown_graph_head_returns_none", unknown_graph_head_returns_none),
    ("list_contributions_ordered_by_id", list_contributions_ordered_by_id),
    ("thread_binding_and_created_at", thread_binding_and_created_at),
    ("thread_append_retry", thread_append_retry),
    ("embedding_lifecycle_monotonic", embedding_lifecycle_monotonic),
    ("semantic_batch_atomicity", semantic_batch_atomicity),
    ("semantic_batch_duplicate_ids", semantic_batch_duplicate_ids),
    ("active_run_search_and_supersede", active_run_search_and_supersede),
    ("scope_visibility_filtering", scope_visibility_filtering),
    ("graph_publish_genesis_and_stale_parent", graph_publish_genesis_and_stale_parent),
    ("identity_and_source_roundtrip", identity_and_source_roundtrip),
]
