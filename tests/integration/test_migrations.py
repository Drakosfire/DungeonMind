"""Migration and schema presence proofs against live PostgreSQL."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "worlds",
    "campaigns",
    "graph_revisions",
    "world_graph_heads",
    "world_graph_head_events",
    "finalized_review_publications",
    "source_artifacts",
    "source_revisions",
    "evidence_refs",
    "graph_contributions",
    "contribution_reviews",
    "identity_decisions",
    "retrieval_sessions",
    "mind_threads",
    "mind_turns",
    "embedding_runs",
    "active_embedding_runs",
    "semantic_documents",
}


def _replace_db(url: str, dbname: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{dbname}"))


def _admin_url(url: str) -> str:
    # Official postgres image accepts connections to the maintenance DB.
    return _replace_db(url, "postgres")


@pytest.mark.integration
def test_vector_extension_and_schema_tables(db) -> None:
    with db.connect() as conn:
        ext = conn.execute(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        assert ext is not None

        rows = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'dungeonmind'
            """
        ).fetchall()
        names = {row["table_name"] for row in rows}
        missing = EXPECTED_TABLES - names
        assert not missing, f"missing tables: {sorted(missing)}"

        version = conn.execute(
            "SELECT version_num FROM dungeonmind.alembic_version"
        ).fetchone()
        assert version is not None
        assert version["version_num"] == "0003_finalized_review_pubs"

        constraints = conn.execute(
            """
            SELECT pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'dungeonmind.finalized_review_publications'::regclass
            """
        ).fetchall()
        constraint_text = "\n".join(
            row["definition"].replace('"', "") for row in constraints
        )
        assert "PRIMARY KEY (world_id, operation_id)" in constraint_text
        assert "UNIQUE (world_id, review_id)" in constraint_text
        assert "UNIQUE (world_id, published_revision_id)" in constraint_text
        assert "FOREIGN KEY (world_id, reviewed_contribution_id)" in constraint_text
        assert (
            "REFERENCES graph_contributions(world_id, contribution_id)"
            in constraint_text
        )


@pytest.mark.integration
def test_migrate_empty_database_roundtrip(database_url: str) -> None:
    """empty → upgrade → assert → downgrade base → upgrade → smoke publish."""
    psycopg = pytest.importorskip("psycopg")
    from tests.conftest import make_publish

    dbname = f"dm_mig_{uuid.uuid4().hex[:12]}"
    admin = _admin_url(database_url)
    target = _replace_db(database_url, dbname)

    with psycopg.connect(admin, autocommit=True) as conn:
        try:
            conn.execute(f'CREATE DATABASE "{dbname}"')
        except psycopg.Error as exc:
            pytest.skip(f"cannot CREATE DATABASE (need CREATEDB): {exc}")

    env = {**os.environ, "DUNGEONMIND_DATABASE_URL": target}
    try:
        for args in (
            ["upgrade", "head"],
            ["downgrade", "base"],
            ["upgrade", "head"],
        ):
            result = subprocess.run(
                [sys.executable, "-m", "alembic", *args],
                cwd=REPO_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"alembic {' '.join(args)} failed:\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

        from dungeonmind.infrastructure.postgres import (
            PostgresDatabase,
            PostgresWorldGraphRepository,
        )

        database = PostgresDatabase(target)
        with database.connect() as conn:
            version = conn.execute(
                "SELECT version_num FROM dungeonmind.alembic_version"
            ).fetchone()
            assert version["version_num"] == "0003_finalized_review_pubs"
            tables = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM information_schema.tables
                WHERE table_schema = 'dungeonmind'
                  AND table_name = ANY(%s)
                """,
                (list(EXPECTED_TABLES),),
            ).fetchone()
            assert tables["n"] == len(EXPECTED_TABLES)

        graph = PostgresWorldGraphRepository(database)
        envelope = graph.publish_revision(make_publish(world_id="world:mig-smoke"))
        assert graph.get_head("world:mig-smoke").head_revision_id == envelope.revision_id  # type: ignore[union-attr]
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (dbname,),
            )
            conn.execute(f'DROP DATABASE IF EXISTS "{dbname}"')