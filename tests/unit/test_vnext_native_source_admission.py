from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from dungeonmind.application.vnext.authority import revision_from_command
from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgeStaleParentRevisionError,
    NativeTextSourceAccessIntegrityError,
    NativeTextSourceAdmissionIntegrityError,
)
from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
from dungeonmind.application.vnext.native_source_access import (
    open_admitted_native_text,
    open_native_text_source_access_context,
)
from dungeonmind.application.vnext.native_source_admission import (
    _build_command,
    build_native_source_write_parts,
    native_source_command_sha256,
    publish_native_text_source_evidence,
)
from dungeonmind.contracts.vnext.common import LabelsAnyVisibility, PublicVisibility
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
)
from dungeonmind.contracts.vnext.native_source import (
    NativeSourceAdmissionReceiptV1,
    NativeTextEvidenceSpanRequestV1,
    NativeTextSourceAccessV1,
    NativeTextSourceAdmissionV1,
    NativeUtf8SpanProofV1,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.infrastructure.memory.vnext_sources import (
    InMemoryNativeSourceEvidenceRepository,
)

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
BODY = "A quiet map — with exact bytes.\n"
CONTRACT_PATH = (
    Path(__file__).parents[2]
    / "Docs"
    / "Contracts"
    / "vnext"
    / "dm_native_source_admission_v1.json"
)


def _domain(*, visibility_labels: list[str] | None = None) -> DomainContractDescriptor:
    return DomainContractDescriptor(
        domain_id="test.native-source",
        domain_revision="1",
        visibility_labels=visibility_labels or [],
        source_annotation_schemas=[],
        admission_policy_id="test.native-source.allow",
    )


def _profile() -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="test.native-source.profile",
        profile_revision="1",
        term_namespaces=["test"],
    )


def _request(
    *,
    space_id: str = "space:native-source",
    admission_id: str = "admit:map-1",
    parent_revision_id: str,
    body: str = BODY,
    visibility: PublicVisibility | LabelsAnyVisibility | None = None,
) -> NativeTextSourceAdmissionV1:
    encoded = body.encode("utf-8")
    return NativeTextSourceAdmissionV1(
        space_id=space_id,
        admission_id=admission_id,
        expected_parent_revision_id=parent_revision_id,
        created_at=NOW + timedelta(minutes=1),
        body_text=body,
        expected_body_sha256=hashlib.sha256(encoded).hexdigest(),
        source_classification="test:authored_text",
        authority="primary",
        visibility=visibility or PublicVisibility(kind="public"),
        spans=[
            NativeTextEvidenceSpanRequestV1(
                client_ref="opening",
                evidence_role="support",
                start_byte=0,
                end_byte=len(encoded),
                expected_slice_sha256=hashlib.sha256(encoded).hexdigest(),
            )
        ],
    )


def _initialized():
    repository = InMemoryNativeSourceEvidenceRepository()
    domain = _domain()
    profile = _profile()
    genesis = initialize_empty_knowledge_space(
        repository=repository,
        space_id="space:native-source",
        initialization_id="init:native-source",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    return repository, domain, profile, genesis


def test_public_admission_commits_exact_body_span_and_child_evidence():
    repository, domain, profile, genesis = _initialized()
    request = _request(parent_revision_id=genesis.published_revision_id)

    receipt = publish_native_text_source_evidence(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )

    assert repository.get_head(request.space_id).head_revision_id == receipt.published_revision_id
    child = repository.get_revision(request.space_id, receipt.published_revision_id)
    assert child is not None
    assert child.graph_payload["entities"] == []
    assert child.graph_payload["assertions"] == []
    assert child.graph_payload["aliases"] == []
    assert len(child.graph_payload["evidence"]) == 1
    evidence_id = receipt.bindings[0].evidence_ref_id
    evidence = next(
        item for item in child.graph_payload["evidence"] if item["evidence_ref_id"] == evidence_id
    )

    context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
    )
    access = open_admitted_native_text(context, evidence_id)
    assert access.status == "available"
    assert access.body_text == BODY
    assert access.body_sha256 == request.expected_body_sha256
    assert access.span_start_byte == 0
    assert access.span_end_byte == len(BODY.encode("utf-8"))
    assert evidence["source_artifact_id"] == receipt.source_artifact_id


