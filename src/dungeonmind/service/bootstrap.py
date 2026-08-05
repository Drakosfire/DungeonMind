"""Executable demo host wiring for curated Mind Turn.

Requires ``postgres`` and ``api`` extras. Never seeds on import or startup.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from ..agents.fixture import FixtureGroundedAgentAdapter
from ..application.graph_snapshot import (
    GraphSnapshotReader,
    VersionedUnionGraphSnapshotReader,
)
from ..application.mind_turn import FixedClock, MindTurnService
from ..application.semantic_profiles import SemanticProfileRegistry
from ..domain.errors import (
    HeadNotFoundError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    RevisionNotFoundError,
    SemanticProfileIntegrityError,
)
from ..infrastructure.fixtures.curated_mind_turn import load_curated_mind_turn_fixture
from ..infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from ..infrastructure.semantic_profiles import (
    ENV_SEMANTIC_PROFILE_REGISTRY_PATH,
    FilesystemSemanticProfileRegistry,
    StaticSemanticProfileRegistry,
)
from .api import create_app, create_fictional_time_query_app, create_publication_app
from .demo_access import DemoAccessBinding
from .fictional_time_access import FictionalTimeQueryAccessBinding
from .publication_access import PublicationAccessBinding


def _require_database_url() -> str:
    url = os.environ.get("DUNGEONMIND_DATABASE_URL")
    if not url:
        raise PersistenceUnavailableError(
            "DUNGEONMIND_DATABASE_URL is required for the demo host",
        )
    return url


def load_configured_profile_registry() -> SemanticProfileRegistry:
    """Load registry from ``DUNGEONMIND_SEMANTIC_PROFILE_REGISTRY_PATH`` or empty."""
    configured = os.environ.get(ENV_SEMANTIC_PROFILE_REGISTRY_PATH)
    if not configured:
        return StaticSemanticProfileRegistry()
    try:
        return FilesystemSemanticProfileRegistry.from_config_path(Path(configured))
    except SemanticProfileIntegrityError:
        raise
    except OSError as exc:
        # ``from None``: OS errors carry absolute paths in their messages, and
        # startup tracebacks must never surface local filesystem layout.
        raise SemanticProfileIntegrityError(
            "semantic profile registry could not be loaded",
            details={"reason": type(exc).__name__},
        ) from None


def build_configured_graph_reader(
    profile_registry: SemanticProfileRegistry | None = None,
) -> VersionedUnionGraphSnapshotReader:
    """Build the shared versioned graph reader used by service and readiness."""
    registry = (
        profile_registry
        if profile_registry is not None
        else load_configured_profile_registry()
    )
    return VersionedUnionGraphSnapshotReader(profile_registry=registry)


def build_readiness_probe(
    *,
    bundle: PostgresRepositoryBundle,
    world_id: str,
    embedding_run_id: str,
    thread_id: str,
    graph_reader: GraphSnapshotReader | None = None,
) -> Callable[[], dict[str, Any]]:
    reader = graph_reader or VersionedUnionGraphSnapshotReader()

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
        # Validate graph payload shape (and v3 profile) without mutating.
        try:
            reader.parse(
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


class UtcSystemClock:
    """Server-owned timezone-aware publication clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def build_publication_readiness_probe(
    *,
    bundle: PostgresRepositoryBundle,
    world_id: str,
) -> Callable[[], dict[str, Any]]:
    """Check publication infrastructure without reading or mutating world state."""

    if not world_id.strip():
        raise ValueError("publication world must be non-blank")
    required_tables = {
        "contribution_reviews",
        "graph_revisions",
        "world_graph_heads",
        "finalized_review_publications",
    }

    def probe() -> dict[str, Any]:
        try:
            with bundle.database.connect() as conn:
                conn.execute("SELECT 1")
                rows = conn.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                      AND table_name = ANY(%s)
                    """,
                    ("dungeonmind", list(required_tables)),
                ).fetchall()
        except Exception as exc:
            if isinstance(exc, (PersistenceUnavailableError, PersistenceIntegrityError)):
                raise
            raise PersistenceUnavailableError(
                "publication readiness database check failed",
                details={"reason": type(exc).__name__},
            ) from None
        visible_tables = {str(row["table_name"]) for row in rows}
        missing = required_tables - visible_tables
        if missing:
            raise PersistenceIntegrityError(
                "publication readiness tables are unavailable",
                details={"reason": "publication_tables_missing"},
            )
        return {
            "status": "ready",
            "world_id": world_id,
            "publication_schema": "dm_finalized_review_publication_v1",
        }

    return probe


def _require_publication_world() -> str:
    world_id = os.environ.get("DUNGEONMIND_PUBLICATION_WORLD_ID", "")
    if not world_id.strip():
        raise ValueError("DUNGEONMIND_PUBLICATION_WORLD_ID is required")
    return world_id


def _require_publication_token() -> str:
    token = os.environ.get("DUNGEONMIND_PUBLICATION_BEARER_TOKEN", "")
    if not token.strip():
        raise ValueError("DUNGEONMIND_PUBLICATION_BEARER_TOKEN is required")
    return token


def _require_publication_database_url() -> str:
    url = os.environ.get("DUNGEONMIND_DATABASE_URL", "")
    if not url.strip():
        raise PersistenceUnavailableError(
            "publication database configuration is unavailable",
            details={"reason": "database_url_missing"},
        )
    return url


def create_demo_app() -> FastAPI:
    """Uvicorn factory: ``uvicorn dungeonmind.service.bootstrap:create_demo_app --factory``.

    B.1a retry coordination is process-local. Run a single Uvicorn worker for the
    demo host; cross-worker uniqueness relies on repository idempotency only.
    """
    fixture = load_curated_mind_turn_fixture()
    binding = DemoAccessBinding.from_mapping(fixture.authorized_demo_binding)
    database = PostgresDatabase(_require_database_url())
    bundle = PostgresRepositoryBundle(database)
    graph_reader = build_configured_graph_reader()
    service = MindTurnService(
        world_graph=bundle.world_graph,
        retrieval_sessions=bundle.retrieval_sessions,
        threads=bundle.threads,
        semantic_documents=bundle.semantic_documents,
        semantic_search=bundle.semantic_search,
        sources=bundle.sources,
        graph_reader=graph_reader,
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
            graph_reader=graph_reader,
        ),
        cors_origin=cors_origin,
    )


def create_publication_service_app() -> FastAPI:
    """Uvicorn factory for the separate finalized-review publication host."""

    world_id = _require_publication_world()
    access_binding = PublicationAccessBinding.from_secret(
        world_id,
        _require_publication_token(),
    )
    database = PostgresDatabase(_require_publication_database_url())
    bundle = PostgresRepositoryBundle(database)
    graph_reader = build_configured_graph_reader()
    return create_publication_app(
        review_repository=bundle.contribution_reviews,
        world_graph_repository=bundle.world_graph,
        publication_repository=bundle.finalized_review_publications,
        graph_reader=graph_reader,
        clock=UtcSystemClock(),
        access_binding=access_binding,
        readiness_probe=build_publication_readiness_probe(
            bundle=bundle,
            world_id=world_id,
        ),
    )


def build_fictional_time_readiness_probe(
    *,
    bundle: PostgresRepositoryBundle,
    world_id: str,
) -> Callable[[], dict[str, Any]]:
    """Check exact-revision read substrate without requiring a world head."""

    if not world_id.strip():
        raise ValueError("fictional-time world must be non-blank")

    def probe() -> dict[str, Any]:
        try:
            with bundle.database.connect() as conn:
                conn.execute("SELECT 1")
                row = conn.execute(
                    """
                    SELECT 1 AS ok
                    FROM information_schema.tables
                    WHERE table_schema = %s
                      AND table_name = %s
                    """,
                    ("dungeonmind", "graph_revisions"),
                ).fetchone()
        except Exception as exc:
            if isinstance(exc, (PersistenceUnavailableError, PersistenceIntegrityError)):
                raise
            raise PersistenceUnavailableError(
                "fictional-time readiness database check failed",
                details={"reason": type(exc).__name__},
            ) from None
        if row is None:
            raise PersistenceIntegrityError(
                "fictional-time readiness tables are unavailable",
                details={"reason": "graph_revisions_missing"},
            )
        return {
            "status": "ready",
            "world_id": world_id,
            "request_schema": "dm_fictional_time_shadow_query_request_v1",
            "result_schema": "dm_fictional_time_query_result_v1",
        }

    return probe


def _require_fictional_time_world() -> str:
    world_id = os.environ.get("DUNGEONMIND_FICTIONAL_TIME_WORLD_ID", "")
    if not world_id.strip():
        raise ValueError("DUNGEONMIND_FICTIONAL_TIME_WORLD_ID is required")
    return world_id


def _require_fictional_time_token() -> str:
    token = os.environ.get("DUNGEONMIND_FICTIONAL_TIME_BEARER_TOKEN", "")
    if not token.strip():
        raise ValueError("DUNGEONMIND_FICTIONAL_TIME_BEARER_TOKEN is required")
    return token


def create_fictional_time_query_service_app() -> FastAPI:
    """Uvicorn factory for the separate fictional-time shadow query host."""

    world_id = _require_fictional_time_world()
    access_binding = FictionalTimeQueryAccessBinding.from_secret(
        world_id,
        _require_fictional_time_token(),
    )
    database = PostgresDatabase(_require_publication_database_url())
    bundle = PostgresRepositoryBundle(database)
    graph_reader = build_configured_graph_reader()
    return create_fictional_time_query_app(
        world_graph_repository=bundle.world_graph,
        graph_reader=graph_reader,
        access_binding=access_binding,
        readiness_probe=build_fictional_time_readiness_probe(
            bundle=bundle,
            world_id=world_id,
        ),
    )
