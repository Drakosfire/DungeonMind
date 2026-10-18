"""Installed migration and real cross-World registration/first-use fences."""

import os
import subprocess
import sys
import threading
from uuid import uuid4

import pytest
from psycopg import connect, sql
from psycopg.conninfo import make_conninfo
from sqlalchemy.engine import make_url

from dungeonmind.application.publication_admission import profile_fence_key
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import (
    PostgresDatabase,
    PostgresPublicationAdmissionRepository,
    PostgresRepositoryBundle,
)
from tests.integration.test_postgres_publication_admission import setup_pg
from tests.unit.test_contribution_review_v2 import PROFILE, REVIEWED_AT
from tests.unit.test_publication_admission import admission_policy

pytestmark = pytest.mark.integration


def unused_ref():
    return PROFILE.model_copy(update={"profile_revision": "admission-race-" + uuid4().hex})


def raw_command(ref, world_id):
    return PublishRevisionCommand(
        world_id=world_id,
        parent_revision_id=None,
        expected_parent_revision_id=None,
        operation_ids=["first-use"],
        graph_schema="synthetic:profile-test",
        graph_payload={"semantic_profile": ref.model_dump(mode="json")},
        created_at=REVIEWED_AT,
    )


@pytest.mark.parametrize("first", ["registration", "raw_use"])
def test_real_cross_world_profile_fence_serializes_registration_against_first_use(pg, first):
    ref = unused_ref()
    policy = admission_policy(ref)
    authority = pg.publication_admission
    ready, release = threading.Event(), threading.Event()
    result = []

    # Hold exact same profile fence in a first real transaction and commit its
    # authority action before releasing the waiting operation on another World.
    def owner():
        with pg.database.transaction() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (profile_fence_key(ref),))
            if first == "registration":
                from dungeonmind.infrastructure.postgres.database import jsonb

                conn.execute(
                    "INSERT INTO dungeonmind.publication_admission_profiles "
                    "(profile_id,profile_revision,descriptor_sha256,policy_payload) "
                    "VALUES(%s,%s,%s,%s)",
                    (
                        ref.profile_id,
                        ref.profile_revision,
                        ref.descriptor_sha256,
                        jsonb(policy.model_dump(mode="json")),
                    ),
                )
            else:
                pg.world_graph._publish_revision_in_transaction(
                    conn, raw_command(ref, "world:race-a"), world_locked=False
                )
            ready.set()
            assert release.wait(5)

    def contender():
        assert ready.wait(5)
        try:
            if first == "registration":
                pg.world_graph.publish_revision(raw_command(ref, "world:race-b"))
            else:
                authority.register(policy)
            result.append("ok")
        except PersistenceIntegrityError:
            result.append("denied")

    a, b = threading.Thread(target=owner), threading.Thread(target=contender)
    a.start()
    assert ready.wait(5)
    b.start()
    # Observe the actual waiting transaction before allowing the lock owner to commit.
    import time

    deadline = time.monotonic() + 5
    waiting = False
    while time.monotonic() < deadline:
        with pg.database.connect() as conn:
            waiting = conn.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_locks "
                "WHERE locktype='advisory' AND NOT granted) AS blocked"
            ).fetchone()["blocked"]
        if waiting:
            break
        time.sleep(0.01)
    release.set()
    a.join(5)
    b.join(5)
    assert waiting and not a.is_alive() and not b.is_alive()
    assert result == (["ok"] if first == "registration" else ["denied"])
    with pg.database.connect() as conn:
        row = conn.execute(
            "SELECT protected_use FROM dungeonmind.publication_admission_profiles "
            "WHERE profile_id=%s AND profile_revision=%s",
            (ref.profile_id, ref.profile_revision),
        ).fetchone()
    assert row["protected_use"] is (first == "registration")


