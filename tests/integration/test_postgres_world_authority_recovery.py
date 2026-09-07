"""PostgreSQL owning-boundary proofs for Eldyrwild authority recovery preflight."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest
from psycopg import sql

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.world_authority_recovery import (
    ELDYRWILD_D_A,
    ELDYRWILD_D_B,
    REASON_STALE_RECOVERY_POINT,
    REASON_WORLD_MISSING,
    STATUS_NOT_READY,
    STATUS_READY,
    check_world_authority,
)
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
    NOW,
    eldyrwild_graph_reader,
    raw_bundle,
)

pytestmark = pytest.mark.integration

DUMP_ENV = "DUNGEONMIND_ELDYRWILD_RECOVERY_DUMP"
REPO_ROOT = Path(__file__).resolve().parents[2]
RECOVERY_SCRIPT = REPO_ROOT / "scripts" / "eldyrwild_world_authority_recovery.py"
WITNESS_DB = "dungeonmind_eldyrwild_recovery_witness"


def test_empty_database_is_world_missing(pg) -> None:
    report = check_world_authority(
        world_graph=pg.world_graph,
        adoptions=pg.existing_world_adoptions,
        sources=pg.sources,
        contributions=pg.contributions,
        identity_decisions=pg.identity_decisions,
    )
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_WORLD_MISSING


def test_adopted_d_a_is_stale_when_expected_head_is_d_b(pg) -> None:
    receipt = adopt_existing_world(
        raw_bundle(),
        adopted_at=NOW,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert receipt.published_revision_id == ELDYRWILD_D_A
    assert pg.world_graph.get_head("eldyrwild").head_revision_id == ELDYRWILD_D_A

    report = check_world_authority(
        world_graph=pg.world_graph,
        adoptions=pg.existing_world_adoptions,
        sources=pg.sources,
        contributions=pg.contributions,
        identity_decisions=pg.identity_decisions,
    )
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_STALE_RECOVERY_POINT
    assert report.current_head == ELDYRWILD_D_A


def _sibling_url(database_url: str, name: str) -> str:
    parsed = urlparse(database_url)
    if not parsed.path:
        raise AssertionError("database URL missing database name")
    return database_url.rsplit("/", 1)[0] + f"/{name}"


def _recreate_database(database_url: str, name: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (name,),
        )
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def test_exact_dump_restore_is_ready_at_d_b(database_url: str) -> None:
    dump = os.environ.get(DUMP_ENV, "").strip()
    if not dump:
        pytest.skip(f"{DUMP_ENV} unset")
    dump_path = Path(dump)
    if not dump_path.is_file():
        pytest.fail(f"{DUMP_ENV} does not exist: {dump_path}")

    witness_url = _sibling_url(database_url, WITNESS_DB)
    _recreate_database(database_url, WITNESS_DB)
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(RECOVERY_SCRIPT),
                "--database-url",
                witness_url,
                "--expected-head",
                ELDYRWILD_D_B,
                "restore",
                "--dump-path",
                str(dump_path),
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        combined = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0:
            pytest.fail(
                f"recovery restore failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        assert f"status={STATUS_READY}" in combined
        assert ELDYRWILD_D_B in combined
        assert ELDYRWILD_D_A in combined
    finally:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (WITNESS_DB,),
            )
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(WITNESS_DB)))
