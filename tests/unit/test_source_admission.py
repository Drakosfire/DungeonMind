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
from dungeonmind.contracts.source_admission import SourceAdmissionReceiptV1
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import (
    HeadNotFoundError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    StaleParentRevisionError,
)
from dungeonmind.infrastructure.memory import (
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)

WORLD_ID = "world:source-admission-test"
BODY = b"A short synthetic recap used by a unit test."
CONTENT_SHA256 = sha256(BODY).hexdigest()
ARTIFACT_ID = "artifact:recap:campaign-a:session-1"
REVISION_ID = f"sha256:{CONTENT_SHA256}"
FIXED_NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def _records():
    artifact = SourceArtifact(
        source_artifact_id=ARTIFACT_ID,
        source_domain=SourceDomain.SESSION_RECAP,
        world_id=WORLD_ID,
        campaign_id="campaign-a",
        session_id="session-1",
        current_revision_id=REVISION_ID,
        created_at=FIXED_NOW,
        visibility=Visibility.GM,
        status=SourceStatus.ACTIVE,
    )
    revision = SourceRevision(
        source_revision_id=REVISION_ID,
        source_artifact_id=ARTIFACT_ID,
        content_sha256=CONTENT_SHA256,
        body_storage="external",
        locator="test://synthetic/recap",
        created_at=FIXED_NOW,
    )
    return artifact, revision


def _setup():
    graph = InMemoryWorldGraphRepository()
    root = graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["operation:source-admission-test-root"],
            graph_schema="dm_union_graph_v1",
            graph_payload={"world_id": WORLD_ID, "nodes": []},
            created_at=FIXED_NOW,
        )
    )
    sources = InMemorySourceRepository()
    artifact, revision = _records()
    kwargs = dict(
        world_id=WORLD_ID,
        admission_id="admission:one",
        expected_head_revision_id=root.revision_id,
        artifact=artifact,
        revision=revision,
        source_body=BODY,
        admitted_at=FIXED_NOW,
        world_graph_repository=graph,
        source_repository=sources,
    )
    return graph, sources, kwargs


def test_source_admission_stores_pair_and_returns_receipt_without_graph_write():
    graph, sources, kwargs = _setup()

    receipt = admit_source_revision(**kwargs)

    assert receipt.world_id == WORLD_ID
    assert receipt.source_artifact_id == ARTIFACT_ID
    assert receipt.source_revision_id == REVISION_ID
    assert receipt.content_sha256 == CONTENT_SHA256
    assert sources.get_artifact(ARTIFACT_ID) == kwargs["artifact"]
    assert sources.get_revision(REVISION_ID) == kwargs["revision"]
    assert sources.get_source_admission("admission:one") == receipt
    assert graph.get_head(WORLD_ID).head_revision_id == kwargs["expected_head_revision_id"]


def test_source_admission_exact_replay_returns_original_receipt():
    _, sources, kwargs = _setup()
    first = admit_source_revision(**kwargs)

    replay = admit_source_revision(
        **{**kwargs, "admitted_at": FIXED_NOW + timedelta(hours=2)}
    )

    assert replay == first
    assert sources.get_source_admission("admission:one") == first


def test_source_admission_recovers_a_committed_lost_response():
    graph, _, kwargs = _setup()

    class CommitThenLoseResponse(InMemorySourceRepository):
        def __init__(self):
            super().__init__()
            self.failed_once = False

        def admit_source_revision(self, **request):
            receipt = super().admit_source_revision(**request)
            if not self.failed_once:
                self.failed_once = True
                raise RuntimeError("synthetic lost response")
            return receipt

    recovering_sources = CommitThenLoseResponse()
    receipt = admit_source_revision(
        **{**kwargs, "source_repository": recovering_sources, "world_graph_repository": graph}
    )

    assert recovering_sources.get_source_admission("admission:one") == receipt
    assert recovering_sources.get_artifact(ARTIFACT_ID) == kwargs["artifact"]
    assert recovering_sources.get_revision(REVISION_ID) == kwargs["revision"]


def test_source_admission_conflicting_replay_is_rejected():
    _, _, kwargs = _setup()
    admit_source_revision(**kwargs)
    changed_artifact = kwargs["artifact"].model_copy(update={"uri": "test://changed"})

    with pytest.raises(IdempotencyConflictError):
        admit_source_revision(**{**kwargs, "artifact": changed_artifact})


def test_source_admission_requires_an_existing_world_head():
    _, _, kwargs = _setup()
    empty_graph = InMemoryWorldGraphRepository()

    with pytest.raises(HeadNotFoundError):
        admit_source_revision(**{**kwargs, "world_graph_repository": empty_graph})


def test_source_admission_rejects_stale_expected_head_before_writing():
    graph, sources, kwargs = _setup()
    graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=kwargs["expected_head_revision_id"],
            expected_parent_revision_id=kwargs["expected_head_revision_id"],
            operation_ids=["operation:source-admission-advance"],
            graph_schema="dm_union_graph_v1",
            graph_payload={"world_id": WORLD_ID, "nodes": [], "advanced": True},
            created_at=FIXED_NOW + timedelta(minutes=1),
        )
    )

    with pytest.raises(StaleParentRevisionError):
        admit_source_revision(**kwargs)

    assert sources.get_artifact(ARTIFACT_ID) is None
    assert sources.get_revision(REVISION_ID) is None
    assert sources.get_source_admission("admission:one") is None


def test_source_admission_rejects_foreign_world_artifact():
    _, _, kwargs = _setup()
    foreign_artifact = kwargs["artifact"].model_copy(update={"world_id": "world:other"})

    with pytest.raises(ValueError, match="different World"):
        admit_source_revision(**{**kwargs, "artifact": foreign_artifact})


def test_source_admission_rejects_body_hash_mismatch():
    _, _, kwargs = _setup()

    with pytest.raises(ValueError, match="digest"):
        admit_source_revision(**{**kwargs, "source_body": b"not the admitted bytes"})


def test_memory_source_repository_rejects_forged_world_or_body_binding():
    sources = InMemorySourceRepository()
    artifact, revision = _records()

    def make_receipt(candidate_artifact):
        command_sha256 = source_admission_command_sha256(
            world_id=WORLD_ID,
            expected_head_revision_id="revision:expected",
            artifact=candidate_artifact,
            revision=revision,
        )
        return SourceAdmissionReceiptV1(
            admission_id="admission:direct",
            world_id=WORLD_ID,
            expected_head_revision_id="revision:expected",
            source_artifact_id=ARTIFACT_ID,
            source_revision_id=REVISION_ID,
            content_sha256=CONTENT_SHA256,
            command_sha256=command_sha256,
            admitted_at=FIXED_NOW,
        )

    with pytest.raises(PersistenceIntegrityError):
        sources.admit_source_revision(
            receipt=make_receipt(artifact),
            artifact=artifact,
            revision=revision,
            source_body=b"different body",
        )
    foreign_artifact = artifact.model_copy(update={"world_id": "world:other"})
    with pytest.raises(PersistenceIntegrityError):
        sources.admit_source_revision(
            receipt=make_receipt(foreign_artifact),
            artifact=foreign_artifact,
            revision=revision,
            source_body=BODY,
        )

    assert sources.get_artifact(ARTIFACT_ID) is None
    assert sources.get_revision(REVISION_ID) is None
    assert sources.get_source_admission("admission:direct") is None
