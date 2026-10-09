"""PostgreSQL owning-boundary proofs for legacy source-pair admission."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from dungeonmind.application.source_admission import (
    admit_source_revision,
    source_admission_command_sha256,
)
from dungeonmind.contracts.evidence import (
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.source_admission import (
    SourceAdmissionReceiptV1,
)
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import (
    HeadNotFoundError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    StaleParentRevisionError,
)

pytestmark = pytest.mark.integration

WORLD_ID = "world:synthetic-source-admission"
BODY = b"A short synthetic source body used in an integration test."
CONTENT_SHA256 = sha256(BODY).hexdigest()
ARTIFACT_ID = "artifact:synthetic:source-admission"
REVISION_ID = f"sha256:{CONTENT_SHA256}"
NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def _records(*, world_id: str = WORLD_ID):
    artifact = SourceArtifact(
        source_artifact_id=ARTIFACT_ID,
        source_domain=SourceDomain.SESSION_RECAP,
        world_id=world_id,
        campaign_id="campaign:synthetic",
        session_id="session:synthetic",
        current_revision_id=REVISION_ID,
        created_at=NOW,
        visibility=Visibility.GM,
        status=SourceStatus.ACTIVE,
    )
    revision = SourceRevision(
        source_revision_id=REVISION_ID,
        source_artifact_id=ARTIFACT_ID,
        content_sha256=CONTENT_SHA256,
        body_storage="external",
        locator="test://synthetic/source-admission",
        created_at=NOW,
    )
    return artifact, revision


def _setup_world(pg):
    return pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["operation:source-admission-root"],
            graph_schema="dm_union_graph_v1",
            graph_payload={"world_id": WORLD_ID, "nodes": []},
            created_at=NOW,
        )
    )


def _request(pg, head_revision_id: str, *, admission_id: str = "admission:synthetic"):
    artifact, revision = _records()
    return dict(
        world_id=WORLD_ID,
        admission_id=admission_id,
        expected_head_revision_id=head_revision_id,
        artifact=artifact,
        revision=revision,
        source_body=BODY,
        admitted_at=NOW,
        world_graph_repository=pg.world_graph,
        source_repository=pg.sources,
    )


def test_postgres_source_admission_atomically_stores_pair_and_receipt(pg) -> None:
    parent = _setup_world(pg)

    receipt = admit_source_revision(**_request(pg, parent.revision_id))

    assert receipt.world_id == WORLD_ID
    assert pg.sources.get_artifact(ARTIFACT_ID) == _records()[0]
    assert pg.sources.get_revision(REVISION_ID) == _records()[1]
    assert pg.sources.get_source_admission(receipt.admission_id) == receipt
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == parent.revision_id


def test_postgres_source_admission_exact_replay_returns_stored_receipt(pg) -> None:
    parent = _setup_world(pg)
    request = _request(pg, parent.revision_id)
    original = admit_source_revision(**request)

    replay = admit_source_revision(
        **{**request, "admitted_at": NOW + timedelta(hours=1)}
    )

    assert replay == original
    assert pg.sources.list_artifacts_for_world(WORLD_ID) == [_records()[0]]
    assert pg.sources.list_revisions(ARTIFACT_ID) == [_records()[1]]


def test_postgres_source_admission_recovers_a_committed_lost_response(
    pg, monkeypatch
) -> None:
    parent = _setup_world(pg)
    request = _request(pg, parent.revision_id)
    original_admit = pg.sources.admit_source_revision
    failed_once = False

    def commit_then_lose_response(**kwargs):
        nonlocal failed_once
        receipt = original_admit(**kwargs)
        if not failed_once:
            failed_once = True
            raise RuntimeError("synthetic lost PostgreSQL response")
        return receipt

    monkeypatch.setattr(pg.sources, "admit_source_revision", commit_then_lose_response)

    receipt = admit_source_revision(**request)

    assert failed_once
    assert receipt == pg.sources.get_source_admission("admission:synthetic")
    assert pg.sources.get_artifact(ARTIFACT_ID) == _records()[0]
    assert pg.sources.get_revision(REVISION_ID) == _records()[1]


def test_postgres_source_admission_conflicting_replay_is_rejected(pg) -> None:
    parent = _setup_world(pg)
    request = _request(pg, parent.revision_id)
    admit_source_revision(**request)
    changed_artifact = request["artifact"].model_copy(update={"uri": "test://changed"})

    with pytest.raises(IdempotencyConflictError):
        admit_source_revision(**{**request, "artifact": changed_artifact})

    assert pg.sources.list_artifacts_for_world(WORLD_ID) == [_records()[0]]
    assert len(pg.sources.list_revisions(ARTIFACT_ID)) == 1


def test_postgres_source_admission_rejects_missing_world_at_repository_boundary(pg) -> None:
    artifact, revision = _records()
    command_sha = source_admission_command_sha256(
        world_id=WORLD_ID,
        expected_head_revision_id="revision:expected",
        artifact=artifact,
        revision=revision,
    )
    receipt = SourceAdmissionReceiptV1(
        admission_id="admission:missing-world",
        world_id=WORLD_ID,
        expected_head_revision_id="revision:expected",
        source_artifact_id=ARTIFACT_ID,
        source_revision_id=REVISION_ID,
        content_sha256=CONTENT_SHA256,
        command_sha256=command_sha,
        admitted_at=NOW,
    )

    with pytest.raises(HeadNotFoundError):
        pg.sources.admit_source_revision(
            receipt=receipt, artifact=artifact, revision=revision, source_body=BODY
        )

    assert pg.sources.get_artifact(ARTIFACT_ID) is None
    assert pg.sources.get_revision(REVISION_ID) is None
    assert pg.sources.get_source_admission(receipt.admission_id) is None


def test_postgres_source_admission_expected_head_is_checked_at_repository_boundary(
    pg,
) -> None:
    parent = _setup_world(pg)
    child = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=parent.revision_id,
            expected_parent_revision_id=parent.revision_id,
            operation_ids=["operation:source-admission-head-advance"],
            graph_schema="dm_union_graph_v1",
            graph_payload={"world_id": WORLD_ID, "nodes": [], "advanced": True},
            created_at=NOW + timedelta(minutes=1),
        )
    )
    artifact, revision = _records()
    receipt = SourceAdmissionReceiptV1(
        admission_id="admission:stale-head",
        world_id=WORLD_ID,
        expected_head_revision_id=parent.revision_id,
        source_artifact_id=ARTIFACT_ID,
        source_revision_id=REVISION_ID,
        content_sha256=CONTENT_SHA256,
        command_sha256=source_admission_command_sha256(
            world_id=WORLD_ID,
            expected_head_revision_id=parent.revision_id,
            artifact=artifact,
            revision=revision,
        ),
        admitted_at=NOW,
    )

    with pytest.raises(StaleParentRevisionError):
        pg.sources.admit_source_revision(
            receipt=receipt, artifact=artifact, revision=revision, source_body=BODY
        )

    assert pg.sources.get_artifact(ARTIFACT_ID) is None
    assert pg.sources.get_revision(REVISION_ID) is None
    assert pg.sources.get_source_admission(receipt.admission_id) is None
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == child.revision_id


def test_postgres_source_admission_rejects_foreign_world_and_hash_mismatch(pg) -> None:
    parent = _setup_world(pg)
    request = _request(pg, parent.revision_id)
    foreign = request["artifact"].model_copy(update={"world_id": "world:other"})

    with pytest.raises(ValueError, match="different World"):
        admit_source_revision(**{**request, "artifact": foreign})
    with pytest.raises(ValueError, match="digest"):
        admit_source_revision(**{**request, "source_body": b"different bytes"})

    assert pg.sources.get_artifact(ARTIFACT_ID) is None
    assert pg.sources.get_revision(REVISION_ID) is None
    assert pg.sources.get_source_admission("admission:synthetic") is None


def test_postgres_source_repository_rejects_forged_world_or_body_binding(pg) -> None:
    artifact, revision = _records()

    def make_receipt(candidate_artifact):
        return SourceAdmissionReceiptV1(
            admission_id="admission:direct-binding",
            world_id=WORLD_ID,
            expected_head_revision_id="revision:expected",
            source_artifact_id=ARTIFACT_ID,
            source_revision_id=REVISION_ID,
            content_sha256=CONTENT_SHA256,
            command_sha256=source_admission_command_sha256(
                world_id=WORLD_ID,
                expected_head_revision_id="revision:expected",
                artifact=candidate_artifact,
                revision=revision,
            ),
            admitted_at=NOW,
        )

    with pytest.raises(PersistenceIntegrityError):
        pg.sources.admit_source_revision(
            receipt=make_receipt(artifact),
            artifact=artifact,
            revision=revision,
            source_body=b"different body",
        )
    foreign_artifact = artifact.model_copy(update={"world_id": "world:other"})
    with pytest.raises(PersistenceIntegrityError):
        pg.sources.admit_source_revision(
            receipt=make_receipt(foreign_artifact),
            artifact=foreign_artifact,
            revision=revision,
            source_body=BODY,
        )

    assert pg.sources.get_artifact(ARTIFACT_ID) is None
    assert pg.sources.get_revision(REVISION_ID) is None
    assert pg.sources.get_source_admission("admission:direct-binding") is None


def test_postgres_source_admission_transaction_rolls_back_pair_on_receipt_failure(
    pg, monkeypatch
) -> None:
    parent = _setup_world(pg)
    request = _request(pg, parent.revision_id)

    def fail_before_receipt(*args, **kwargs):
        raise RuntimeError("synthetic receipt write failure")

    monkeypatch.setattr(
        "dungeonmind.infrastructure.postgres.records._insert_source_admission_receipt",
        fail_before_receipt,
    )
    with pytest.raises(RuntimeError, match="synthetic receipt write failure"):
        admit_source_revision(**request)

    assert pg.sources.get_artifact(ARTIFACT_ID) is None
    assert pg.sources.get_revision(REVISION_ID) is None
    assert pg.sources.get_source_admission("admission:synthetic") is None
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == parent.revision_id
