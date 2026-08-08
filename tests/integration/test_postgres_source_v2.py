"""PostgreSQL roundtrip for ``dm_source_artifact_v2``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceDomain,
    SourceRevision,
    SourceStatus,
    WorkspaceDocumentRefV1,
)
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import IdempotencyConflictError
from tests.conftest import WORLD_ID

NOW = datetime(2026, 8, 7, 12, 0, 0, tzinfo=UTC)


def _artifact_v2(
    *,
    source_artifact_id: str = "src:pg-v2",
    source_domain: SourceDomain | None = SourceDomain.WORLDBUILDING,
    visibility: Visibility | None = Visibility.GM,
) -> SourceArtifactV2:
    return SourceArtifactV2(
        source_artifact_id=source_artifact_id,
        source_domain_key="buddy.worldbuilding",
        source_domain=source_domain,
        world_id=WORLD_ID,
        campaign_id=None,
        session_id=None,
        uri=None,
        current_revision_id=None,
        authority=None,
        visibility=visibility,
        artifact_kind="note",
        document_class=None,
        review_state=None,
        source_visibility_state=None,
        workspace_document_ref=WorkspaceDocumentRefV1(
            document_id="doc:pg-v2", revision=1
        ),
        lineage={"batch": "pg-v2"},
        status=SourceStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.integration
def test_source_artifact_v2_roundtrip(pg) -> None:
    artifact = _artifact_v2()
    assert pg.sources.put_artifact(artifact) == artifact
    assert pg.sources.get_artifact("src:pg-v2") == artifact


@pytest.mark.integration
def test_source_artifact_v2_nullable_axes_roundtrip(pg) -> None:
    artifact = _artifact_v2(source_domain=None, visibility=None)
    assert pg.sources.put_artifact(artifact) == artifact
    got = pg.sources.get_artifact("src:pg-v2")
    assert got is not None
    assert got.source_domain is None
    assert got.visibility is None


@pytest.mark.integration
def test_source_artifact_v2_null_timestamps_roundtrip(pg) -> None:
    artifact = _artifact_v2()
    artifact = artifact.model_copy(update={"created_at": None, "updated_at": None})
    assert pg.sources.put_artifact(artifact) == artifact
    got = pg.sources.get_artifact("src:pg-v2")
    assert got is not None
    assert got.created_at is None
    assert got.updated_at is None


@pytest.mark.integration
def test_source_artifact_v2_idempotency_conflict(pg) -> None:
    artifact = _artifact_v2()
    pg.sources.put_artifact(artifact)
    with pytest.raises(IdempotencyConflictError):
        pg.sources.put_artifact(artifact.model_copy(update={"artifact_kind": "other"}))


@pytest.mark.integration
def test_source_artifact_v2_revision_roundtrip(pg) -> None:
    artifact = _artifact_v2()
    pg.sources.put_artifact(artifact)
    revision = SourceRevision(
        source_revision_id="srev:pg-v2",
        source_artifact_id="src:pg-v2",
        content_sha256="ef" * 32,
        locator="r2://dm/src-pg-v2",
        created_at=NOW,
    )
    pg.sources.put_revision(revision)
    assert pg.sources.list_revisions("src:pg-v2") == [revision]
