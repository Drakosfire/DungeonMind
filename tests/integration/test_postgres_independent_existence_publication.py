"""Real SQL owning-boundary checks for explicit independent existence publication."""

import pytest

from dungeonmind.application.contribution_review_v5 import finalize_contribution_review_v5
from dungeonmind.application.review_publication_v7 import publish_finalized_review_v7
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.review_publication import FinalizedReviewPublicationV3
from dungeonmind.infrastructure.postgres import PostgresRepositoryBundle
from dungeonmind.infrastructure.postgres.review_publication import (
    PostgresFinalizedReviewPublicationRepository,
)
from tests.conformance.test_independent_existence_publication import prepared
from tests.unit.test_contribution_review_v3 import source_snapshot
from tests.unit.test_contribution_review_v5 import setup_case

pytestmark = pytest.mark.integration


def setup_sql(pg, schema, *, protected=False):
    reader = prepared()[3]
    profile = None
    if protected:
        from uuid import uuid4

        from dungeonmind.application.graph_snapshot_v7 import VersionedUnionGraphSnapshotReaderV7
        from dungeonmind.contracts.semantic_profile import SemanticProfileRef
        from dungeonmind.domain.canonical import canonical_sha256
        from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
        from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor
        from tests.unit.test_publication_admission import admission_policy

        descriptor = load_builtin_v3_descriptor().model_copy(
            update={"profile_revision": "v7-protected-" + uuid4().hex}
        )
        profile = SemanticProfileRef(
            profile_id=descriptor.profile_id,
            profile_revision=descriptor.profile_revision,
            descriptor_sha256=canonical_sha256(descriptor.model_dump(mode="json")),
        )
        reader = VersionedUnionGraphSnapshotReaderV7(StaticSemanticProfileRegistry([descriptor]))
        pg.publication_admission.register(admission_policy(profile))
    case = setup_case(schema, semantic_profile=profile)
    parent = case[1]
    pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=parent.revision.world_id,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=parent.revision.operation_ids,
            graph_schema=schema,
            graph_payload=parent.graph_payload,
            created_at=parent.revision.created_at,
        )
    )
    snapshot = source_snapshot()
    for source in snapshot.artifacts.values():
        pg.sources.put_artifact(source)
    for revision in snapshot.revisions.values():
        pg.sources.put_revision(revision)
    state = finalize_contribution_review_v5(
        case[4],
        capability_policy=case[5],
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )
    return case, state, reader


def publish(pg, state, reader, repo=None):
    return publish_finalized_review_v7(
        state.record.world_id,
        state.record.review_id,
        published_at=state.record.reviewed_at,
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=repo or pg.finalized_review_publications,
        graph_reader=reader,
    )


@pytest.mark.parametrize("schema", ["dm_union_graph_v6", "dm_union_graph_v7"])
def test_sql_confirmed_review_publication_reconstruction_and_replay(pg, schema):
    case, state, reader = setup_sql(pg, schema)
    enabled = PostgresRepositoryBundle(pg.database, v7_graph_reader=reader)
    receipt = publish(enabled, state, reader)
    assert isinstance(receipt, FinalizedReviewPublicationV3)
    assert receipt.parent_graph_schema == schema
    assert publish(enabled, state, reader) == receipt
    fresh = PostgresRepositoryBundle(pg.database, v7_graph_reader=reader)
    assert (
        fresh.finalized_review_publications.get_for_review(receipt.world_id, receipt.review_id)
        == receipt
    )
    assert fresh.world_graph.get_revision(receipt.world_id, case[1].revision.revision_id) == case[1]
    assert (
        fresh.world_graph.get_head(receipt.world_id).head_revision_id
        == receipt.published_revision_id
    )
    with pg.database.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.finalized_review_publications"
            ).fetchone()["n"]
            == 1
        )