def test_direct_finalization_marks_first_use_and_rejects_retroactive_policy(pg):
    lane = setup_pg(pg, protected=False)
    with pytest.raises(PersistenceIntegrityError):
        lane.authority.register(lane.policy)
    # Use a never-published independent identity in a valid finalized review.
    from dungeonmind.application.contribution_review_v4 import _build_review_state
    from tests.unit.test_contribution_review_v3_contract import typed_intent
    from tests.unit.test_contribution_review_v4 import submission, upgrade_intent

    ref = unused_ref()
    intent = typed_intent().model_copy(update={"operation_id": "reviewop:" + uuid4().hex})
    intent.plan_ref = intent.plan_ref.model_copy(
        update={
            "semantic_profile": ref,
            "source_plan_id": "plan:direct-finalize-only",
            "expected_parent_revision_id": lane.parent.revision.revision_id,
            "base_graph_payload_sha256": lane.parent.revision.graph_payload_sha256,
            "base_graph_schema": lane.parent.revision.graph_schema,
        }
    )
    intent = upgrade_intent(intent)
    pg.contribution_reviews.finalize(_build_review_state(submission(intent)))
    with pytest.raises(PersistenceIntegrityError):
        lane.authority.register(admission_policy(ref))


def test_exact_registration_replay_and_descriptor_policy_conflicts(pg):
    ref = unused_ref()
    policy = admission_policy(ref)
    assert pg.publication_admission.register(policy) == policy
    assert PostgresPublicationAdmissionRepository(pg.database).register(policy) == policy
    for changed in (
        admission_policy(ref, version="v2"),
        admission_policy(ref.model_copy(update={"descriptor_sha256": "0" * 64})),
    ):
        with pytest.raises(PersistenceIntegrityError):
            pg.publication_admission.register(changed)
    pg.world_graph.publish_revision(raw_command(ref, "world:registered"))
    assert pg.publication_admission.register(policy) == policy
    with pytest.raises(PersistenceIntegrityError):
        pg.world_graph.publish_revision(
            raw_command(ref.model_copy(update={"descriptor_sha256": "0" * 64}), "world:conflict")
        )


def test_database_immutability_cannot_delete_or_disable_policy(pg):
    ref = unused_ref()
    policy = pg.publication_admission.register(admission_policy(ref))
    for statement in (
        "DELETE FROM dungeonmind.publication_admission_profiles "
        "WHERE profile_id=%s AND profile_revision=%s",
        "UPDATE dungeonmind.publication_admission_profiles SET policy_payload=NULL "
        "WHERE profile_id=%s AND profile_revision=%s",
    ):
        with pytest.raises(PersistenceIntegrityError), pg.database.transaction() as conn:
            conn.execute(statement, (ref.profile_id, ref.profile_revision))
    assert pg.publication_admission.get(ref) == policy


