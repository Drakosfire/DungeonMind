from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import timedelta

import pytest
from pydantic import ValidationError

from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
    NativeTextSourceAdmissionIntegrityError,
)
from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
from dungeonmind.application.vnext.native_source_access import (
    open_admitted_native_text,
    open_native_text_source_access_context,
)
from dungeonmind.application.vnext.native_source_admission import (
    publish_native_text_source_evidence,
)
from dungeonmind.application.vnext.native_source_extension import (
    publish_native_source_evidence_extension,
)
from dungeonmind.contracts.vnext.common import LabelsAnyVisibility
from dungeonmind.contracts.vnext.native_source import (
    NativeSourceEvidenceExtensionV1,
    NativeTextEvidenceSpanRequestV1,
)
from dungeonmind.infrastructure.memory.vnext_sources import InMemoryNativeSourceEvidenceRepository
from tests.unit.test_vnext_native_source_admission import BODY, NOW, _domain, _profile, _request


def setup_source(repo, *, private=False):
    domain = _domain(visibility_labels=["role:gm"] if private else None)
    profile = _profile()
    genesis = initialize_empty_knowledge_space(
        repository=repo,
        space_id="space:extension",
        initialization_id="init:extension",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    req = _request(
        space_id="space:extension",
        parent_revision_id=genesis.published_revision_id,
        visibility=LabelsAnyVisibility(kind="labels_any", labels=["role:gm"]) if private else None,
    )
    req.spans = [
        NativeTextEvidenceSpanRequestV1(
            client_ref="first",
            evidence_role="support",
            start_byte=0,
            end_byte=1,
            expected_slice_sha256=hashlib.sha256(BODY.encode()[:1]).hexdigest(),
        )
    ]
    root = publish_native_text_source_evidence(
        repository=repo, request=req, domain_contract=domain, semantic_profile=profile
    )
    return domain, profile, req, root


def extension(repo, root, *, operation="extension:one", start=2, end=8):
    return NativeSourceEvidenceExtensionV1(
        space_id=root.space_id,
        extension_id=operation,
        original_admission_id=root.admission_id,
        source_artifact_id=root.source_artifact_id,
        source_revision_id=root.source_revision_id,
        expected_body_sha256=hashlib.sha256(BODY.encode()).hexdigest(),
        expected_parent_revision_id=repo.get_head(root.space_id).head_revision_id,
        expected_source_authority_epoch=repo.open_native_source_view(root.space_id).epoch,
        created_at=NOW + timedelta(minutes=2),
        spans=[
            NativeTextEvidenceSpanRequestV1(
                client_ref="new",
                evidence_role="support",
                start_byte=start,
                end_byte=end,
                expected_slice_sha256=hashlib.sha256(BODY.encode()[start:end]).hexdigest(),
            )
        ],
    )


def publish(repo, domain, profile, request, *, audience=()):
    return publish_native_source_evidence_extension(
        repository=repo,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
        audience_labels=audience,
    )


def access(repo, domain, root, evidence, *, revision=None, audience=()):
    context = open_native_text_source_access_context(
        repository=repo,
        space_id=root.space_id,
        revision_id=revision or repo.get_head(root.space_id).head_revision_id,
        domain_contract=domain,
        audience_labels=audience,
    )
    return open_admitted_native_text(context, evidence)


def seed_semantic_content(repo, root):
    from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand

    parent = repo.get_revision(root.space_id, root.published_revision_id)
    payload = deepcopy(parent.graph_payload)
    payload["entities"] = [{"schema_version": "dm_entity_v1", "entity_id": "entity:preserved"}]
    payload["assertions"] = [
        {
            "schema_version": "dm_assertion_v1",
            "assertion_id": "assertion:preserved",
            "subject_entity_id": "entity:preserved",
            "predicate": "test:name",
            "value": {"kind": "literal", "value": "Retained name"},
            "metadata": {
                "scope": [],
                "visibility": {"kind": "public"},
                "epistemic_basis": "asserted",
                "claim_mode": "test:source",
                "standing": "established",
                "evidence_ref_ids": [root.bindings[0].evidence_ref_id],
                "temporal_scope": {"kind": "unknown"},
                "domain_metadata": [],
            },
        }
    ]
    payload["aliases"] = [
        {
            "schema_version": "dm_identity_alias_v1",
            "alias_id": "alias:preserved",
            "entity_id": "entity:preserved",
            "alias_text": "Retained alias",
            "evidence_ref_ids": [root.bindings[0].evidence_ref_id],
            "standing": "established",
        }
    ]
    command = PublishKnowledgeRevisionCommand(
        space_id=root.space_id,
        parent_revision_id=root.published_revision_id,
        expected_parent_revision_id=root.published_revision_id,
        operation_ids=["op:semantic-fixture"],
        graph_schema=parent.revision.graph_schema,
        graph_payload=payload,
        domain_contract_ref=parent.revision.domain_contract_ref,
        semantic_profile_ref=parent.revision.semantic_profile_ref,
        migration_origin_ref=parent.revision.migration_origin_ref,
        created_at=NOW + timedelta(seconds=90),
    )
    return repo.publish_revision(command)


def exercise_success(repo):
    domain, profile, original, root = setup_source(repo)
    semantic_parent = seed_semantic_content(repo, root)
    old_view = repo.open_native_source_view(root.space_id)
    old_revision = repo.get_revision(root.space_id, root.published_revision_id)
    req = extension(repo, root)
    receipt = publish(repo, domain, profile, req)
    ev = receipt.bindings[0].evidence_ref_id
    result = access(repo, domain, root, ev)
    assert result.status == "available" and result.body_text == BODY
    assert (result.span_start_byte, result.span_end_byte) == (2, 8)
    assert (receipt.source_artifact_id, receipt.source_revision_id, receipt.origin) == (
        root.source_artifact_id,
        root.source_revision_id,
        root.origin,
    )
    assert repo.get_native_source_admission_receipt(root.space_id, root.admission_id) == root
    assert repo.get_revision(root.space_id, root.published_revision_id) == old_revision
    child = repo.get_revision(root.space_id, receipt.publication_receipt.published_revision_id)
    for k in ["entities", "assertions", "aliases"]:
        assert child.graph_payload[k] == semantic_parent.graph_payload[k]
        assert child.graph_payload[k]
    assert (
        access(repo, domain, root, root.bindings[0].evidence_ref_id).body_text == original.body_text
    )
    assert (
        access(repo, domain, root, ev, revision=root.published_revision_id).status == "unavailable"
    )
    assert (
        old_view.get_native_text_source(
            source_artifact_id=root.source_artifact_id,
            source_revision_id=root.source_revision_id,
            span_id=receipt.proofs[0].span_id,
        )
        is None
    )
    middle_view = repo.open_native_source_view(root.space_id)
    second = publish(
        repo, domain, profile, extension(repo, root, operation="extension:two", start=3, end=9)
    )
    assert (
        middle_view.get_native_text_source(
            source_artifact_id=root.source_artifact_id,
            source_revision_id=root.source_revision_id,
            span_id=receipt.proofs[0].span_id,
        )
        is not None
    )
    assert (
        middle_view.get_native_text_source(
            source_artifact_id=root.source_artifact_id,
            source_revision_id=root.source_revision_id,
            span_id=second.proofs[0].span_id,
        )
        is None
    )
    head = repo.get_head(root.space_id)
    assert publish(repo, domain, profile, req) == receipt
    assert repo.get_head(root.space_id) == head
    assert access(repo, domain, root, second.bindings[0].evidence_ref_id).status == "available"
    return domain, profile, root, req, receipt


def test_memory_success_replay_overlap_and_prior_readers():
    repo = InMemoryNativeSourceEvidenceRepository()
    original = deepcopy(repo._native_records)
    exercise_success(repo)
    assert (
        original == {}
    )  # Genesis starts empty; source body remains in the single original record.
    assert len(repo._native_records) == 1 and len(repo._native_receipts) == 1


@pytest.mark.parametrize(
    "change",
    ["body", "source", "root", "slice", "epoch", "parent", "space", "metadata", "utf8", "bounds"],
)
def test_memory_invalid_inputs_do_not_publish(change):
    exercise_refusal(InMemoryNativeSourceEvidenceRepository(), change)


def exercise_refusal(repo, change):
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)
    if change == "body":
        req.expected_body_sha256 = "0" * 64
    elif change == "source":
        req.source_revision_id = "wrong"
    elif change == "root":
        req.original_admission_id = "wrong"
    elif change == "slice":
        req.spans[0].expected_slice_sha256 = "0" * 64
    elif change == "epoch":
        req.expected_source_authority_epoch += 1
    elif change == "parent":
        req.expected_parent_revision_id = "wrong"
    elif change == "space":
        req.space_id = "another-world"
    elif change == "metadata":
        from dungeonmind.contracts.vnext.common import DomainMetadataEntry

        req.spans[0].domain_metadata = [
            DomainMetadataEntry(schema_term="unknown:schema", payload={})
        ]
    elif change == "utf8":
        req.spans[0].start_byte = 13
        req.spans[0].end_byte = 14
    elif change == "bounds":
        req.spans[0].end_byte = 999
    before = repo.get_head(root.space_id)
    epoch = repo.open_native_source_view(root.space_id).epoch
    with pytest.raises(
        (NativeTextSourceAdmissionIntegrityError, KnowledgeStaleParentRevisionError)
    ):
        publish(repo, domain, profile, req)
    assert repo.get_head(root.space_id) == before
    assert repo.open_native_source_view(root.space_id).epoch == epoch
    assert repo.get_native_source_evidence_extension_receipt(req.space_id, req.extension_id) is None


