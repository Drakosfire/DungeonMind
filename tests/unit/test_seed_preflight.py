"""Seed preflight must reject conflicts before creating the demo thread."""

from __future__ import annotations

import pytest

from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.errors import IdempotencyConflictError
from dungeonmind.infrastructure.fixtures.curated_mind_turn import (
    load_curated_mind_turn_fixture,
    seed_curated_mind_turn,
)
from dungeonmind.infrastructure.memory import (
    InMemoryEmbeddingRunRepository,
    InMemoryMindThreadRepository,
    InMemorySemanticDocumentRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)


def test_divergent_head_without_thread_rejects_before_writes() -> None:
    fixture = load_curated_mind_turn_fixture()
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    embedding_runs = InMemoryEmbeddingRunRepository()
    semantic_documents = InMemorySemanticDocumentRepository(embedding_runs)
    threads = InMemoryMindThreadRepository()

    payload = dict(fixture.graph_payload)
    nodes = list(payload["nodes"])
    nodes[0] = {**nodes[0], "label": "Not Vael"}
    payload["nodes"] = nodes
    world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=fixture.world_id,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:foreign-head"],
            graph_schema=fixture.graph_schema,
            graph_payload=payload,
            created_at=fixture.created_at(),
        )
    )

    thread_id = str(fixture.authorized_demo_binding["thread_id"])
    with pytest.raises(IdempotencyConflictError, match="different graph head"):
        seed_curated_mind_turn(
            world_graph=world_graph,
            sources=sources,
            embedding_runs=embedding_runs,
            semantic_documents=semantic_documents,
            threads=threads,
            fixture=fixture,
        )
    assert thread_id not in threads._threads
