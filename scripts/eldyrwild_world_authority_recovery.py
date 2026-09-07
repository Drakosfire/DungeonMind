#!/usr/bin/env -S uv run python
"""Operator check/restore/backup for durable Eldyrwild World authority.

This CLI restores the exact accepted PostgreSQL dump and verifies D_A/D_B
lineage through DungeonMind application ports. It does not invent a child
revision, re-ingest C1/C2 recaps, or write Buddy APP-STATE.

Usage:
    uv run python scripts/eldyrwild_world_authority_recovery.py check \\
        --database-url "$DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL"

    uv run python scripts/eldyrwild_world_authority_recovery.py restore \\
        --database-url "$DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL" \\
        --dump-path /path/to/dungeonmind_cutover_live.dump

    uv run python scripts/eldyrwild_world_authority_recovery.py backup \\
        --database-url "$DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL" \\
        --output-path /path/outside/git/eldyrwild.dump

Options such as ``--database-url`` belong to the subcommand and must follow it
(``check --database-url ...``), not precede it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dungeonmind.application.world_authority_recovery import (  # noqa: E402
    ELDYRWILD_D_B,
    ELDYRWILD_WORLD_ID,
    ProjectionWitness,
    RecoveryExpectation,
    WorldAuthorityPreflight,
    _load_sealed_manifest,
    check_world_authority,
    unavailable_preflight,
)

EXPECTED_DUMP_SHA256 = "a7d126b88b72400d208572e20d02226acbe84887af9d8b69cdcae4ba99c8f617"


def _redact_dsn(database_url: str) -> str:
    parsed = urlparse(database_url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    db = parsed.path.lstrip("/")
    return f"postgresql://{parsed.username or ''}:***@{host}{port}/{db}"


def _pg_env(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url)
    password = unquote(parsed.password or "")
    env = {**os.environ}
    if password:
        env["PGPASSWORD"] = password
    return env


def _pg_args(database_url: str) -> list[str]:
    parsed = urlparse(database_url)
    args: list[str] = []
    if parsed.hostname:
        args.extend(["-h", parsed.hostname])
    if parsed.port:
        args.extend(["-p", str(parsed.port)])
    if parsed.username:
        args.extend(["-U", parsed.username])
    db = parsed.path.lstrip("/")
    if db:
        args.extend(["-d", db])
    return args


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_restore_target(database_url: str) -> None:
    """Install pgvector in schema dungeonmind before table restore.

    The accepted dump types ``embedding`` as ``dungeonmind.vector`` and does
    not include ``CREATE EXTENSION``. An empty database therefore cannot
    restore ``semantic_documents`` until the type exists in that schema.
    Pre-creating the schema means the dump's SCHEMA object must be skipped.
    """

    import psycopg

    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS dungeonmind")
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA dungeonmind")


def _pg_restore(database_url: str, dump_path: Path) -> subprocess.CompletedProcess[str]:
    listed = subprocess.run(
        ["pg_restore", "-l", str(dump_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if listed.returncode != 0:
        return listed
    toc_lines: list[str] = []
    for line in listed.stdout.splitlines():
        if " SCHEMA - dungeonmind " in line:
            toc_lines.append(f";{line}")
        else:
            toc_lines.append(line)
    with tempfile.NamedTemporaryFile("w", suffix=".toc", delete=False) as handle:
        handle.write("\n".join(toc_lines) + "\n")
        toc_path = handle.name
    try:
        return subprocess.run(
            [
                "pg_restore",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "--use-list",
                toc_path,
                *_pg_args(database_url),
                str(dump_path),
            ],
            env=_pg_env(database_url),
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        Path(toc_path).unlink(missing_ok=True)


def _schema_revision(database_url: str) -> str | None:
    from dungeonmind.infrastructure.postgres.database import PostgresDatabase

    database = PostgresDatabase(database_url)
    try:
        with database.connect() as conn:
            row = conn.execute("SELECT version_num FROM dungeonmind.alembic_version").fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return str(row["version_num"] if isinstance(row, dict) else row[0])


def _build_projector(
    database_url: str, world_id: str
) -> tuple[Any, Callable[[], ProjectionWitness]]:
    from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
    from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
    from dungeonmind.contracts.projection import Admissibility
    from dungeonmind.contracts.projection_v2 import (
        ScopeModeV2,
        WorldGraphProjectionRequestV2,
    )
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresRepositoryBundle,
    )
    from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
    from dungeonmind_dnd.application.world_object_vocabulary import (
        load_builtin_v3_descriptor,
    )

    bundle = PostgresRepositoryBundle(PostgresDatabase(database_url))
    reader = VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([load_builtin_v3_descriptor()])
    )
    service = WorldGraphProjectionService(
        world_graph=bundle.world_graph,
        sources=bundle.sources,
        graph_reader=reader,
        reviewed_world_initializations=bundle.reviewed_world_initializations,
    )
    request = WorldGraphProjectionRequestV2.for_authorized(
        world_id=world_id,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
    )

    def _project() -> ProjectionWitness:
        result = service.project(request)
        return ProjectionWitness(
            revision_id=result.snapshot.revision_id,
            head_revision_id=result.snapshot.head_revision_id,
            object_count=len(result.graph.objects),
        )

    return bundle, _project


def _run_check(database_url: str, expected_head: str) -> WorldAuthorityPreflight:
    try:
        bundle, project = _build_projector(database_url, ELDYRWILD_WORLD_ID)
        schema_revision = _schema_revision(database_url)
        return check_world_authority(
            world_graph=bundle.world_graph,
            adoptions=bundle.existing_world_adoptions,
            sources=bundle.sources,
            contributions=bundle.contributions,
            identity_decisions=bundle.identity_decisions,
            expected=RecoveryExpectation(expected_head=expected_head),
            project=project,
            schema_revision=schema_revision,
            membership_manifest=_load_sealed_manifest(),
        )
    except Exception as exc:
        return unavailable_preflight(diagnostic=str(exc))


def _print_report(report: WorldAuthorityPreflight, database_url: str) -> None:
    print(f"status={report.status}")
    if report.reason:
        print(f"reason={report.reason}")
    print(f"database={_redact_dsn(database_url)}")
    print(f"world_id={report.world_id}")
    print(f"schema_revision={report.schema_revision}")
    print(f"receipt_schema={report.receipt_schema}")
    print(f"adopted_revision_id={report.adopted_revision_id}")
    print(f"current_head={report.current_head}")
    print(f"parent_revision_id={report.parent_revision_id}")
    print(f"bundle_sha256={report.bundle_sha256}")
    print(f"membership_m0={report.membership_m0}")
    print(f"membership_m1={report.membership_m1}")
    print(f"artifact_count={report.artifact_count}")
    print(f"source_revision_count={report.source_revision_count}")
    print(f"contribution_count={report.contribution_count}")
    print(f"identity_decision_count={report.identity_decision_count}")
    if report.projection is not None:
        print(
            "projection="
            f"revision={report.projection.revision_id} "
            f"head={report.projection.head_revision_id} "
            f"objects={report.projection.object_count}"
        )
    for diagnostic in report.diagnostics:
        print(f"diagnostic={diagnostic}")


def _cmd_check(args: argparse.Namespace) -> int:
    report = _run_check(args.database_url, args.expected_head)
    _print_report(report, args.database_url)
    return 0 if report.ready else 2


def _cmd_restore(args: argparse.Namespace) -> int:
    dump_path = Path(args.dump_path)
    if not dump_path.is_file():
        print(f"error: dump not found: {dump_path}", file=sys.stderr)
        return 2
    actual = _sha256_file(dump_path)
    expected = args.expected_dump_sha256
    if actual != expected:
        print(
            "error: dump digest mismatch; refusing to restore a substitute file\n"
            f"  path={dump_path}\n"
            f"  expected={expected}\n"
            f"  actual={actual}",
            file=sys.stderr,
        )
        return 2
    try:
        _prepare_restore_target(args.database_url)
    except Exception as exc:
        print(f"error: failed to prepare restore target: {exc}", file=sys.stderr)
        return 2
    restore = _pg_restore(args.database_url, dump_path)
    if restore.returncode != 0:
        print(restore.stdout)
        print(restore.stderr, file=sys.stderr)
        print("error: pg_restore failed", file=sys.stderr)
        return 2
    migrate = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_ROOT,
        env={**os.environ, "DUNGEONMIND_DATABASE_URL": args.database_url},
        check=False,
        capture_output=True,
        text=True,
    )
    if migrate.returncode != 0:
        print(migrate.stdout)
        print(migrate.stderr, file=sys.stderr)
        print("error: alembic upgrade head failed", file=sys.stderr)
        return 2
    print(f"restored dump_sha256={actual}")
    return _cmd_check(args)


def _cmd_backup(args: argparse.Namespace) -> int:
    output = Path(args.output_path)
    if output.exists():
        print(f"error: refusing to overwrite {output}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    dump = subprocess.run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--file",
            str(output),
            *_pg_args(args.database_url),
        ],
        env=_pg_env(args.database_url),
        check=False,
        capture_output=True,
        text=True,
    )
    if dump.returncode != 0:
        print(dump.stdout)
        print(dump.stderr, file=sys.stderr)
        print("error: pg_dump failed", file=sys.stderr)
        return 2
    digest = _sha256_file(output)
    print(f"backup={output}")
    print(f"sha256={digest}")
    print(f"source={_redact_dsn(args.database_url)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # ``--database-url`` / ``--expected-head`` are owned by the subparsers only.
    # Registering them on both the root parser and the subparsers lets argparse
    # overwrite a value supplied before the subcommand with the subparser's
    # environment default, silently re-targeting the command at the wrong DSN.
    # A single owner makes the supplied value authoritative.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--database-url",
        default=os.environ.get("DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL", ""),
        help="Designated World DSN; never the Buddy APP-STATE DSN.",
    )
    common.add_argument("--expected-head", default=ELDYRWILD_D_B)
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=("common options must follow the subcommand, e.g. `check --database-url ...`"),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "check",
        parents=[common],
        help="Verify exact D_A/D_B authority without writing.",
    )

    restore = sub.add_parser(
        "restore",
        parents=[common],
        help="Restore the accepted dump, migrate, check.",
    )
    restore.add_argument("--dump-path", required=True)
    restore.add_argument("--expected-dump-sha256", default=EXPECTED_DUMP_SHA256)

    backup = sub.add_parser(
        "backup",
        parents=[common],
        help="pg_dump custom format to an external path.",
    )
    backup.add_argument("--output-path", required=True)

    args = parser.parse_args(argv)
    if not args.database_url:
        print(
            "error: --database-url or DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL required",
            file=sys.stderr,
        )
        return 2
    if args.command == "check":
        return _cmd_check(args)
    if args.command == "restore":
        return _cmd_restore(args)
    return _cmd_backup(args)


if __name__ == "__main__":
    raise SystemExit(main())
