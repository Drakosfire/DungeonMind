"""Contribution / identity / source / session roundtrips on PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dungeonmind.contracts import (
    Admissibility,
    ContributionSourceKind,
    GraphContribution,
    GraphRetrievalSession,
    IdentityDecisionKind,
    IdentityDecisionRecord,
    ProjectionSnapshot,
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    Visibility,
)
from dungeonmind.domain.errors import IdempotencyConflictError
from tests.conftest import WORLD_ID

NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
REV = "rev:" + "ab" * 16


def _contribution(cid: str = "contrib:1") -> GraphContribution:
    return GraphContribution(
        contribution_id=cid,
        world_id=WORLD_ID,
        source_kind=ContributionSourceKind.MANUAL_IMPORT,
        produced_at=NOW,
    )


def _session(session_id: str = "rsess:1") -> GraphRetrievalSession:
    return GraphRetrievalSession(
        session_id=session_id,
        snapshot=ProjectionSnapshot(
            world_id=WORLD_ID,
            admissibility=Admissibility.GM,
            revision_id=REV,
            head_revision_id=REV,
            is_head=True,
            projected_at=NOW,
        ),
        question="who holds the Sun Ledger?",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.integration
def test_contribution_identity_source_session_roundtrip(pg) -> None:
    contrib = _contribution()
    assert pg.contributions.append(contrib) == contrib
    assert pg.contributions.append(contrib) == contrib
    with pytest.raises(IdempotencyConflictError):
        pg.contributions.append(contrib.model_copy(update={"authored_by": "x"}))
    assert pg.contributions.get(WORLD_ID, "contrib:1") == contrib

    decision = IdentityDecisionRecord(
        decision_id="idec:pg",
        world_id=WORLD_ID,
        decision_kind=IdentityDecisionKind.ALIAS_ADD,
        subject_object_ids=["obj:1"],
        alias="Mere Astor",
        created_at=NOW,
    )
    pg.identity_decisions.append(decision)
    assert pg.identity_decisions.get(WORLD_ID, "idec:pg") == decision

    artifact = SourceArtifact(
        source_artifact_id="src:pg",
        source_domain=SourceDomain.WORLDBUILDING,
        world_id=WORLD_ID,
        visibility=Visibility.GM,
        created_at=NOW,
    )
    pg.sources.put_artifact(artifact)
    revision = SourceRevision(
        source_revision_id="srev:pg",
        source_artifact_id="src:pg",
        content_sha256="cd" * 32,
        locator="r2://dm/src-pg",
        created_at=NOW,
    )
    pg.sources.put_revision(revision)
    assert pg.sources.get_artifact("src:pg") == artifact
    assert pg.sources.list_revisions("src:pg") == [revision]

    session = _session()
    pg.retrieval_sessions.create(session)
    assert pg.retrieval_sessions.get("rsess:1") == session
    updated = session.model_copy(update={"question": "updated?"})
    pg.retrieval_sessions.save(updated)
    assert pg.retrieval_sessions.get("rsess:1").question == "updated?"  # type: ignore[union-attr]


@pytest.mark.integration
def test_records_survive_restart(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresContributionRepository,
        PostgresDatabase,
        PostgresIdentityDecisionRepository,
        PostgresRetrievalSessionRepository,
        PostgresSourceRepository,
    )

    contrib = _contribution("contrib:restart")
    PostgresContributionRepository(PostgresDatabase(migrated_database)).append(contrib)
    decision = IdentityDecisionRecord(
        decision_id="idec:restart",
        world_id=WORLD_ID,
        decision_kind=IdentityDecisionKind.MARK_AMBIGUOUS,
        subject_object_ids=["obj:r"],
        created_at=NOW,
    )
    PostgresIdentityDecisionRepository(PostgresDatabase(migrated_database)).append(
        decision
    )
    artifact = SourceArtifact(
        source_artifact_id="src:restart",
        source_domain=SourceDomain.MANUAL,
        world_id=WORLD_ID,
        created_at=NOW,
    )
    sources = PostgresSourceRepository(PostgresDatabase(migrated_database))
    sources.put_artifact(artifact)
    sessions = PostgresRetrievalSessionRepository(PostgresDatabase(migrated_database))
    sessions.create(_session("rsess:restart"))

    db2 = PostgresDatabase(migrated_database)
    assert (
        PostgresContributionRepository(db2).get(WORLD_ID, "contrib:restart") == contrib
    )
    assert (
        PostgresIdentityDecisionRepository(db2).get(WORLD_ID, "idec:restart")
        == decision
    )
    assert PostgresSourceRepository(db2).get_artifact("src:restart") == artifact
    assert PostgresRetrievalSessionRepository(db2).get("rsess:restart") is not None


@pytest.mark.integration
def test_contribution_conflict(pg) -> None:
    contrib = _contribution("contrib:conflict")
    pg.contributions.append(contrib)
    with pytest.raises(IdempotencyConflictError):
        pg.contributions.append(
            contrib.model_copy(update={"extraction_profile": "other"})
        )