def exercise_duplicates(repo):
    domain, profile, _, root = setup_source(repo)
    for start, end in [(0, 1), (2, 8)]:
        req = extension(repo, root, start=start, end=end)
        if start == 2:
            publish(repo, domain, profile, req)
            req = extension(repo, root, operation="extension:duplicate", start=start, end=end)
        before = repo.get_head(root.space_id)
        with pytest.raises(NativeTextSourceAdmissionIntegrityError) as caught:
            publish(repo, domain, profile, req)
        assert caught.value.reason == "extension_interval_already_registered"
        assert repo.get_head(root.space_id) == before
    req = extension(repo, root, operation="extension:within", start=4, end=9)
    req.spans.append(
        req.spans[0].model_copy(update={"client_ref": "another", "evidence_role": "context"})
    )
    with pytest.raises(ValidationError, match="duplicate source interval"):
        publish(repo, domain, profile, req)


def test_memory_duplicate_intervals():
    exercise_duplicates(InMemoryNativeSourceEvidenceRepository())


def exercise_access_and_conflict(repo):
    domain, profile, _, root = setup_source(repo, private=True)
    req = extension(repo, root)
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish(repo, domain, profile, req)
    receipt = publish(repo, domain, profile, req, audience=["role:gm"])
    before = repo.get_head(root.space_id)
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish(
            repo, domain, profile, req
        )  # Exact replay cannot recover private material without current access.
    assert publish(repo, domain, profile, req, audience=["role:gm"]) == receipt
    changed = req.model_copy(deep=True)
    changed.spans[0].client_ref = "different"
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        publish(repo, domain, profile, changed, audience=["role:gm"])
    forged = extension(repo, root, operation="extension:forged", start=3, end=9)
    forged.original_admission_id = receipt.extension_id
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish(repo, domain, profile, forged, audience=["role:gm"])
    assert repo.get_head(root.space_id) == before