def test_old_epoch_view_cannot_observe_later_admission():
    repository, domain, profile, genesis = _initialized()
    old_view = repository.open_native_source_view("space:native-source")
    request = _request(parent_revision_id=genesis.published_revision_id)
    receipt = publish_native_text_source_evidence(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )

    assert (
        old_view.get_native_text_source(
            source_artifact_id=receipt.source_artifact_id,
            source_revision_id=receipt.source_revision_id,
            span_id=receipt.bindings[0].span_id,
        )
        is None
    )
    new_view = repository.open_native_source_view("space:native-source")
    assert new_view.epoch == receipt.source_authority_epoch
    assert (
        new_view.get_native_text_source(
            source_artifact_id=receipt.source_artifact_id,
            source_revision_id=receipt.source_revision_id,
            span_id=receipt.bindings[0].span_id,
        )
        is not None
    )


def test_private_preview_is_non_disclosing_without_exact_audience():
    private_label = "test:private"
    domain = _domain(visibility_labels=[private_label])
    profile = _profile()
    repository = InMemoryNativeSourceEvidenceRepository()
    genesis = initialize_empty_knowledge_space(
        repository=repository,
        space_id="space:native-source",
        initialization_id="init:native-source",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    request = _request(
        parent_revision_id=genesis.published_revision_id,
        visibility=LabelsAnyVisibility(kind="labels_any", labels=[private_label]),
    )
    receipt = publish_native_text_source_evidence(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )
    evidence_id = receipt.bindings[0].evidence_ref_id
    hidden_context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
    )
    hidden = open_admitted_native_text(hidden_context, evidence_id)
    assert hidden.status == "unavailable"
    assert hidden.body_text is None
    assert hidden.source_artifact_id is None
    visible_context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
        audience_labels=[private_label],
    )
    visible = open_admitted_native_text(visible_context, evidence_id)
    assert visible.status == "available"
    assert visible.body_text == BODY
    foreign = open_admitted_native_text(visible_context, "foreign-evidence")
    assert foreign == hidden


@pytest.mark.parametrize("failpoint", ["revision", "publication_receipt", "source", "receipt"])
def test_atomic_failure_rolls_back_child_receipts_events_and_epoch(failpoint: str):
    def fail() -> None:
        raise RuntimeError("injected failure")

    repository = InMemoryNativeSourceEvidenceRepository(
        after_native_source_insert=fail if failpoint == "source" else None,
        after_native_receipt_insert=fail if failpoint == "receipt" else None,
    )
    domain, profile = _domain(), _profile()
    genesis = initialize_empty_knowledge_space(
        repository=repository,
        space_id="space:native-source",
        initialization_id="init:native-source",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    repository._after_revision_insert = fail if failpoint == "revision" else None
    repository._after_native_publication_receipt_insert = (
        fail if failpoint == "publication_receipt" else None
    )
    before_events = repository.head_events("space:native-source")
    request = _request(parent_revision_id=genesis.published_revision_id)
    parent = repository.get_revision("space:native-source", genesis.published_revision_id)
    assert parent is not None
    parts = build_native_source_write_parts(request=request)
    command = _build_command(
        request=request,
        parent=parent,
        parts=parts,
        domain_contract=domain,
        semantic_profile=profile,
    )
    command_sha = native_source_command_sha256(
        request=request,
        command=command,
        domain_contract=domain,
        semantic_profile=profile,
    )

    with pytest.raises(RuntimeError):
        repository.publish_native_text_source_evidence(
            request=request,
            command=command,
            command_sha256=command_sha,
            domain_contract=domain,
            semantic_profile=profile,
            source_artifact=parts.artifact,
            source_revision=parts.revision,
            body_bytes=parts.body_bytes,
            span_proofs=parts.span_proofs,
        )

    assert (
        repository.get_head("space:native-source").head_revision_id == genesis.published_revision_id
    )
    assert repository.head_events("space:native-source") == before_events
    assert (
        repository.get_native_source_admission_receipt("space:native-source", request.admission_id)
        is None
    )
    assert repository.open_native_source_view("space:native-source").epoch == 0
    assert (
        repository.get_revision("space:native-source", revision_from_command(command).revision_id)
        is None
    )


def test_exact_replay_returns_original_receipt_and_changed_body_conflicts():
    repository, domain, profile, genesis = _initialized()
    request = _request(parent_revision_id=genesis.published_revision_id)
    first = publish_native_text_source_evidence(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )
    assert (
        publish_native_text_source_evidence(
            repository=repository,
            request=request,
            domain_contract=domain,
            semantic_profile=profile,
        )
        == first
    )
    changed = _request(
        parent_revision_id=genesis.published_revision_id,
        body="A changed body.\n",
    )
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        publish_native_text_source_evidence(
            repository=repository,
            request=changed,
            domain_contract=domain,
            semantic_profile=profile,
        )


def test_concurrent_same_admission_is_one_exact_replay():
    repository, domain, profile, genesis = _initialized()
    request = _request(parent_revision_id=genesis.published_revision_id)

    def publish():
        return publish_native_text_source_evidence(
            repository=repository,
            request=request,
            domain_contract=domain,
            semantic_profile=profile,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = tuple(pool.map(lambda _: publish(), range(2)))
    assert first == second
    assert len(repository.head_events(request.space_id)) == 2
    assert repository.open_native_source_view(request.space_id).epoch == 1


def test_concurrent_distinct_admissions_from_same_parent_have_one_winner():
    repository, domain, profile, genesis = _initialized()
    requests = (
        _request(admission_id="admit:first", parent_revision_id=genesis.published_revision_id),
        _request(admission_id="admit:second", parent_revision_id=genesis.published_revision_id),
    )

    def publish(request):
        try:
            return publish_native_text_source_evidence(
                repository=repository,
                request=request,
                domain_contract=domain,
                semantic_profile=profile,
            )
        except KnowledgeStaleParentRevisionError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(publish, requests))
    assert sum(not isinstance(item, KnowledgeStaleParentRevisionError) for item in outcomes) == 1
    assert sum(isinstance(item, KnowledgeStaleParentRevisionError) for item in outcomes) == 1
    assert len(repository.head_events("space:native-source")) == 2
    assert repository.open_native_source_view("space:native-source").epoch == 1


def test_corrupt_native_body_fails_closed_without_returning_bytes():
    repository, domain, profile, genesis = _initialized()
    request = _request(parent_revision_id=genesis.published_revision_id)
    receipt = publish_native_text_source_evidence(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )
    context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
    )
    key = (request.space_id, receipt.source_artifact_id)
    object.__setattr__(repository._native_records[key], "body", b"tampered bytes")
    with pytest.raises(NativeTextSourceAccessIntegrityError):
        open_admitted_native_text(context, receipt.bindings[0].evidence_ref_id)


