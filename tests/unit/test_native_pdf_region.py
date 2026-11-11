from datetime import UTC, datetime
from hashlib import sha256

import pytest
from pydantic import ValidationError

from dungeonmind.application.vnext.native_source_admission import build_native_pdf_source_records
from dungeonmind.contracts.vnext.pdf_region import NativePdfRegionV1, NativePdfSourceAdmissionV1
from dungeonmind.contracts.vnext.source import SourceRevisionV2


@pytest.fixture
def region():
    return {
        "source_revision_id": "rev:pdf",
        "content_sha256": "a" * 64,
        "page": 1,
        "left": 0,
        "top": 0.2,
        "right": 1,
        "bottom": 0.8,
    }


def test_native_pdf_region_json_round_trip(region):
    locator = NativePdfRegionV1.model_validate(region)
    assert NativePdfRegionV1.model_validate_json(locator.model_dump_json()) == locator


@pytest.mark.parametrize(
    "invalid",
    [
        {"page": 0},
        {"page": "1"},
        {"right": 0},
        {"bottom": 0.1},
        {"left": float("nan")},
        {"top": -1},
        {"bottom": 1.01},
        {"content_sha256": "wrong"},
    ],
)
def test_native_pdf_region_rejects_invalid_locator(region, invalid):
    with pytest.raises(ValidationError):
        NativePdfRegionV1.model_validate(region | invalid)


def test_native_pdf_region_binds_exact_revision_and_page(region):
    body = b"test source bytes"
    locator = NativePdfRegionV1.model_validate(
        region | {"content_sha256": sha256(body).hexdigest()}
    )
    revision = SourceRevisionV2(
        source_revision_id=locator.source_revision_id,
        source_artifact_id="artifact:pdf",
        content_sha256=locator.content_sha256,
        body_storage="native",
        created_at=datetime.now(UTC),
    )
    locator.validate_source(revision, body=body, page_count=1)

    with pytest.raises(ValueError, match="different source revision"):
        locator.validate_source(
            revision.model_copy(update={"source_revision_id": "rev:other"}), body=body, page_count=1
        )
    with pytest.raises(ValueError, match="content hash"):
        locator.validate_source(
            revision.model_copy(update={"content_sha256": "b" * 64}), body=body, page_count=1
        )
    with pytest.raises(ValueError, match="outside"):
        locator.validate_source(revision, body=body, page_count=0)
    with pytest.raises(ValueError, match="body digest"):
        locator.validate_source(revision, body=b"changed source bytes", page_count=1)


def test_build_native_pdf_records_bind_verified_bytes_to_stable_identity():
    body = b"%PDF-1.7\n"
    request = NativePdfSourceAdmissionV1.model_validate({
        "space_id": "space:pdf",
        "admission_id": "admission:pdf",
        "created_at": datetime.now(UTC),
        "content_sha256": sha256(body).hexdigest(),
        "source_classification": "test:pdf",
        "authority": "primary",
        "visibility": {"kind": "public"},
    })

    artifact, revision = build_native_pdf_source_records(request, body)
    assert artifact.current_revision_id == revision.source_revision_id
    assert artifact.source_artifact_id == revision.source_artifact_id
    assert revision.content_sha256 == request.content_sha256
    assert build_native_pdf_source_records(request, body) == (artifact, revision)

    with pytest.raises(ValueError, match="PDF header"):
        build_native_pdf_source_records(request, b"not a PDF")
    with pytest.raises(ValueError, match="digest"):
        build_native_pdf_source_records(request, b"%PDF-1.4\n")