def test_memory_access_conflict_and_forged_extension_root():
    exercise_access_and_conflict(InMemoryNativeSourceEvidenceRepository())


@pytest.mark.parametrize(
    "hook",
    [
        "_after_revision_insert",
        "_after_native_publication_receipt_insert",
        "_after_native_source_insert",
        "_after_native_receipt_insert",
    ],
)
def test_memory_rollback_at_every_stage(hook):
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)
    before = deepcopy(
        (
            repo._revisions,
            repo._heads,
            repo._events,
            repo._receipts,
            repo._native_epoch,
            repo._native_records,
            repo._native_receipts,
        )
    )

    def fail():
        raise RuntimeError("injected failure")

    setattr(repo, hook, fail)
    with pytest.raises(RuntimeError, match="injected"):
        publish(repo, domain, profile, req)
    assert (
        repo._revisions,
        repo._heads,
        repo._events,
        repo._receipts,
        repo._native_epoch,
        repo._native_records,
        repo._native_receipts,
    ) == before
    assert repo._extension_receipts == {} and repo._extension_by_span == {}


def test_memory_lost_acknowledgement_reconciles_once():
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)

    def fail():
        raise RuntimeError("lost acknowledgement")

    repo._after_publication_commit = fail
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        publish(repo, domain, profile, req)
    head = repo.get_head(root.space_id)
    receipt = publish(repo, domain, profile, req)
    assert receipt == repo.get_native_source_evidence_extension_receipt(
        root.space_id, req.extension_id
    )
    assert repo.get_head(root.space_id) == head and len(repo._extension_receipts) == 1


def test_repository_revalidates_constructed_duplicate_request():
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)
    req.spans.append(req.spans[0].model_copy(update={"client_ref": "second"}))
    before = repo.get_head(root.space_id)
    with pytest.raises(ValidationError):
        repo.publish_native_source_evidence_extension(
            request=req, domain_contract=domain, semantic_profile=profile, audience_labels=()
        )
    assert repo.get_head(root.space_id) == before and not repo._extension_receipts


def test_memory_tampered_companion_is_not_replayed_or_opened():
    from dungeonmind.domain.errors import PersistenceIntegrityError

    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    req = extension(repo, root)
    receipt = publish(repo, domain, profile, req)
    repo._extension_receipts[(root.space_id, req.extension_id)][0].origin = None
    repo._extension_receipts[(root.space_id, req.extension_id)][0].original_admission_id = "forged"
    with pytest.raises(PersistenceIntegrityError):
        publish(repo, domain, profile, req)
    with pytest.raises(PersistenceIntegrityError):
        access(repo, domain, root, receipt.bindings[0].evidence_ref_id)


def contract_bundle():
    from dungeonmind.contracts.vnext.native_source import NativeSourceEvidenceExtensionReceiptV1
    from dungeonmind.domain.canonical import canonical_sha256

    models = (NativeSourceEvidenceExtensionV1, NativeSourceEvidenceExtensionReceiptV1)
    bundle = {
        "schema": "dm_native_source_evidence_extension_contract_v1",
        "contracts": [
            {
                "name": m.__name__,
                "schema": m.model_json_schema(by_alias=True, ref_template="#/$defs/{model}"),
            }
            for m in models
        ],
    }
    bundle["aggregate_sha256"] = canonical_sha256(bundle)
    return bundle


def test_extension_contract_artifact_is_reproducible():
    import json
    from pathlib import Path

    path = (
        Path(__file__).parents[2]
        / "Docs/Contracts/vnext/dm_native_source_evidence_extension_v1.json"
    )
    assert path.read_text() == json.dumps(contract_bundle(), sort_keys=True, indent=2) + "\n"