def test_invalid_utf8_span_is_rejected_before_mutation():
    repository, domain, profile, genesis = _initialized()
    body = "évidence".encode()
    request = NativeTextSourceAdmissionV1(
        space_id="space:native-source",
        admission_id="admit:bad-span",
        expected_parent_revision_id=genesis.published_revision_id,
        created_at=NOW + timedelta(minutes=1),
        body_text=body.decode("utf-8"),
        expected_body_sha256=hashlib.sha256(body).hexdigest(),
        source_classification="test:authored_text",
        authority="primary",
        visibility=PublicVisibility(kind="public"),
        spans=[
            NativeTextEvidenceSpanRequestV1(
                client_ref="mid-codepoint",
                evidence_role="support",
                start_byte=1,
                end_byte=3,
                expected_slice_sha256=hashlib.sha256(body[1:3]).hexdigest(),
            )
        ],
    )
    before_events = repository.head_events("space:native-source")
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish_native_text_source_evidence(
            repository=repository,
            request=request,
            domain_contract=domain,
            semantic_profile=profile,
        )
    assert (
        repository.get_head("space:native-source").head_revision_id == genesis.published_revision_id
    )
    assert repository.head_events("space:native-source") == before_events
    assert repository.open_native_source_view("space:native-source").epoch == 0


def test_additive_native_source_contract_artifact_is_reproducible():
    models = (
        NativeTextSourceAdmissionV1,
        NativeUtf8SpanProofV1,
        NativeSourceAdmissionReceiptV1,
        NativeTextSourceAccessV1,
    )
    bundle = {
        "schema": "dm_native_source_admission_contract_v1",
        "contracts": [
            {
                "name": model.__name__,
                "schema": model.model_json_schema(
                    by_alias=True,
                    ref_template="#/$defs/{model}",
                ),
            }
            for model in models
        ],
    }
    bundle["aggregate_sha256"] = canonical_sha256(bundle)
    expected = json.dumps(bundle, sort_keys=True, indent=2) + "\n"
    assert CONTRACT_PATH.read_text(encoding="utf-8") == expected
