"""Native catalog comparison owns scope/protection without mutating admission."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from dungeonmind.application.source_admission import (
    load_admitted_source_pair,
    match_admitted_source_revision,
)
from dungeonmind.contracts.evidence import SourceArtifactV2, SourceRevision
from dungeonmind.domain.errors import IdempotencyConflictError, PersistenceIntegrityError
from dungeonmind.infrastructure.memory import InMemorySourceRepository

NOW = datetime(2026, 10, 30, tzinfo=UTC)
DIGEST = sha256(b"Synthetic catalog comparison source.").hexdigest()


def records():
    artifact = SourceArtifactV2(
        source_artifact_id="source:synthetic",
        source_domain_key="worldbuilding",
        source_domain="worldbuilding",
        world_id="world:synthetic",
        campaign_id=None,
        session_id=None,
        uri="object://original",
        current_revision_id="revision:synthetic",
        authority=None,
        visibility="gm",
        artifact_kind="markdown",
        document_class="lore",
        review_state="reviewed",
        source_visibility_state="internal",
        workspace_document_ref=None,
        lineage={"producer": "synthetic"},
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    revision = SourceRevision(
        source_revision_id="revision:synthetic",
        source_artifact_id=artifact.source_artifact_id,
        content_sha256=DIGEST,
        body_storage="object_store",
        locator=artifact.uri,
        created_at=NOW,
    )
    return artifact, revision


def stored():
    source = InMemorySourceRepository()
    artifact, revision = records()
    source.put_artifact(artifact)
    source.put_revision(revision)
    return source, artifact, revision


def match(source, artifact, revision, verified=None):
    return match_admitted_source_revision(
        artifact=artifact,
        revision=revision,
        verified_input_sha256=verified,
        source_repository=source,
    )


def test_matching_returns_catalog_records_and_preserves_metadata():
    source, artifact, revision = stored()
    stored_artifact = artifact.model_copy(
        update={
            "lineage": {**artifact.lineage, "native_review": "kept"},
            "updated_at": NOW + timedelta(days=1),
        }
    )
    source._artifacts[artifact.source_artifact_id] = stored_artifact
    incoming = artifact.model_copy(update={"uri": "object://different-local-mirror"})
    assert match(source, incoming, revision, DIGEST) == (stored_artifact, revision)
    assert source.get_artifact(artifact.source_artifact_id) == stored_artifact
    assert source.get_revision(revision.source_revision_id) == revision
    assert not source._source_admissions


def test_missing_pair_is_not_admitted_and_half_pair_is_corrupt():
    source = InMemorySourceRepository()
    artifact, revision = records()
    assert match(source, artifact, revision) is None
    source.put_artifact(artifact)
    with pytest.raises(PersistenceIntegrityError, match="one half"):
        match(source, artifact, revision)
    assert source.get_revision(revision.source_revision_id) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("world_id", "other-world"),
        ("campaign_id", "other-campaign"),
        ("source_domain_key", "other-domain"),
        ("visibility", "player"),
        ("review_state", "draft"),
        ("source_visibility_state", "external"),
        ("status", "retracted"),
        ("current_revision_id", "other-revision"),
        ("lineage", {"producer": "changed"}),
        ("authority", "primary"),
        ("document_class", "recap"),
    ],
)
def test_changed_metadata_fails_closed(field, value):
    source, artifact, revision = stored()
    with pytest.raises(IdempotencyConflictError):
        match(source, artifact.model_copy(update={field: value}), revision, DIGEST)
    assert source.get_artifact(artifact.source_artifact_id) == artifact
    assert not source._source_admissions


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_artifact_id", "other-artifact"),
        ("content_sha256", "f" * 64),
        ("body_storage", "external"),
    ],
)
def test_changed_revision_fails_closed(field, value):
    source, artifact, revision = stored()
    with pytest.raises(IdempotencyConflictError):
        match(source, artifact, revision.model_copy(update={field: value}), DIGEST)


def test_alternate_mirror_requires_matching_verified_digest():
    source, artifact, revision = stored()
    incoming = artifact.model_copy(update={"uri": "object://mirror"})
    for verified in (None, "f" * 64):
        with pytest.raises(IdempotencyConflictError):
            match(source, incoming, revision, verified)
    assert match(source, incoming, revision, DIGEST) == (artifact, revision)
    with pytest.raises(IdempotencyConflictError):
        match(source, artifact, revision, "f" * 64)


def test_catalog_pair_cannot_change_current_revision():
    source, artifact, revision = stored()
    source._artifacts[artifact.source_artifact_id] = artifact.model_copy(
        update={"current_revision_id": "later"}
    )
    with pytest.raises(IdempotencyConflictError):
        load_admitted_source_pair(
            world_id=artifact.world_id,
            source_artifact_id=artifact.source_artifact_id,
            source_revision_id=revision.source_revision_id,
            source_repository=source,
        )


def test_revision_locator_is_the_input_mirror_when_artifact_has_no_uri():
    source = InMemorySourceRepository()
    artifact, revision = records()
    artifact = artifact.model_copy(update={"uri": None})
    source.put_artifact(artifact)
    source.put_revision(revision)
    incoming = revision.model_copy(update={"locator": "object://another-mirror"})
    with pytest.raises(IdempotencyConflictError):
        match(source, artifact, incoming)
    assert match(source, artifact, incoming, DIGEST) == (artifact, revision)


def test_native_postgres_body_can_have_no_external_locator():
    source = InMemorySourceRepository()
    artifact, revision = records()
    artifact = artifact.model_copy(update={"uri": None})
    revision = revision.model_copy(update={"body_storage": "postgres", "locator": None})
    source.put_artifact(artifact)
    source.put_revision(revision)
    assert match(source, artifact, revision) == (artifact, revision)
