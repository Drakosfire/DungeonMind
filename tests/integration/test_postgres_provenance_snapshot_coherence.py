"""PostgreSQL REPEATABLE_READ proof for batched source provenance snapshots."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest
from psycopg import sql

from dungeonmind.application.source_provenance_snapshot import SourceProvenanceSnapshot
from dungeonmind.contracts.evidence import (
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.infrastructure.postgres.database import SCHEMA, jsonb
from dungeonmind.infrastructure.postgres.serialization import dump_payload, model_fingerprint

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
ARTIFACT_ID = "src:snapshot-coherence"
REVISION_ID = "srev:snapshot-coherence"
WORLD_ID = "world:snapshot-coherence"


def _artifact(*, visibility: Visibility, current_revision_id: str) -> SourceArtifact:
    return SourceArtifact(
        source_artifact_id=ARTIFACT_ID,
        source_domain=SourceDomain.WORLDBUILDING,
        world_id=WORLD_ID,
        visibility=visibility,
        status=SourceStatus.ACTIVE,
        current_revision_id=current_revision_id,
        created_at=NOW,
    )


def _revision(*, content_sha256: str, locator: str) -> SourceRevision:
    return SourceRevision(
        source_revision_id=REVISION_ID,
        source_artifact_id=ARTIFACT_ID,
        content_sha256=content_sha256,
        body_storage="external",
        locator=locator,
        created_at=NOW,
    )


def _overwrite_source_generation(conn, artifact: SourceArtifact, revision: SourceRevision) -> None:
    conn.execute(
        sql.SQL(
            """
            UPDATE {}.source_artifacts
            SET visibility = %s,
                current_revision_id = %s,
                record_fingerprint = %s,
                payload = %s
            WHERE source_artifact_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (
            artifact.visibility.value,
            artifact.current_revision_id,
            model_fingerprint(artifact),
            jsonb(dump_payload(artifact)),
            artifact.source_artifact_id,
        ),
    )
    conn.execute(
        sql.SQL(
            """
            UPDATE {}.source_revisions
            SET content_sha256 = %s,
                locator = %s,
                record_fingerprint = %s,
                payload = %s
            WHERE source_revision_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (
            revision.content_sha256,
            revision.locator,
            model_fingerprint(revision),
            jsonb(dump_payload(revision)),
            revision.source_revision_id,
        ),
    )


@pytest.mark.integration
def test_postgres_provenance_snapshot_does_not_mix_source_generations(
    migrated_database: str, pg
) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresSourceRepository,
    )

    del pg
    gen1_artifact = _artifact(visibility=Visibility.PLAYER, current_revision_id=REVISION_ID)
    gen1_revision = _revision(content_sha256="aa" * 32, locator="fixture://gen-1")
    gen2_artifact = _artifact(visibility=Visibility.GM, current_revision_id=REVISION_ID)
    gen2_revision = _revision(content_sha256="bb" * 32, locator="fixture://gen-2")

    seed = PostgresSourceRepository(PostgresDatabase(migrated_database))
    seed.put_artifact(gen1_artifact)
    seed.put_revision(gen1_revision)

    started = threading.Event()
    release = threading.Event()
    writer_committed = threading.Event()
    captured: dict[str, object] = {}

    class _GatedSources(PostgresSourceRepository):
        def _after_provenance_artifact_batch(self) -> None:
            started.set()
            assert release.wait(timeout=5)

    gated = _GatedSources(PostgresDatabase(migrated_database))

    def reader() -> None:
        captured["snapshot"] = gated.get_provenance_snapshot(
            artifact_ids=[ARTIFACT_ID],
            revision_ids=[REVISION_ID],
        )

    def writer() -> None:
        assert started.wait(timeout=5)
        with PostgresDatabase(migrated_database).transaction() as conn:
            _overwrite_source_generation(conn, gen2_artifact, gen2_revision)
        writer_committed.set()

    reader_thread = threading.Thread(target=reader)
    writer_thread = threading.Thread(target=writer)
    reader_thread.start()
    assert started.wait(timeout=5)
    writer_thread.start()
    assert writer_committed.wait(timeout=5)
    release.set()
    reader_thread.join(timeout=5)
    writer_thread.join(timeout=5)
    assert not reader_thread.is_alive() and not writer_thread.is_alive()

    snapshot = captured["snapshot"]
    assert isinstance(snapshot, SourceProvenanceSnapshot)
    artifact = snapshot.get_artifact(ARTIFACT_ID)
    revision = snapshot.get_revision(REVISION_ID)
    assert artifact is not None
    assert revision is not None
    assert artifact.visibility is Visibility.PLAYER
    assert artifact.current_revision_id == REVISION_ID
    assert revision.locator == "fixture://gen-1"
    assert revision.content_sha256 == "aa" * 32
    assert not (
        artifact.visibility is Visibility.GM and revision.locator == "fixture://gen-1"
    )
    assert not (
        artifact.visibility is Visibility.PLAYER and revision.locator == "fixture://gen-2"
    )

    later = seed.get_provenance_snapshot(
        artifact_ids=[ARTIFACT_ID],
        revision_ids=[REVISION_ID],
    )
    later_artifact = later.get_artifact(ARTIFACT_ID)
    later_revision = later.get_revision(REVISION_ID)
    assert later_artifact is not None
    assert later_revision is not None
    assert later_artifact.visibility is Visibility.GM
    assert later_revision.locator == "fixture://gen-2"
    assert later_revision.content_sha256 == "bb" * 32