@pytest.mark.parametrize("fail_at", [1, 2])
def test_sql_failure_rolls_back_revision_head_event_and_receipt(pg, fail_at):
    case, state, reader = setup_sql(pg, "dm_union_graph_v6")
    calls = []

    def fail():
        calls.append(1)
        if len(calls) == fail_at:
            raise RuntimeError("injected V7 publication rollback")

    repo = PostgresFinalizedReviewPublicationRepository(
        pg.database, v7_graph_reader=reader, failure_hook=fail
    )
    with pytest.raises(RuntimeError, match="injected"):
        publish(pg, state, reader, repo)
    assert (
        pg.world_graph.get_head(state.record.world_id).head_revision_id
        == case[1].revision.revision_id
    )
    with pg.database.connect() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM dungeonmind.graph_revisions").fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.world_graph_head_events"
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.finalized_review_publications"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE dungeonmind.finalized_review_publications "
        "SET schema_version='dm_finalized_review_publication_v1'",
        "DELETE FROM dungeonmind.finalized_review_publications",
    ],
)
def test_sql_v3_receipt_cannot_be_changed_or_deleted(pg, statement):
    import psycopg

    _, state, reader = setup_sql(pg, "dm_union_graph_v6")
    enabled = PostgresRepositoryBundle(pg.database, v7_graph_reader=reader)
    receipt = publish(enabled, state, reader)
    with pg.database.connect() as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
            conn.execute(statement)
        conn.rollback()
    assert (
        enabled.finalized_review_publications.get_for_review(receipt.world_id, receipt.review_id)
        == receipt
    )


@pytest.mark.parametrize("level", ["REPEATABLE_READ", "SERIALIZABLE"])
def test_sql_snapshot_isolation_is_rejected_before_publication(pg, level):
    import psycopg

    from dungeonmind.domain.errors import PersistenceIntegrityError
    from dungeonmind.infrastructure.postgres import PostgresDatabase

    case, state, reader = setup_sql(pg, "dm_union_graph_v6")

    class SnapshotDatabase(PostgresDatabase):
        def connect(self):
            conn = super().connect()
            conn.isolation_level = getattr(psycopg.IsolationLevel, level)
            return conn

    repo = PostgresFinalizedReviewPublicationRepository(
        SnapshotDatabase(pg.database._database_url), v7_graph_reader=reader
    )
    with pytest.raises(PersistenceIntegrityError, match="READ COMMITTED"):
        publish(pg, state, reader, repo)
    assert (
        pg.world_graph.get_head(state.record.world_id).head_revision_id
        == case[1].revision.revision_id
    )
    with pg.database.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.finalized_review_publications"
            ).fetchone()["n"]
            == 0
        )


def test_sql_rejects_self_consistent_forged_graph_delta(pg):
    from dungeonmind.domain.errors import PersistenceIntegrityError
    from tests.conformance.test_independent_existence_publication import command_for

    case, _, reader = setup_sql(pg, "dm_union_graph_v6")

    def forge(payload):
        obj = next(o for o in payload["objects"] if o["properties"])
        obj["properties"][0]["value"]["count"] = 999

    command = command_for(prepared(), alter=forge)
    repo = PostgresFinalizedReviewPublicationRepository(pg.database, v7_graph_reader=reader)
    with pytest.raises(PersistenceIntegrityError, match="reviewed semantic delta"):
        repo.publish(command)
    assert (
        pg.world_graph.get_head(command.world_id).head_revision_id == case[1].revision.revision_id
    )
    with pg.database.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.finalized_review_publications"
            ).fetchone()["n"]
            == 0
        )


def test_sql_populated_v3_receipts_prevent_downgrade(pg):
    import os
    import subprocess
    import sys

    _, state, reader = setup_sql(pg, "dm_union_graph_v6")
    enabled = PostgresRepositoryBundle(pg.database, v7_graph_reader=reader)
    receipt = publish(enabled, state, reader)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0020_adopted_relation_correction"],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "cannot downgrade populated independent existence publications" in result.stderr
    assert (
        enabled.finalized_review_publications.get_for_review(receipt.world_id, receipt.review_id)
        == receipt
    )


def test_sql_receipt_and_ancestry_readback_work_on_read_only_connections(pg):
    from psycopg.conninfo import make_conninfo

    from dungeonmind.infrastructure.postgres import PostgresDatabase

    _, state, reader = setup_sql(pg, "dm_union_graph_v6")
    enabled = PostgresRepositoryBundle(pg.database, v7_graph_reader=reader)
    receipt = publish(enabled, state, reader)
    read_only = PostgresRepositoryBundle(
        PostgresDatabase(
            make_conninfo(pg.database._database_url, options="-c default_transaction_read_only=on")
        ),
        v7_graph_reader=reader,
    )
    assert (
        read_only.finalized_review_publications.get_for_review(receipt.world_id, receipt.review_id)
        == receipt
    )
    history = read_only.finalized_review_publications.read_verified_ancestry(
        receipt.world_id, receipt.published_revision_id
    )
    assert history


