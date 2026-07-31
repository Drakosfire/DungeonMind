"""Executable demo host wiring for curated Mind Turn.

Requires ``postgres`` and ``api`` extras. Never seeds on import or startup.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from ..agents.fixture import FixtureGroundedAgentAdapter
from ..application.graph_snapshot import UnionGraphV1SnapshotReader
from ..application.mind_turn import FixedClock, MindTurnService
from ..domain.errors import (
    HeadNotFoundError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    RevisionNotFoundError,
)
from ..infrastructure.fixtures.curated_mind_turn import load_curated_mind_turn_fixture
from ..infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from .api import create_app
from .demo_access import DemoAccessBinding


def _require_database_url() -> str:
    url = os.environ.get("DUNGEONMIND_DATABASE_URL")
    if not url:
        raise PersistenceUnavailableError(
            "DUNGEONMIND_DATABASE_URL is required for the demo host",
        )
    return url


def build_readiness_probe(
    *,
    bundle: PostgresRepositoryBundle,
    world_id: str,
    embedding_run_id: str,
    thread_id: str,
) -> Callable[[], dict[str, Any]]:
    def probe() -> dict[str, Any]:
        try:
            with bundle.database.connect() as conn:
                conn.execute("SELECT 1")
        except Exception as exc:
            raise PersistenceUnavailableError(
                "database connection failed",
                details={"reason": type(exc).__name__},
            ) from exc

        head = bundle.world_graph.get_head(world_id)
        if head is None:
            raise HeadNotFoundError(f"curated world head missing for {world_id!r}")
        stored = bundle.world_graph.get_revision(world_id, head.head_revision_id)
        if stored is None:
            raise RevisionNotFoundError(
                f"curated revision {head.head_revision_id!r} is unreadable"
            )
        # Validate graph payload shape without mutating.
        try:
            UnionGraphV1SnapshotReader().parse(
                graph_schema=stored.revision.graph_schema,
                graph_payload=stored.graph_payload,
            )
        except PersistenceIntegrityError:
            raise
        active = bundle.embedding_runs.get_active_run_id(world_id)
        if active != embedding_run_id:
            raise PersistenceIntegrityError(
                "expected active curated embedding run is not active",
                details={
                    "expected": embedding_run_id,
                    "actual": active,
                },
            )
        run = bundle.embedding_runs.get(embedding_run_id)
        if run is None or run.status.value != "completed":
            raise PersistenceIntegrityError(
                "curated embedding run is missing or not completed",
                details={"embedding_run_id": embedding_run_id},
            )
        try:
            with bundle.database.connect() as conn:
                row = conn.execute(
                    "SELECT 1 AS ok FROM dungeonmind.mind_threads WHERE thread_id = %s",
                    (thread_id,),
                ).fetchone()
        except Exception as exc:
            raise PersistenceUnavailableError(
                "database connection failed during thread readiness check",
                details={"reason": type(exc).__name__},
            ) from exc
        if row is None:
            raise PersistenceIntegrityError(
                "curated demo thread is missing",
                details={"thread_id": thread_id},
            )
        return {
            "status": "ready",
            "world_id": world_id,
            "revision_id": head.head_revision_id,
            "embedding_run_id": embedding_run_id,
        }

    return probe


def create_demo_app() -> FastAPI:
    """Uvicorn factory: ``uvicorn dungeonmind.service.bootstrap:create_demo_app --factory``."""
    fixture = load_curated_mind_turn_fixture()
    binding = DemoAccessBinding.from_mapping(fixture.authorized_demo_binding)
    database = PostgresDatabase(_require_database_url())
    bundle = PostgresRepositoryBundle(database)
    service = MindTurnService(
        world_graph=bundle.world_graph,
        retrieval_sessions=bundle.retrieval_sessions,
        threads=bundle.threads,
        semantic_documents=bundle.semantic_documents,
        semantic_search=bundle.semantic_search,
        sources=bundle.sources,
        graph_reader=UnionGraphV1SnapshotReader(),
        query_embedder=fixture.query_embedder,
        agent_adapter=FixtureGroundedAgentAdapter(),
        clock=FixedClock(fixture.created_at()),
    )
    cors_origin = os.environ.get("DUNGEONMIND_CORS_ORIGIN") or None
    return create_app(
        service=service,
        demo_binding=binding,
        readiness_probe=build_readiness_probe(
            bundle=bundle,
            world_id=fixture.world_id,
            embedding_run_id=str(fixture.raw["embedding_run"]["run_id"]),
            thread_id=str(fixture.authorized_demo_binding["thread_id"]),
        ),
        cors_origin=cors_origin,
    )
