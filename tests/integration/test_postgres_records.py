"""Contribution / identity / source / session roundtrips on PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dungeonmind.contracts import (
    Admissibility,
    ContributionEpistemicKind,
    ContributionSourceKind,
    GraphContribution,
    GraphContributionAssertionCorrection,
    GraphContributionAssertionCorrectionKind,
    GraphContributionAssertionV2,
    GraphContributionV2,
    GraphRetrievalSession,
    IdentityAliasMapRewrite,
    IdentityDecisionKind,
    IdentityDecisionRecord,
    IdentityDecisionRecordV2,
    IdentityMergeSideEffects,
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


@pytest.mark.integration
def test_session_save_updates_extracted_created_at(pg) -> None:
    session = _session("rsess:created-at")
    pg.retrieval_sessions.create(session)
    later = NOW.replace(year=2027)
    updated = session.model_copy(
        update={"created_at": later, "updated_at": later, "question": "moved?"}
    )
    pg.retrieval_sessions.save(updated)
    loaded = pg.retrieval_sessions.get("rsess:created-at")
    assert loaded is not None
    assert loaded.created_at == later
    assert loaded.question == "moved?"


@pytest.mark.integration
def test_contribution_status_column_drift_fails_closed(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres.database import SCHEMA, PostgresDatabase

    contrib = _contribution("contrib:drift-status")
    pg.contributions.append(contrib)
    db = PostgresDatabase(migrated_database)
    with db.transaction() as conn:
        conn.execute(
            f"UPDATE {SCHEMA}.graph_contributions SET status = 'retracted' "
            "WHERE contribution_id = %s",
            ("contrib:drift-status",),
        )
    from dungeonmind.domain.errors import PersistenceIntegrityError

    with pytest.raises(PersistenceIntegrityError, match="status"):
        pg.contributions.get(WORLD_ID, "contrib:drift-status")


@pytest.mark.integration
def test_conflicting_duplicate_evidence_in_contribution_fails(pg) -> None:
    from dungeonmind.contracts import (
        EvidenceRef,
        EvidenceRole,
        GraphContributionAssertion,
        SourceDomain,
    )

    ev_a = EvidenceRef(
        evidence_ref_id="ev:dup",
        source_artifact_id="src:a",
        source_revision_id="srev:x",
        source_domain=SourceDomain.WORLDBUILDING,
        evidence_role=EvidenceRole.SUPPORT,
    )
    ev_b = ev_a.model_copy(update={"source_revision_id": "srev:y"})
    contrib = GraphContribution(
        contribution_id="contrib:ev-conflict",
        world_id=WORLD_ID,
        source_kind=ContributionSourceKind.MANUAL_IMPORT,
        produced_at=NOW,
        assertions=[
            GraphContributionAssertion(
                assertion_id="a:1",
                assertion_kind="attribute",
                evidence_refs=[ev_a],
            ),
            GraphContributionAssertion(
                assertion_id="a:2",
                assertion_kind="attribute",
                evidence_refs=[ev_b],
            ),
        ],
    )
    with pytest.raises(IdempotencyConflictError, match="conflicting evidence_ref"):
        pg.contributions.append(contrib)
    assert pg.contributions.get(WORLD_ID, "contrib:ev-conflict") is None


@pytest.mark.integration
def test_identical_duplicate_evidence_in_contribution_ok(pg) -> None:
    from dungeonmind.contracts import (
        EvidenceRef,
        EvidenceRole,
        GraphContributionAssertion,
        SourceDomain,
    )

    ev = EvidenceRef(
        evidence_ref_id="ev:same",
        source_artifact_id="src:a",
        source_revision_id="srev:x",
        source_domain=SourceDomain.WORLDBUILDING,
        evidence_role=EvidenceRole.SUPPORT,
    )
    contrib = GraphContribution(
        contribution_id="contrib:ev-same",
        world_id=WORLD_ID,
        source_kind=ContributionSourceKind.MANUAL_IMPORT,
        produced_at=NOW,
        assertions=[
            GraphContributionAssertion(
                assertion_id="a:1",
                assertion_kind="attribute",
                evidence_refs=[ev],
            ),
            GraphContributionAssertion(
                assertion_id="a:2",
                assertion_kind="attribute",
                evidence_refs=[ev],
            ),
        ],
    )
    assert pg.contributions.append(contrib) == contrib
    assert pg.contributions.get(WORLD_ID, "contrib:ev-same") == contrib


@pytest.mark.integration
def test_postgres_v2_contribution_and_identity_roundtrip(pg) -> None:
    contribution = GraphContributionV2(
        contribution_id="contrib:v2",
        world_id=WORLD_ID,
        source_kind=ContributionSourceKind.MANUAL_IMPORT,
        produced_at=NOW,
        assertions=[
            GraphContributionAssertionV2(
                assertion_id="a:source",
                assertion_kind="attribute",
                source_artifact_id="src:v2",
                epistemic_kind=ContributionEpistemicKind.SOURCE_DERIVED_CANDIDATE,
            ),
            GraphContributionAssertionV2(
                assertion_id="a:replacement",
                assertion_kind="attribute",
                source_artifact_id="src:v2",
                acceptance_state="accepted",
            ),
        ],
        assertion_corrections=[
            GraphContributionAssertionCorrection(
                correction_kind=GraphContributionAssertionCorrectionKind.CONTRADICTS,
                target_contribution_id="contrib:other",
                target_assertion_id="a:other",
            ),
            GraphContributionAssertionCorrection(
                correction_kind=GraphContributionAssertionCorrectionKind.CONTRADICTS_AND_REPLACES,
                target_contribution_id="contrib:other",
                target_assertion_id="a:other",
                replacement_assertion_id="a:replacement",
            ),
        ],
    )
    assert pg.contributions.append(contribution) == contribution
    loaded = pg.contributions.get(WORLD_ID, "contrib:v2")
    assert loaded == contribution
    assert loaded.model_dump(mode="json") == contribution.model_dump(mode="json")
    assert loaded.assertions[0].epistemic_kind is ContributionEpistemicKind.SOURCE_DERIVED_CANDIDATE
    listed = pg.contributions.list_for_world(WORLD_ID)
    assert contribution in listed

    decision = IdentityDecisionRecordV2(
        decision_id="idec:v2-merge",
        world_id=WORLD_ID,
        decision_kind=IdentityDecisionKind.MERGE,
        subject_object_ids=["obj:merged-away", "obj:keep"],
        target_object_ids=["obj:keep"],
        created_at=NOW,
        merge_side_effects=IdentityMergeSideEffects(
            aliases_added_to_target=["kept"],
            evidence_ref_ids_added_to_target=["ev:1"],
            source_domains_added_to_target=["worldbuilding"],
            alias_map_rewrites=[
                IdentityAliasMapRewrite(
                    alias_key="old",
                    prior_owner_node_id="obj:merged-away",
                    new_owner_node_id="obj:keep",
                ),
                IdentityAliasMapRewrite(
                    alias_key="kept",
                    prior_owner_node_id=None,
                    new_owner_node_id="obj:keep",
                ),
            ],
        ),
    )
    assert pg.identity_decisions.append(decision) == decision
    loaded_decision = pg.identity_decisions.get(WORLD_ID, "idec:v2-merge")
    assert loaded_decision == decision
    assert loaded_decision.model_dump(mode="json") == decision.model_dump(mode="json")
    assert pg.identity_decisions.list_for_world(WORLD_ID)[-1] == decision


@pytest.mark.integration
def test_postgres_unsupported_contribution_schema_fails_closed(
    migrated_database: str, pg
) -> None:
    from dungeonmind.domain.errors import PersistenceIntegrityError
    from dungeonmind.infrastructure.postgres.database import SCHEMA, PostgresDatabase

    contrib = _contribution("contrib:bad-schema")
    pg.contributions.append(contrib)
    db = PostgresDatabase(migrated_database)
    with db.transaction() as conn:
        conn.execute(
            f"UPDATE {SCHEMA}.graph_contributions "
            "SET schema_version = 'dm_graph_contribution_v9' "
            "WHERE contribution_id = %s",
            ("contrib:bad-schema",),
        )
    with pytest.raises(PersistenceIntegrityError, match="unsupported contribution schema"):
        pg.contributions.get(WORLD_ID, "contrib:bad-schema")