def test_sql_concurrent_same_review_returns_one_atomic_publication(pg):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    _, state, reader = setup_sql(pg, "dm_union_graph_v6")
    barrier = Barrier(2)

    class SynchronizedPublisher(PostgresFinalizedReviewPublicationRepository):
        def publish(self, command):
            barrier.wait(timeout=10)
            return super().publish(command)

    repo = SynchronizedPublisher(pg.database, v7_graph_reader=reader)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(publish, pg, state, reader, repo) for _ in range(2)]
        receipts = [future.result(timeout=20) for future in futures]
    assert receipts[0] == receipts[1]
    with pg.database.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.finalized_review_publications"
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM dungeonmind.graph_revisions").fetchone()["n"]
            == 2
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.world_graph_head_events"
            ).fetchone()["n"]
            == 2
        )


@pytest.mark.parametrize("writer_kind", ["source", "identity"])
def test_sql_world_fence_serializes_later_source_and_identity_writers(pg, writer_kind):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic, sleep

    from psycopg.conninfo import make_conninfo

    from dungeonmind.contracts.evidence import SourceArtifact
    from dungeonmind.contracts.identity import IdentityDecisionRecord
    from dungeonmind.infrastructure.postgres import PostgresDatabase

    _, state, reader = setup_sql(pg, "dm_union_graph_v6")
    entered, release = Event(), Event()

    def hold_before_commit():
        entered.set()
        assert release.wait(10)

    publisher = PostgresFinalizedReviewPublicationRepository(
        pg.database, v7_graph_reader=reader, failure_hook=hold_before_commit
    )
    application_name = "v7-fence-" + writer_kind
    writer = PostgresRepositoryBundle(
        PostgresDatabase(
            make_conninfo(pg.database._database_url, application_name=application_name)
        )
    )

    def write():
        if writer_kind == "source":
            return writer.sources.put_artifact(
                SourceArtifact(
                    source_artifact_id="source:after-v7",
                    source_domain="worldbuilding",
                    world_id=state.record.world_id,
                    visibility="gm",
                    created_at=state.record.reviewed_at,
                )
            )
        return writer.identity_decisions.append(
            IdentityDecisionRecord(
                decision_id="idec:after-v7",
                world_id=state.record.world_id,
                decision_kind="alias_add",
                subject_object_ids=["npc:new_npc"],
                alias="Later independently authored alias",
                created_at=state.record.reviewed_at,
            )
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        publication = pool.submit(publish, pg, state, reader, publisher)
        try:
            assert entered.wait(10)
            later = pool.submit(write)
            deadline = monotonic() + 10
            blocked = False
            while monotonic() < deadline:
                with pg.database.connect() as conn:
                    blocked = conn.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                        "WHERE application_name=%s AND wait_event_type='Lock') AS waiting",
                        (application_name,),
                    ).fetchone()["waiting"]
                if blocked:
                    break
                sleep(0.01)
            assert blocked, "writer did not encounter the owning World fence"
            assert not later.done()
        finally:
            release.set()
        receipt = publication.result(timeout=20)
        later.result(timeout=20)
    verified = PostgresRepositoryBundle(pg.database, v7_graph_reader=reader)
    assert (
        verified.finalized_review_publications.get_for_review(receipt.world_id, receipt.review_id)
        == receipt
    )
    assert receipt.identity_history == ()


def test_sql_sequential_v6_v7_v7_ingestion_keeps_both_campaigns_visible(pg):
    from tests.conformance.test_independent_existence_publication import (
        assert_two_campaign_ingestions,
    )

    case, state, reader = setup_sql(pg, "dm_union_graph_v6")
    enabled = PostgresRepositoryBundle(pg.database, v7_graph_reader=reader)
    sql_case = list(case)
    sql_case[0] = enabled.world_graph
    sql_case[3] = enabled.contribution_reviews
    assert_two_campaign_ingestions(
        (
            sql_case,
            state,
            enabled.sources,
            reader,
            enabled.finalized_review_publications,
        )
    )


