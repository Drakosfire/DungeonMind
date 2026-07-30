"""PostgreSQL integration fixtures. Skip cleanly when DSN is unset."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

TRUNCATE_SQL = """
TRUNCATE TABLE
    dungeonmind.semantic_documents,
    dungeonmind.active_embedding_runs,
    dungeonmind.embedding_runs,
    dungeonmind.mind_turns,
    dungeonmind.mind_threads,
    dungeonmind.retrieval_sessions,
    dungeonmind.identity_decisions,
    dungeonmind.graph_contributions,
    dungeonmind.evidence_refs,
    dungeonmind.source_revisions,
    dungeonmind.source_artifacts,
    dungeonmind.world_graph_head_events,
    dungeonmind.world_graph_heads,
    dungeonmind.graph_revisions,
    dungeonmind.campaigns,
    dungeonmind.worlds
RESTART IDENTITY CASCADE
"""


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: requires a live PostgreSQL+pgvector instance "
        "(opt-in; skipped when DUNGEONMIND_DATABASE_URL is unset)",
    )


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("DUNGEONMIND_DATABASE_URL")
    if not url:
        pytest.skip("DUNGEONMIND_DATABASE_URL unset")
    return url


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> str:
    env = {**os.environ, "DUNGEONMIND_DATABASE_URL": database_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            "alembic upgrade head failed:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return database_url


@pytest.fixture
def db(migrated_database: str):
    from dungeonmind.infrastructure.postgres import PostgresDatabase

    return PostgresDatabase(migrated_database)


@pytest.fixture
def pg(migrated_database: str) -> Iterator:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresRepositoryBundle,
    )

    database = PostgresDatabase(migrated_database)
    with database.connect() as conn:
        conn.execute(TRUNCATE_SQL)
        conn.commit()

    bundle = PostgresRepositoryBundle(database)
    yield bundle

    with database.connect() as conn:
        conn.execute(TRUNCATE_SQL)
        conn.commit()


@pytest.fixture
def repository_bundle(pg):
    from tests.conformance.repository_contract_cases import RepositoryBundle

    return RepositoryBundle(
        world_graph=pg.world_graph,
        contributions=pg.contributions,
        identity=pg.identity_decisions,
        sources=pg.sources,
        sessions=pg.retrieval_sessions,
        threads=pg.threads,
        runs=pg.embedding_runs,
        documents=pg.semantic_documents,
        search=pg.semantic_search,
    )