def test_open_pdf_region_requires_visibility_and_exact_bytes(region):
    from dungeonmind.application.vnext.native_pdf_access import (
        bind_native_pdf_evidence,
        open_native_pdf_region,
    )

    body = b"%PDF-1.7\n"
    request = NativePdfSourceAdmissionV1.model_validate({
        "space_id": "space:pdf",
        "admission_id": "admission:pdf",
        "created_at": datetime.now(UTC),
        "content_sha256": sha256(body).hexdigest(),
        "source_classification": "test:pdf",
        "authority": "primary",
        "visibility": {"kind": "labels_any", "labels": ["test:private"]},
    })
    artifact, revision = build_native_pdf_source_records(request, body)
    locator = NativePdfRegionV1.model_validate(region | {
        "source_revision_id": revision.source_revision_id,
        "content_sha256": revision.content_sha256,
    })

    def load(space_id, revision_id):
        if (space_id, revision_id) == (request.space_id, revision.source_revision_id):
            return artifact, revision, 1, body
        return None

    assert open_native_pdf_region(
        locator, authorized_space_id=request.space_id, audience=frozenset(),
        declared_labels=frozenset({"test:private"}), load=load,
    ) is None
    assert open_native_pdf_region(
        locator, authorized_space_id="space:other", audience=frozenset({"test:private"}),
        declared_labels=frozenset({"test:private"}), load=load,
    ) is None
    assert open_native_pdf_region(
        locator, authorized_space_id=request.space_id, audience=frozenset({"test:private"}),
        declared_labels=frozenset({"test:private"}), load=load,
    ) == body

    evidence = bind_native_pdf_evidence(
        locator, authorized_space_id=request.space_id, audience=frozenset({"test:private"}),
        declared_labels=frozenset({"test:private"}), load=load,
    )
    assert evidence is not None and evidence.source_locator is not None
    assert evidence.source_artifact_id == artifact.source_artifact_id
    assert evidence.source_revision_id == revision.source_revision_id
    assert NativePdfRegionV1.model_validate_json(evidence.source_locator) == locator
    assert bind_native_pdf_evidence(
        locator, authorized_space_id=request.space_id, audience=frozenset(),
        declared_labels=frozenset({"test:private"}), load=load,
    ) is None


def test_register_pdf_evidence_preserves_graph_and_replays_exact_parent(region):
    from dungeonmind.application.vnext.errors import KnowledgeStaleParentRevisionError
    from dungeonmind.application.vnext.native_pdf_access import register_native_pdf_evidence
    from dungeonmind.infrastructure.memory.vnext_knowledge import InMemoryKnowledgeRevisionRepository
    from tests.unit.test_vnext_cas_publication import genesis_command

    repository = InMemoryKnowledgeRevisionRepository()
    parent = repository.publish_revision(genesis_command())
    body = b"%PDF-1.7\n"
    created_at = datetime.now(UTC)
    request = NativePdfSourceAdmissionV1.model_validate({
        "space_id": parent.revision.space_id,
        "admission_id": "admission:pdf",
        "created_at": created_at,
        "content_sha256": sha256(body).hexdigest(),
        "source_classification": "test:pdf",
        "authority": "primary",
        "visibility": {"kind": "public"},
    })
    artifact, revision = build_native_pdf_source_records(request, body)
    locator = NativePdfRegionV1.model_validate(region | {
        "source_revision_id": revision.source_revision_id,
        "content_sha256": revision.content_sha256,
    })

    def load(space_id, revision_id):
        if (space_id, revision_id) == (request.space_id, revision.source_revision_id):
            return artifact, revision, 1, body
        return None

    def register(publication_id):
        return register_native_pdf_evidence(
            locator, authorized_space_id=request.space_id, audience=frozenset(),
            declared_labels=frozenset(), load=load, repository=repository,
            expected_parent_revision_id=parent.revision.revision_id,
            publication_id=publication_id, created_at=created_at,
        )

    registered = register("register:region")
    assert registered is not None
    evidence, receipt = registered
    child = repository.get_revision(request.space_id, receipt.published_revision_id)
    assert child is not None
    assert child.graph_payload == parent.graph_payload | {
        "evidence": [*parent.graph_payload["evidence"], evidence.model_dump(mode="json")],
    }
    assert register("register:region") == registered
    with pytest.raises(KnowledgeStaleParentRevisionError):
        register("register:stale")