def test_sql_two_distinct_confirmed_reviews_have_one_parent_cas_winner(pg):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from dungeonmind.contracts.contribution import GraphContributionV4
    from dungeonmind.contracts.contribution_review import derive_confirmation_id
    from dungeonmind.contracts.contribution_review_v5 import (
        CommitConfirmationReceiptV5,
        ContributionReviewIntentV5,
        ContributionReviewSubmissionV5,
        contribution_v4_payload_sha256,
        derive_review_intent_sha256_v5,
    )
    from dungeonmind.domain.errors import StaleParentRevisionError

    case, first, reader = setup_sql(pg, "dm_union_graph_v6")
    old = case[4].intent
    fields = {
        k: getattr(old, k)
        for k in type(old).model_fields
        if k not in {"schema_version", "review_intent_sha256"}
    }
    candidate = GraphContributionV4.model_validate(
        {
            **old.candidate_contribution.model_dump(mode="json"),
            "contribution_id": "contrib:" + "e" * 32,
        }
    )
    fields.update(
        operation_id="reviewop:" + "e" * 32,
        candidate_contribution=candidate,
        plan_ref=old.plan_ref.model_copy(
            update={
                "candidate_contribution_sha256": contribution_v4_payload_sha256(candidate),
                "source_plan_id": "plan:second-competing-reviewed-ingestion",
            }
        ),
    )
    intent = ContributionReviewIntentV5(
        **fields, review_intent_sha256=derive_review_intent_sha256_v5(**fields)
    )
    confirmation = CommitConfirmationReceiptV5(
        operation_id=intent.operation_id,
        review_intent_sha256=intent.review_intent_sha256,
        actor=intent.reviewer_id,
        world_id=intent.world_id,
        campaign_id=intent.campaign_id,
        expected_parent_revision_id=intent.plan_ref.expected_parent_revision_id,
        confirmed_at=intent.reviewed_at,
        confirmation_id=derive_confirmation_id(
            operation_id=intent.operation_id,
            review_intent_sha256=intent.review_intent_sha256,
            actor=intent.reviewer_id,
            confirmed_at=intent.reviewed_at,
        ),
    )
    second = finalize_contribution_review_v5(
        ContributionReviewSubmissionV5(intent=intent, confirmation=confirmation),
        capability_policy=case[5],
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )
    barrier = Barrier(2)

    class CompetingPublisher(PostgresFinalizedReviewPublicationRepository):
        def publish(self, command):
            barrier.wait(timeout=10)
            return super().publish(command)

    repo = CompetingPublisher(pg.database, v7_graph_reader=reader)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(publish, pg, state, reader, repo) for state in [first, second]]
        results = []
        for future in futures:
            try:
                results.append(future.result(timeout=20))
            except StaleParentRevisionError as error:
                results.append(error)
    assert sum(isinstance(r, FinalizedReviewPublicationV3) for r in results) == 1
    assert sum(isinstance(r, StaleParentRevisionError) for r in results) == 1
    with pg.database.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.finalized_review_publications"
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM dungeonmind.graph_revisions").fetchone()["n"]
            == 2
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM dungeonmind.world_graph_head_events"
            ).fetchone()["n"]
            == 2
        )


@pytest.mark.parametrize("validator_available", [False, True])
def test_sql_v7_protected_profile_requires_the_current_validator(pg, validator_available):
    from dungeonmind.application.publication_admission import PublicationAdmissionRegistry
    from dungeonmind.domain.errors import PersistenceIntegrityError
    from tests.unit.test_publication_admission import SyntheticValidator

    case, state, reader = setup_sql(pg, "dm_union_graph_v6", protected=True)
    validator = SyntheticValidator()
    registry = PublicationAdmissionRegistry((("synthetic.complete-set", "v1", validator),))
    enabled = PostgresRepositoryBundle(
        pg.database,
        v7_graph_reader=reader,
        admission_registry=registry if validator_available else None,
    )
    if validator_available:
        receipt = publish(enabled, state, reader)
        assert receipt.admission_context is not None
        assert receipt.admission_policy_ref is not None
        assert len(validator.calls) == 1
        assert publish(enabled, state, reader) == receipt
    else:
        with pytest.raises(PersistenceIntegrityError) as failure:
            publish(enabled, state, reader)
        assert failure.value.details["reason"] == "validator_unavailable"
        assert (
            enabled.world_graph.get_head(state.record.world_id).head_revision_id
            == case[1].revision.revision_id
        )
        with pg.database.connect() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) AS n FROM dungeonmind.finalized_review_publications"
                ).fetchone()["n"]
                == 0
            )