def alembic(url, *args, check=True):
    env = dict(os.environ, DUNGEONMIND_DATABASE_URL=url, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args], env=env, capture_output=True, text=True
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_installed_migration_backfills_history_rejects_ambiguous_and_refuses_protected_downgrade(
    migrated_database,
):
    # This one migration witness creates a second uniquely owned disposable DB
    # on the SAME authorized fixture. Always finally-drop it, including failures.
    name = "admission_migration_" + uuid4().hex
    admin = make_conninfo(migrated_database, dbname="postgres")
    with connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        url = make_url(migrated_database).set(database=name).render_as_string(hide_password=False)
        alembic(url, "upgrade", "0016_operator_source_attestation")
        # Current writer must fail closed against missing authority schema.
        bundle = PostgresRepositoryBundle(PostgresDatabase(url))
        with pytest.raises(PersistenceIntegrityError):
            bundle.world_graph.publish_revision(raw_command(unused_ref(), "world:missing-schema"))
        # Emulate pre-gate writer history only in this isolated migration DB.
        from dungeonmind.contracts.graph import StoredGraphRevision, WorldGraphRevision
        from dungeonmind.domain.revision_ids import compute_revision_id
        from dungeonmind.infrastructure.postgres.database import jsonb, lock_world
        from dungeonmind.infrastructure.postgres.serialization import model_fingerprint

        ref = unused_ref()
        command = raw_command(ref, "world:historical")
        digest = canonical_sha256(command.graph_payload)
        revision = WorldGraphRevision(
            world_id=command.world_id,
            revision_id=compute_revision_id(
                world_id=command.world_id,
                parent_revision_id=None,
                operation_ids=command.operation_ids,
                graph_schema=command.graph_schema,
                graph_payload_sha256=digest,
            ),
            parent_revision_id=None,
            created_at=REVIEWED_AT,
            operation_ids=command.operation_ids,
            graph_schema=command.graph_schema,
            graph_payload_sha256=digest,
        )
        with bundle.database.transaction() as conn:
            lock_world(conn, command.world_id, created_at=REVIEWED_AT)
            conn.execute(
                "INSERT INTO dungeonmind.graph_revisions(world_id,revision_id,parent_revision_id,"
                "created_at,graph_schema,graph_payload_sha256,schema_version,record_fingerprint,"
                "revision_payload,graph_payload) VALUES(%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s)",
                (
                    revision.world_id,
                    revision.revision_id,
                    revision.created_at,
                    revision.graph_schema,
                    digest,
                    revision.schema_version,
                    model_fingerprint(
                        StoredGraphRevision(revision=revision, graph_payload=command.graph_payload)
                    ),
                    jsonb(revision.model_dump(mode="json")),
                    jsonb(command.graph_payload),
                ),
            )
        alembic(url, "upgrade", "head")
        with pytest.raises(PersistenceIntegrityError):
            bundle.publication_admission.register(admission_policy(ref))
        # Unprotected history alone can downgrade; no protected authority is lost.
        alembic(url, "downgrade", "0016_operator_source_attestation")
        changed = ref.model_copy(update={"descriptor_sha256": "0" * 64})
        other = raw_command(changed, "world:ambiguous-history")
        other_digest = canonical_sha256(other.graph_payload)
        other_revision = revision.model_copy(
            update={
                "world_id": other.world_id,
                "revision_id": compute_revision_id(
                    world_id=other.world_id,
                    parent_revision_id=None,
                    operation_ids=other.operation_ids,
                    graph_schema=other.graph_schema,
                    graph_payload_sha256=other_digest,
                ),
                "graph_payload_sha256": other_digest,
            }
        )
        with bundle.database.transaction() as conn:
            lock_world(conn, other.world_id, created_at=REVIEWED_AT)
            conn.execute(
                "INSERT INTO dungeonmind.graph_revisions(world_id,revision_id,parent_revision_id,"
                "created_at,graph_schema,graph_payload_sha256,schema_version,record_fingerprint,"
                "revision_payload,graph_payload) VALUES(%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s)",
                (
                    other_revision.world_id,
                    other_revision.revision_id,
                    other_revision.created_at,
                    other_revision.graph_schema,
                    other_digest,
                    other_revision.schema_version,
                    model_fingerprint(
                        StoredGraphRevision(
                            revision=other_revision, graph_payload=other.graph_payload
                        )
                    ),
                    jsonb(other_revision.model_dump(mode="json")),
                    jsonb(other.graph_payload),
                ),
            )
        rejected = alembic(url, "upgrade", "head", check=False)
        assert (
            rejected.returncode != 0
            and "ambiguous historical profile descriptor" in rejected.stderr
        )
        with bundle.database.transaction() as conn:
            conn.execute(
                "DELETE FROM dungeonmind.graph_revisions WHERE world_id=%s", (other.world_id,)
            )
        alembic(url, "upgrade", "head")
        # Valid direct finalized-review history survives a downgrade/re-upgrade
        # as irreversible unprotected use too, even without a graph using its profile.
        migration_lane = setup_pg(bundle, protected=False)
        from dungeonmind.application.contribution_review_v4 import _build_review_state
        from tests.unit.test_contribution_review_v3_contract import typed_intent
        from tests.unit.test_contribution_review_v4 import submission, upgrade_intent

        review_only_ref = unused_ref()
        intent = typed_intent().model_copy(update={"operation_id": "reviewop:" + uuid4().hex})
        intent.plan_ref = intent.plan_ref.model_copy(
            update={
                "semantic_profile": review_only_ref,
                "source_plan_id": "plan:review-only-history",
                "expected_parent_revision_id": migration_lane.parent.revision.revision_id,
                "base_graph_payload_sha256": migration_lane.parent.revision.graph_payload_sha256,
                "base_graph_schema": migration_lane.parent.revision.graph_schema,
            }
        )
        bundle.contribution_reviews.finalize(
            _build_review_state(submission(upgrade_intent(intent)))
        )
        alembic(url, "downgrade", "0016_operator_source_attestation")
        alembic(url, "upgrade", "head")
        with pytest.raises(PersistenceIntegrityError):
            bundle.publication_admission.register(admission_policy(review_only_ref))
        bundle.publication_admission.register(admission_policy(unused_ref()))
        refused = alembic(url, "downgrade", "0016_operator_source_attestation", check=False)
        assert refused.returncode != 0 and "cannot discard protected" in refused.stderr
    finally:
        with connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
