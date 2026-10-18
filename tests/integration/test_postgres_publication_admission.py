"""Real PostgreSQL owning admission gate; unique disposable database required."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from dungeonmind.application.contribution_review_v4 import _build_review_state
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.publication_admission import PublicationAdmissionRegistry
from dungeonmind.application.review_materialization_v4 import materialize_finalized_review_v4
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.review_publication import (
    FinalizedReviewPublicationCommand,
    FinalizedReviewPublicationCommandV2,
    FinalizedReviewPublicationV2,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.postgres import (
    PostgresFinalizedReviewPublicationRepository,
    PostgresPublicationAdmissionRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from tests.unit.test_contribution_review_v2 import (
    REVIEWED_AT,
    WORLD_ID,
    _v6_parent_payload,
    load_builtin_v3_descriptor,
)
from tests.unit.test_contribution_review_v3 import source_snapshot
from tests.unit.test_contribution_review_v3_contract import typed_intent
from tests.unit.test_contribution_review_v4 import submission, upgrade_intent
from tests.unit.test_publication_admission import SyntheticValidator, admission_policy

pytestmark = pytest.mark.integration


def setup_pg(pg, *, validator=None, protected=True, failure_hook=None):
    descriptor = load_builtin_v3_descriptor().model_copy(
        update={"profile_revision": "admission-" + uuid4().hex}
    )
    ref = SemanticProfileRef(
        profile_id=descriptor.profile_id,
        profile_revision=descriptor.profile_revision,
        descriptor_sha256=canonical_sha256(descriptor.model_dump(mode="json")),
    )
    reader = VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )
    authority = PostgresPublicationAdmissionRepository(pg.database)
    policy = admission_policy(ref)
    if protected:
        authority.register(policy)
    payload = _v6_parent_payload()
    payload["semantic_profile"] = ref.model_dump(mode="json")
    pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["adoption:test"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload,
            created_at=REVIEWED_AT,
        )
    )
    parent = pg.world_graph.get_revision(
        WORLD_ID, pg.world_graph.get_head(WORLD_ID).head_revision_id
    )
    snapshot = source_snapshot()
    for artifact in snapshot.artifacts.values():
        pg.sources.put_artifact(artifact)
    for revision in snapshot.revisions.values():
        pg.sources.put_revision(revision)
    old = typed_intent()
    old.plan_ref = old.plan_ref.model_copy(
        update={
            "semantic_profile": ref,
            "expected_parent_revision_id": parent.revision.revision_id,
            "base_graph_payload_sha256": parent.revision.graph_payload_sha256,
        }
    )
    intent = upgrade_intent(old)
    state = pg.contribution_reviews.finalize(_build_review_state(submission(intent)))
    body = materialize_finalized_review_v4(
        state, parent=parent, graph_reader=reader, source_snapshot=snapshot
    ).graph_payload
    command = FinalizedReviewPublicationCommandV2(
        world_id=WORLD_ID,
        review_id=state.record.review_id,
        reviewed_contribution_id=state.record.reviewed_contribution_id,
        reviewed_contribution_sha256=state.record.reviewed_contribution_sha256,
        review_intent_sha256=state.record.review_intent_sha256,
        confirmation_id=state.record.confirmation_id,
        operation_id=state.record.operation_id,
        expected_parent_revision_id=parent.revision.revision_id,
        parent_graph_payload_sha256=parent.revision.graph_payload_sha256,
        expected_published_revision_id=compute_revision_id(
            world_id=WORLD_ID,
            parent_revision_id=parent.revision.revision_id,
            operation_ids=[state.record.operation_id],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload_sha256=canonical_sha256(body),
        ),
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload=body,
        graph_payload_sha256=canonical_sha256(body),
        requested_published_at=REVIEWED_AT,
        admission_policy_ref=policy.reference,
        validator_ref=policy.validator_ref,
    )
    registry = (
        PublicationAdmissionRegistry((("synthetic.complete-set", "v1", validator),))
        if validator
        else None
    )
    publications = PostgresFinalizedReviewPublicationRepository(
        pg.database, admission_registry=registry, failure_hook=failure_hook
    )
    return SimpleNamespace(
        pg=pg,
        authority=authority,
        policy=policy,
        ref=ref,
        parent=parent,
        state=state,
        command=command,
        publications=publications,
        reader=reader,
        snapshot=snapshot,
    )


def counts(pg):
    with pg.database.connect() as conn:
        result = {
            table: conn.execute(f"SELECT count(*) AS n FROM dungeonmind.{table}").fetchone()["n"]
            for table in (
                "graph_revisions",
                "finalized_review_publications",
                "world_graph_head_events",
            )
        }
    return result, pg.world_graph.get_head(WORLD_ID)


def test_real_atomic_v2_and_default_empty_registry_denial(pg):
    lane = setup_pg(pg)
    before = counts(pg)
    with pytest.raises(PersistenceIntegrityError) as exc:
        lane.publications.publish(lane.command)
    assert exc.value.details["reason"] == "validator_unavailable"
    assert counts(pg) == before
    validator = SyntheticValidator()
    lane.publications = PostgresFinalizedReviewPublicationRepository(
        pg.database,
        admission_registry=PublicationAdmissionRegistry(
            (("synthetic.complete-set", "v1", validator),)
        ),
    )
    receipt = lane.publications.publish(lane.command)
    assert isinstance(receipt, FinalizedReviewPublicationV2) and len(validator.calls) == 1
    assert lane.publications.publish(lane.command) == receipt and len(validator.calls) == 1


@pytest.mark.parametrize(
    "case",
    [
        "legacy",
        "policy_mismatch",
        "profile_substitution",
        "raw_adoption",
        "validator_reject",
        "after_revision",
        "after_receipt",
    ],
)
def test_direct_gate_refusals_and_atomic_rollback(pg, case):
    calls = []

    def hook():
        calls.append(1)
        if len(calls) == (1 if case == "after_revision" else 2):
            raise RuntimeError("synthetic transaction failure")

    validator = SyntheticValidator(
        reason="accepted_set_mismatch" if case == "validator_reject" else None
    )
    lane = setup_pg(
        pg, validator=validator, failure_hook=hook if case.startswith("after_") else None
    )
    if case == "legacy":
        lane.command = FinalizedReviewPublicationCommand(
            **lane.command.model_dump(
                mode="python", exclude={"schema_version", "admission_policy_ref", "validator_ref"}
            )
        )
    elif case == "policy_mismatch":
        lane.command.admission_policy_ref = lane.command.admission_policy_ref.model_copy(
            update={"policy_sha256": "0" * 64}
        )
    elif case == "profile_substitution":
        lane.command.graph_payload["semantic_profile"]["descriptor_sha256"] = "0" * 64
        lane.command.graph_payload_sha256 = canonical_sha256(lane.command.graph_payload)
        lane.command.expected_published_revision_id = compute_revision_id(
            world_id=WORLD_ID,
            parent_revision_id=lane.command.expected_parent_revision_id,
            operation_ids=[lane.command.operation_id],
            graph_schema=lane.command.graph_schema,
            graph_payload_sha256=lane.command.graph_payload_sha256,
        )
    elif case == "raw_adoption":
        pg.world_graph.publish_revision(
            PublishRevisionCommand(
                world_id=WORLD_ID,
                parent_revision_id=lane.command.expected_parent_revision_id,
                expected_parent_revision_id=lane.command.expected_parent_revision_id,
                operation_ids=[lane.command.operation_id],
                graph_schema=lane.command.graph_schema,
                graph_payload=lane.command.graph_payload,
                created_at=REVIEWED_AT,
            )
        )
    before = counts(pg)
    with pytest.raises((PersistenceIntegrityError, RuntimeError)):
        lane.publications.publish(lane.command)
    assert counts(pg) == before


def test_application_durable_selection_and_history(pg):
    from dungeonmind.application.review_publication import publish_finalized_review

    lane = setup_pg(pg, validator=SyntheticValidator())
    receipt = publish_finalized_review(
        WORLD_ID,
        lane.state.record.review_id,
        published_at=REVIEWED_AT,
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=lane.publications,
        graph_reader=lane.reader,
    )
    assert isinstance(receipt, FinalizedReviewPublicationV2)
    history = lane.publications.read_verified_ancestry(WORLD_ID, receipt.published_revision_id)
    assert history[0].publication == receipt


def retract_source(pg, artifact_id, *, observed=None):
    from dungeonmind.contracts.evidence import SourceStatus
    from dungeonmind.infrastructure.postgres.database import jsonb
    from dungeonmind.infrastructure.postgres.serialization import model_fingerprint

    artifact = pg.sources.get_artifact(artifact_id).model_copy(
        update={"status": SourceStatus.RETRACTED}
    )
    with pg.database.transaction() as conn:
        if observed is not None:
            observed["pid"] = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            observed["started"].set()
        conn.execute(
            "UPDATE dungeonmind.source_artifacts SET status=%s,payload=%s,record_fingerprint=%s "
            "WHERE source_artifact_id=%s",
            (
                artifact.status.value,
                jsonb(artifact.model_dump(mode="json")),
                model_fingerprint(artifact),
                artifact_id,
            ),
        )


def test_withdrawn_before_admission_refuses_zero_writes(pg):
    lane = setup_pg(pg, validator=SyntheticValidator())
    retract_source(pg, next(iter(lane.snapshot.artifacts)))
    before = counts(pg)
    with pytest.raises(PersistenceIntegrityError) as exc:
        lane.publications.publish(lane.command)
    assert exc.value.details["reason"] == "domain_invalid"
    assert counts(pg) == before


def test_real_source_writer_waits_for_same_admission_transaction_then_history_replays(
    pg, monkeypatch
):
    import threading
    from time import monotonic, sleep

    lane = setup_pg(pg, validator=SyntheticValidator())
    validated, release = threading.Event(), threading.Event()
    writer_observed = {"started": threading.Event()}
    pids, receipts, errors = {}, [], []
    actual_snapshot = lane.publications._locked_source_snapshot
    actual_validate = lane.publications._admission_registry.validate

    def snapshot(conn, **kwargs):
        pids["publisher"] = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
        return actual_snapshot(conn, **kwargs)

    def pause(*args):
        actual_validate(*args)
        validated.set()
        assert release.wait(10)

    monkeypatch.setattr(lane.publications, "_locked_source_snapshot", snapshot)
    monkeypatch.setattr(lane.publications._admission_registry, "validate", pause)

    def publish():
        try:
            receipts.append(lane.publications.publish(lane.command))
        except BaseException as exc:
            errors.append(exc)

    def write():
        try:
            retract_source(pg, next(iter(lane.snapshot.artifacts)), observed=writer_observed)
        except BaseException as exc:
            errors.append(exc)

    publisher, writer = threading.Thread(target=publish), threading.Thread(target=write)
    publisher.start()
    try:
        assert validated.wait(10), repr(errors)
        writer.start()
        assert writer_observed["started"].wait(10), repr(errors)
        deadline = monotonic() + 5
        blocked = False
        while monotonic() < deadline:
            with pg.database.connect() as conn:
                blocked = conn.execute(
                    "SELECT %s=ANY(pg_blocking_pids(%s)) AS blocked",
                    (pids["publisher"], writer_observed["pid"]),
                ).fetchone()["blocked"]
            if blocked:
                break
            sleep(0.01)
        assert blocked and writer.is_alive()
    finally:
        release.set()
        publisher.join(10)
        if writer.ident is not None:
            writer.join(10)
    assert not errors and not publisher.is_alive() and not writer.is_alive()
    assert len(receipts) == 1
    assert lane.publications.publish(lane.command) == receipts[0]
    assert pg.sources.get_artifact(next(iter(lane.snapshot.artifacts))).status == "retracted"


def test_two_protected_reviews_race_one_cas_winner(pg):
    import threading

    from dungeonmind.domain.errors import StaleParentRevisionError

    lane = setup_pg(pg, validator=SyntheticValidator())
    old = typed_intent().model_copy(update={"operation_id": "reviewop:" + uuid4().hex})
    old.plan_ref = old.plan_ref.model_copy(
        update={
            "source_plan_id": "plan:second-protected",
            "semantic_profile": lane.ref,
            "expected_parent_revision_id": lane.parent.revision.revision_id,
            "base_graph_payload_sha256": lane.parent.revision.graph_payload_sha256,
        }
    )
    state = pg.contribution_reviews.finalize(_build_review_state(submission(upgrade_intent(old))))
    body = materialize_finalized_review_v4(
        state, parent=lane.parent, graph_reader=lane.reader, source_snapshot=lane.snapshot
    ).graph_payload
    record = state.record
    command = lane.command.model_copy(
        update=dict(
            review_id=record.review_id,
            reviewed_contribution_id=record.reviewed_contribution_id,
            reviewed_contribution_sha256=record.reviewed_contribution_sha256,
            review_intent_sha256=record.review_intent_sha256,
            confirmation_id=record.confirmation_id,
            operation_id=record.operation_id,
            graph_payload=body,
            graph_payload_sha256=canonical_sha256(body),
            expected_published_revision_id=compute_revision_id(
                world_id=WORLD_ID,
                parent_revision_id=lane.parent.revision.revision_id,
                operation_ids=[record.operation_id],
                graph_schema=GRAPH_SCHEMA_V6,
                graph_payload_sha256=canonical_sha256(body),
            ),
        )
    )
    start = threading.Barrier(2)
    receipts = []
    errors = []
    before = counts(pg)[0]

    def publish(cmd):
        start.wait()
        try:
            receipts.append(lane.publications.publish(cmd))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish, args=(cmd,)) for cmd in (lane.command, command)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert all(not thread.is_alive() for thread in threads)
    assert len(receipts) == len(errors) == 1 and isinstance(errors[0], StaleParentRevisionError)
    after = counts(pg)[0]
    assert all(after[key] - before[key] == 1 for key in before)
