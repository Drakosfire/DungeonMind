"""Owning memory proofs for one-source atomic facts/aliases."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import pytest
from pydantic import ValidationError

from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgeStaleParentRevisionError,
    NativeTextSourceAdmissionIntegrityError,
    ProspectivePublicationIntegrityError,
)
from dungeonmind.application.vnext.native_source_publication import (
    preview_native_source_publication_evidence,
    publish_governed_native_source_publication,
    recover_governed_native_source_publication,
)
from dungeonmind.contracts.vnext.native_source_publication import (
    GovernedNativeSourcePublicationReceiptV1,
    GovernedNativeSourcePublicationV1,
    NativeSourcePublicationBasisV1,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory.vnext_sources import InMemoryNativeSourceEvidenceRepository
from tests.unit.test_vnext_native_source_evidence_extension import access, extension, setup_source
from tests.unit.test_vnext_native_source_evidence_extension import publish as publish_extension


def support_ref(receipt, proof, kind):
    return dict(
        evidence_ref_id=proof.evidence_ref_id,
        span_id=proof.span_id,
        proof=proof.model_dump(mode="json"),
        introducing_kind=kind,
        introducing_operation_id=receipt.admission_id
        if kind == "admission"
        else receipt.extension_id
        if kind == "extension"
        else receipt.publication_id,
        introducing_receipt_sha256=canonical_sha256(receipt.model_dump(mode="json")),
        proof_authority_epoch=receipt.source_authority_epoch_after
        if kind == "publication"
        else receipt.source_authority_epoch,
    )


def request_for(
    repo, domain, profile, root, *, mode="new_intervals", operation="composed:one", support=None
):
    ext = extension(repo, root, operation=operation)
    data = {
        k: v
        for k, v in ext.model_dump(mode="json").items()
        if k not in ("schema_version", "extension_id", "spans")
    }
    data["expected_body_sha256"] = repo.get_native_source_publication_source(
        root.space_id, root.admission_id
    )[0].content_sha256
    if mode == "new_intervals":
        evidence = {"mode": mode, "spans": [s.model_dump(mode="json") for s in ext.spans]}
    else:
        if support is None:
            proof = (
                repo.open_native_source_view(root.space_id)
                .get_native_text_source(
                    source_artifact_id=root.source_artifact_id,
                    source_revision_id=root.source_revision_id,
                    span_id=root.bindings[0].span_id,
                )
                .span_proof
            )
            support = [support_ref(root, proof, "admission")]
        evidence = {"mode": mode, "support": support}
    basis = NativeSourcePublicationBasisV1(publication_id=operation, evidence=evidence, **data)
    selected = preview_native_source_publication_evidence(
        repository=repo, request=basis, domain_contract=domain, semantic_profile=profile
    )
    metadata = dict(
        scope=[],
        visibility={"kind": "public"},
        epistemic_basis="asserted",
        claim_mode="test:source",
        standing="established",
        evidence_ref_ids=[selected[0].evidence_ref_id],
        temporal_scope={"kind": "unknown"},
        domain_metadata=[],
    )
    return GovernedNativeSourcePublicationV1.model_validate(
        {
            **basis.model_dump(mode="json"),
            "schema_version": "dm_governed_native_source_publication_v1",
            "contribution": dict(
                contribution_id="contribution:composed",
                space_id=root.space_id,
                producer="test:author",
                produced_at=ext.created_at,
                status="finalized",
                items=[
                    dict(kind="create_entity", item_id="entity", client_op_id="new-entity"),
                    dict(
                        kind="create_assertion",
                        item_id="name",
                        client_op_id="new-name",
                        subject={"kind": "result_of", "client_op_id": "new-entity"},
                        predicate="test:name",
                        value={"kind": "literal", "value": "Exact 🐉 name"},
                        metadata=metadata,
                    ),
                ],
            ),
            "aliases": [
                dict(
                    item_id="alias",
                    alias_id="alias:" + operation,
                    entity={"kind": "result_of", "client_op_id": "new-entity"},
                    alias_text="Exact 🐉 name",
                    evidence_ref_ids=[selected[0].evidence_ref_id],
                    standing="established",
                )
            ],
            "dispositions": [
                dict(item_id=i, disposition="accepted") for i in ("entity", "name", "alias")
            ],
        }
    )


def publish(repo, domain, profile, request):
    return publish_governed_native_source_publication(
        repository=repo, request=request, domain_contract=domain, semantic_profile=profile
    )


def recover(repo, domain, profile, request):
    return recover_governed_native_source_publication(
        repository=repo, request=request, domain_contract=domain, semantic_profile=profile
    )


def snapshot(repo):
    names = (
        "_revisions",
        "_heads",
        "_events",
        "_receipts",
        "_native_epoch",
        "_native_withdrawals",
        "_native_receipts",
        "_native_records",
        "_by_revision",
        "_by_span",
        "_source_admission_by_span",
        "_global_identity_space",
        "_extension_receipts",
        "_extension_by_span",
        "_source_publication_receipts",
        "_source_publication_by_span",
    )
    return deepcopy({n: getattr(repo, n) for n in names})


def exercise_success(repo, mode):
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root, mode=mode)
    before_epoch = repo.open_native_source_view(root.space_id).epoch
    oldview = repo.open_native_source_view(root.space_id)
    before_events = len(repo.head_events(root.space_id))
    receipt = publish(repo, domain, profile, request)
    assert len(repo.head_events(root.space_id)) == before_events + 1
    assert receipt.source_authority_epoch_after == before_epoch + int(mode == "new_intervals")
    assert repo.open_native_source_view(root.space_id).epoch == receipt.source_authority_epoch_after
    assert [b.result_kind for b in receipt.result_bindings] == ["entity", "assertion"]
    stored = repo.get_revision(root.space_id, receipt.publication_receipt.published_revision_id)
    assert len(stored.graph_payload["entities"]) == 1
    assert stored.graph_payload["aliases"][0]["alias_text"] == "Exact 🐉 name"
    assert stored.graph_payload["assertions"][0]["value"]["value"] == "Exact 🐉 name"
    evidence = request.contribution.items[1].metadata.evidence_ref_ids[0]
    opened = access(repo, domain, root, evidence)
    assert opened.status == "available"
    if mode == "new_intervals":
        assert (
            oldview.get_native_text_source(
                source_artifact_id=root.source_artifact_id,
                source_revision_id=root.source_revision_id,
                span_id=receipt.proofs[0].span_id,
            )
            is None
        )
        import hashlib

        from tests.unit.test_vnext_native_source_admission import BODY

        proof = receipt.proofs[0]
        assert (opened.span_start_byte, opened.span_end_byte, opened.span_sha256) == (
            proof.start_byte,
            proof.end_byte,
            proof.slice_sha256,
        )
        assert opened.body_text == BODY
        assert (
            hashlib.sha256(
                opened.body_text.encode("utf8")[proof.start_byte : proof.end_byte]
            ).hexdigest()
            == proof.slice_sha256
        )
    assert publish(repo, domain, profile, request) == receipt
    assert recover(repo, domain, profile, request) == receipt
    return domain, profile, root, request, receipt


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_atomic_facts_aliases_and_epoch(mode):
    exercise_success(InMemoryNativeSourceEvidenceRepository(), mode)


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_metadata_recovery_after_withdrawal_without_mutable_opens(mode, monkeypatch):
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, root, request, receipt = exercise_success(repo, mode)
    repo.withdraw_native_source(
        space_id=root.space_id,
        source_artifact_id=root.source_artifact_id,
        source_revision_id=root.source_revision_id,
    )
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish(repo, domain, profile, request)
    before = snapshot(repo)

    def forbidden(*a, **k):
        raise AssertionError("mutable authority or write opened in recovery")

    monkeypatch.setattr(repo, "get_head", forbidden)
    monkeypatch.setattr(repo, "open_native_source_view", forbidden)
    monkeypatch.setattr(repo, "publish_governed_native_source_publication", forbidden)
    assert recover(repo, domain, profile, request) == receipt
    assert snapshot(repo) == before


@pytest.mark.parametrize(
    "hook",
    [
        "_after_revision_insert",
        "_after_native_publication_receipt_insert",
        "_after_native_source_insert",
        "_after_native_receipt_insert",
    ],
)
def test_memory_atomic_rollback(hook):
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root)
    before = snapshot(repo)
    fired = []

    def fail():
        fired.append(True)
        raise RuntimeError("injected mutation fault")

    setattr(repo, hook, fail)
    with pytest.raises(RuntimeError, match="injected"):
        publish(repo, domain, profile, request)
    assert fired
    assert snapshot(repo) == before


def test_changed_time_same_child_identity_conflicts():
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, request, _ = exercise_success(repo, "new_intervals")
    changed = request.model_copy(deep=True)
    changed.created_at += timedelta(seconds=1)
    before = snapshot(repo)
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        recover(repo, domain, profile, changed)
    assert snapshot(repo) == before


def test_foreign_or_unselected_fact_evidence_refused():
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root)
    request.contribution.items[1].metadata.evidence_ref_ids = [root.bindings[0].evidence_ref_id]
    before = snapshot(repo)
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish(repo, domain, profile, request)
    assert snapshot(repo) == before


def test_new_source_proofs_reused_without_reindexing():
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, root, _, receipt = exercise_success(repo, "new_intervals")
    request = request_for(
        repo,
        domain,
        profile,
        root,
        mode="existing_support",
        operation="composed:two",
        support=[support_ref(receipt, receipt.proofs[0], "publication")],
    )
    before = dict(repo._source_publication_by_span)
    receipt2 = publish(repo, domain, profile, request)
    assert not receipt2.proofs and repo._source_publication_by_span == before
    assert receipt2.source_authority_epoch_after == receipt.source_authority_epoch_after


def test_old_extension_after_new_publication_rejects_registered_interval():
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, root, _, _ = exercise_success(repo, "new_intervals")
    ext = extension(repo, root, operation="old:extension")
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        publish_extension(repo, domain, profile, ext)


def contract_bundle():
    models = (
        NativeSourcePublicationBasisV1,
        GovernedNativeSourcePublicationV1,
        GovernedNativeSourcePublicationReceiptV1,
    )
    payload = {
        "schema": "dm_governed_native_source_publication_contract_v1",
        "contracts": [
            {
                "name": m.__name__,
                "schema": m.model_json_schema(by_alias=True, ref_template="#/$defs/{model}"),
            }
            for m in models
        ],
    }
    return {**payload, "aggregate_sha256": canonical_sha256(payload)}


def advance_head(repo, request, receipt):
    from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand

    stored = repo.get_revision(request.space_id, receipt.publication_receipt.published_revision_id)
    return repo.publish_revision(
        PublishKnowledgeRevisionCommand(
            space_id=request.space_id,
            parent_revision_id=stored.revision.revision_id,
            expected_parent_revision_id=stored.revision.revision_id,
            operation_ids=["descendant:real"],
            graph_schema=stored.revision.graph_schema,
            graph_payload=stored.graph_payload,
            domain_contract_ref=stored.revision.domain_contract_ref,
            semantic_profile_ref=stored.revision.semantic_profile_ref,
            migration_origin_ref=stored.revision.migration_origin_ref,
            created_at=request.created_at + timedelta(minutes=1),
        )
    )


def exercise_refusal(repo, change):
    domain, profile, _, root = setup_source(repo)
    mode = "existing_support" if change.startswith("support_") else "new_intervals"
    request = request_for(repo, domain, profile, root, mode=mode)
    if change == "body":
        request.expected_body_sha256 = "0" * 64
    elif change == "source":
        request.source_artifact_id = "source:foreign"
    elif change == "root":
        request.original_admission_id = "admission:missing"
    elif change == "epoch":
        request.expected_source_authority_epoch += 1
    elif change == "parent":
        request.expected_parent_revision_id = "rev:missing"
    elif change == "slice":
        request.evidence.spans[0].expected_slice_sha256 = "0" * 64
    elif change == "utf8":
        request.evidence.spans[0].end_byte = 13
    elif change == "bounds":
        request.evidence.spans[0].end_byte = 10000
    elif change == "context":
        request.evidence.spans[0].evidence_role = "context"
    elif change == "alias_target":
        request.aliases[0].entity.client_op_id = "unaccepted-entity"
    elif change == "fact_evidence":
        request.contribution.items[1].metadata.evidence_ref_ids = [root.bindings[0].evidence_ref_id]
    elif change == "alias_evidence":
        request.aliases[0].evidence_ref_ids = [root.bindings[0].evidence_ref_id]
    elif change == "support_hash":
        request.evidence.support[0].introducing_receipt_sha256 = "0" * 64
    elif change == "support_epoch":
        request.evidence.support[0].proof_authority_epoch += 1
    elif change == "support_origin":
        request.evidence.support[0].introducing_operation_id = "missing:origin"
    elif change == "support_proof":
        request.evidence.support[0].proof.slice_sha256 = "0" * 64
    elif change == "support_revision":
        request.evidence.support[0].proof.source_revision_id = "source-revision:foreign"
    else:
        raise AssertionError(change)
    before_head = repo.get_head(root.space_id)
    before_events = repo.head_events(root.space_id)
    before_epoch = repo.open_native_source_view(root.space_id).epoch
    with pytest.raises(
        (
            ValidationError,
            NativeTextSourceAdmissionIntegrityError,
            PersistenceIntegrityError,
            KnowledgeStaleParentRevisionError,
            ProspectivePublicationIntegrityError,
        )
    ):
        publish(repo, domain, profile, request)
    assert repo.get_head(root.space_id) == before_head
    assert repo.head_events(root.space_id) == before_events
    assert repo.open_native_source_view(root.space_id).epoch == before_epoch
    assert repo.get_publication_receipt(root.space_id, request.publication_id) is None
    assert repo.get_native_source_publication_receipt(root.space_id, request.publication_id) is None


REFUSALS = (
    "body",
    "source",
    "root",
    "epoch",
    "parent",
    "slice",
    "utf8",
    "bounds",
    "context",
    "alias_target",
    "fact_evidence",
    "alias_evidence",
    "support_hash",
    "support_epoch",
    "support_origin",
    "support_proof",
    "support_revision",
)


@pytest.mark.parametrize("change", REFUSALS)
def test_closed_refusals_zero_mutation(change):
    exercise_refusal(InMemoryNativeSourceEvidenceRepository(), change)


@pytest.mark.parametrize("change", ["missing", "duplicate", "unresolved", "rejected_target"])
def test_governance_and_rejected_target(change):
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root)
    if change == "missing":
        request.dispositions.pop()
    elif change == "duplicate":
        request.dispositions.append(request.dispositions[0])
    elif change == "unresolved":
        request.dispositions[0].disposition = "unresolved"
    else:
        request.dispositions[0].disposition = "rejected"
    before = snapshot(repo)
    with pytest.raises((ValidationError, ProspectivePublicationIntegrityError)):
        publish(repo, domain, profile, request)
    assert snapshot(repo) == before


@pytest.mark.parametrize("empty", [True, False])
def test_empty_or_rejected_aliases_and_full_rejected_intent(empty):
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root)
    if empty:
        request.aliases = []
        request.dispositions.pop()
    else:
        request.dispositions[-1].disposition = "rejected"
    receipt = publish(repo, domain, profile, request)
    assert (
        repo.get_revision(
            root.space_id, receipt.publication_receipt.published_revision_id
        ).graph_payload["aliases"]
        == []
    )
    if not empty:
        request.aliases[0].alias_text = "changed rejected intent"
        with pytest.raises(KnowledgePublicationIdempotencyConflictError):
            recover(repo, domain, profile, request)


def exercise_all_origin_lookups(repo):
    from dungeonmind.application.vnext import get_native_source_publication_support

    domain, profile, _, root = setup_source(repo)
    root_proof = (
        repo.open_native_source_view(root.space_id)
        .get_native_text_source(
            source_artifact_id=root.source_artifact_id,
            source_revision_id=root.source_revision_id,
            span_id=root.bindings[0].span_id,
        )
        .span_proof
    )
    ext = extension(repo, root, operation="old:extension", start=9, end=10)
    ext_receipt = publish_extension(repo, domain, profile, ext)
    request = request_for(repo, domain, profile, root)
    receipt = publish(repo, domain, profile, request)
    for kind, original, proof in (
        ("admission", root, root_proof),
        ("extension", ext_receipt, ext_receipt.proofs[0]),
        ("publication", receipt, receipt.proofs[0]),
    ):
        # Simulate host reloading only its known admitted source/span coordinates,
        # not caller memory of old publication receipts or private indexes.
        ref = get_native_source_publication_support(
            repository=repo,
            space_id=root.space_id,
            source_revision_id=root.source_revision_id,
            span_id=proof.span_id,
        )
        assert ref.model_dump(mode="json") == support_ref(original, proof, kind)
        req = request_for(
            repo,
            domain,
            profile,
            root,
            mode="existing_support",
            operation="reuse:" + kind,
            support=[ref.model_dump(mode="json")],
        )
        result = publish(repo, domain, profile, req)
        assert not result.proofs
        assert result.source_authority_epoch_before == result.source_authority_epoch_after
        assert recover(repo, domain, profile, req) == result
    assert (
        get_native_source_publication_support(
            repository=repo,
            space_id=root.space_id,
            source_revision_id=root.source_revision_id,
            span_id="missing:span",
        )
        is None
    )
    assert (
        get_native_source_publication_support(
            repository=repo,
            space_id="foreign:world",
            source_revision_id=root.source_revision_id,
            span_id=root_proof.span_id,
        )
        is None
    )


def test_public_ref_lookup_all_origins_no_remembered_receipts():
    exercise_all_origin_lookups(InMemoryNativeSourceEvidenceRepository())


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_recovery_after_actual_descendant_and_withdrawal(mode, monkeypatch):
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, root, request, receipt = exercise_success(repo, mode)
    advance_head(repo, request, receipt)
    repo.withdraw_native_source(
        space_id=root.space_id,
        source_artifact_id=root.source_artifact_id,
        source_revision_id=root.source_revision_id,
    )
    before = snapshot(repo)

    def forbidden(*a, **k):
        raise AssertionError("mutable open/write in recovery")

    for name in (
        "get_head",
        "open_native_source_view",
        "publish_governed_native_source_publication",
        "publish_revision",
        "publish_publication",
    ):
        monkeypatch.setattr(repo, name, forbidden)
    assert recover(repo, domain, profile, request) == receipt
    assert snapshot(repo) == before


@pytest.mark.parametrize(
    "damage",
    [
        "receipt_missing",
        "publication_missing",
        "root_missing",
        "parent_missing",
        "child_missing",
        "child_alias",
        "result",
        "proof",
        "receipt_fingerprint",
    ],
)
def test_immutable_corruption_never_falls_through_to_write(damage):
    from dataclasses import replace

    from dungeonmind.domain.canonical import canonical_json

    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, root, request, receipt = exercise_success(repo, "new_intervals")
    key = (root.space_id, request.publication_id)
    if damage == "receipt_missing":
        del repo._source_publication_receipts[key]
    elif damage == "publication_missing":
        del repo._receipts[key]
    elif damage == "root_missing":
        del repo._native_receipts[(root.space_id, root.admission_id)]
    elif damage == "parent_missing":
        del repo._revisions[(root.space_id, request.expected_parent_revision_id)]
    elif damage == "child_missing":
        del repo._revisions[(root.space_id, receipt.publication_receipt.published_revision_id)]
    elif damage == "child_alias":
        child_key = (root.space_id, receipt.publication_receipt.published_revision_id)
        stored = repo._revisions[child_key]
        payload = stored.graph_payload
        payload["aliases"][0]["alias_text"] = "tampered"
        repo._revisions[child_key] = replace(stored, _payload_json=canonical_json(payload))
    elif damage in ("result", "proof"):
        changed = receipt.model_copy(deep=True)
        if damage == "result":
            changed.result_bindings[0].durable_id = "ent:forged"
        else:
            changed.proofs[0].slice_sha256 = "0" * 64
        repo._source_publication_receipts[key] = (
            changed,
            canonical_sha256(changed.model_dump(mode="json")),
        )
    else:
        repo._source_publication_receipts[key] = (receipt, "0" * 64)
    before = snapshot(repo)
    with pytest.raises(PersistenceIntegrityError):
        recover(repo, domain, profile, request)
    assert snapshot(repo) == before


def test_absent_recovery_is_read_only_observation():
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root)
    before = snapshot(repo)
    assert recover(repo, domain, profile, request) is None
    assert snapshot(repo) == before


def context_for(repo, domain, profile, receipt):
    from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy
    from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
    from dungeonmind.application.vnext.materialization import decode_native_graph_payload
    from dungeonmind.application.vnext.read_context import KnowledgeReadContext
    from dungeonmind.contracts.vnext.projection import ProjectionRequest

    stored = repo.get_revision(receipt.space_id, receipt.publication_receipt.published_revision_id)
    parsed = build_parsed_knowledge_revision(
        revision=stored.revision, decoded_content=decode_native_graph_payload(stored.graph_payload)
    )
    return KnowledgeReadContext(
        parsed=parsed,
        request=ProjectionRequest(
            space_id=receipt.space_id,
            revision_id=parsed.revision_id,
            scope_selector={"include_unscoped": True},
            audience_labels=[],
            standing_selector=["established"],
        ),
        domain_contract=domain,
        semantic_profile=profile,
        domain_policy=AlwaysAdmitPolicy(policy_id=domain.admission_policy_id),
        source_reader=repo.open_native_source_view(receipt.space_id),
    )


def exercise_authorized_reads(repo, mode):
    from dungeonmind.application.vnext.alias_search import AliasSearchReadService
    from dungeonmind.application.vnext.entity_reads import EntityReadService
    from dungeonmind.application.vnext.search import SearchReadService

    domain, profile, root, request, receipt = exercise_success(repo, mode)
    context = context_for(repo, domain, profile, receipt)
    entity = next(b.durable_id for b in receipt.result_bindings if b.result_kind == "entity")
    complete = EntityReadService().get_complete_entity(context, entity)
    assert complete.found
    assert [a.alias_text for a in complete.aliases] == ["Exact 🐉 name"]
    assert AliasSearchReadService().search_aliases(context, "Exact").hits
    assert SearchReadService().search_entities(context, "Exact").hits
    repo.withdraw_native_source(
        space_id=root.space_id,
        source_artifact_id=root.source_artifact_id,
        source_revision_id=root.source_revision_id,
    )
    fresh = context_for(repo, domain, profile, receipt)
    assert not EntityReadService().get_complete_entity(fresh, entity).aliases
    assert not AliasSearchReadService().search_aliases(fresh, "Exact").hits
    assert not SearchReadService().search_entities(fresh, "Exact").hits
    assert (
        access(
            repo, domain, root, request.contribution.items[1].metadata.evidence_ref_ids[0]
        ).status
        == "unavailable"
    )
    assert recover(repo, domain, profile, request) == receipt


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_authorized_names_aliases_citations_withdrawal(mode):
    exercise_authorized_reads(InMemoryNativeSourceEvidenceRepository(), mode)


def exercise_crossfamily_id_conflicts(repo):
    domain, profile, _, root = setup_source(repo)
    old = extension(repo, root, operation="shared:operation", start=9, end=10)
    publish_extension(repo, domain, profile, old)
    req = request_for(repo, domain, profile, root, operation="new:request")
    req.publication_id = "shared:operation"
    before = repo.get_head(root.space_id)
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        publish(repo, domain, profile, req)
    assert repo.get_head(root.space_id) == before
    req = request_for(repo, domain, profile, root, operation="composed:operation")
    result = publish(repo, domain, profile, req)
    old2 = extension(repo, root, operation="composed:operation", start=10, end=11)
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        publish_extension(repo, domain, profile, old2)
    assert (
        repo.get_head(root.space_id).head_revision_id
        == result.publication_receipt.published_revision_id
    )


def test_crossfamily_publication_ids_conflict():
    exercise_crossfamily_id_conflicts(InMemoryNativeSourceEvidenceRepository())


def test_reuse_receipt_cannot_be_an_introduction():
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, root, _, receipt = exercise_success(repo, "new_intervals")
    req = request_for(
        repo,
        domain,
        profile,
        root,
        mode="existing_support",
        operation="reuse:once",
        support=[support_ref(receipt, receipt.proofs[0], "publication")],
    )
    reused = publish(repo, domain, profile, req)
    bad = support_ref(receipt, receipt.proofs[0], "publication")
    bad["introducing_operation_id"] = reused.publication_id
    bad["introducing_receipt_sha256"] = canonical_sha256(reused.model_dump(mode="json"))
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        request_for(
            repo,
            domain,
            profile,
            root,
            mode="existing_support",
            operation="reuse:bad",
            support=[bad],
        )


def test_unicode_crlf_exact_new_span_and_reuse():
    import hashlib

    from dungeonmind.application.vnext import get_native_source_publication_support
    from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
    from dungeonmind.application.vnext.native_source_admission import (
        publish_native_text_source_evidence,
    )
    from dungeonmind.contracts.vnext.domain import SemanticProfilePredicate
    from tests.unit.test_vnext_native_source_admission import NOW, _domain, _profile, _request

    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile = _domain(), _profile()
    domain.claim_modes = ["test:source"]
    profile.predicates = [
        SemanticProfilePredicate(term="test:name", allowed_value_kinds=["literal"])
    ]
    genesis = initialize_empty_knowledge_space(
        repository=repo,
        space_id="space:unicode",
        initialization_id="init:unicode",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    body = "A🐉\r\nÉ exact\r\n"
    admission = _request(
        space_id="space:unicode", parent_revision_id=genesis.published_revision_id, body=body
    )
    admission.spans[0].end_byte = 1
    admission.spans[0].expected_slice_sha256 = hashlib.sha256(b"A").hexdigest()
    root = publish_native_text_source_evidence(
        repository=repo, request=admission, domain_contract=domain, semantic_profile=profile
    )
    basis = NativeSourcePublicationBasisV1(
        space_id=root.space_id,
        publication_id="unicode:one",
        original_admission_id=root.admission_id,
        source_artifact_id=root.source_artifact_id,
        source_revision_id=root.source_revision_id,
        expected_body_sha256=hashlib.sha256(body.encode()).hexdigest(),
        expected_parent_revision_id=root.published_revision_id,
        expected_source_authority_epoch=root.source_authority_epoch,
        created_at=NOW + timedelta(minutes=2),
        evidence={
            "mode": "new_intervals",
            "spans": [
                dict(
                    client_ref="unicode",
                    evidence_role="support",
                    start_byte=1,
                    end_byte=len(body.encode()),
                    expected_slice_sha256=hashlib.sha256(body.encode()[1:]).hexdigest(),
                )
            ],
        },
    )
    ev = preview_native_source_publication_evidence(
        repository=repo, request=basis, domain_contract=domain, semantic_profile=profile
    )[0]
    # Reuse the real public prospective shape, without any private allocation.
    template = request_for(
        repo, domain, profile, root, mode="existing_support", operation="unicode:template"
    )
    data = template.model_dump(mode="json")
    data.update(basis.model_dump(mode="json"))
    data["schema_version"] = "dm_governed_native_source_publication_v1"
    data["contribution"]["items"][1]["metadata"]["evidence_ref_ids"] = [ev.evidence_ref_id]
    data["aliases"][0]["evidence_ref_ids"] = [ev.evidence_ref_id]
    request = GovernedNativeSourcePublicationV1.model_validate(data)
    receipt = publish(repo, domain, profile, request)
    opened = access(repo, domain, root, ev.evidence_ref_id)
    assert opened.body_text == body
    assert (opened.span_start_byte, opened.span_end_byte, opened.span_sha256) == (
        1,
        len(body.encode()),
        hashlib.sha256(body.encode()[1:]).hexdigest(),
    )
    assert (
        opened.body_text.encode()[opened.span_start_byte : opened.span_end_byte]
        == body.encode()[1:]
    )
    ref = get_native_source_publication_support(
        repository=repo,
        space_id=root.space_id,
        source_revision_id=root.source_revision_id,
        span_id=receipt.proofs[0].span_id,
    )
    assert ref.proof == receipt.proofs[0]


def test_support_private_source_ref_metadata_is_not_read_authority():
    from dungeonmind.application.vnext import get_native_source_publication_support

    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo, private=True)
    ref = get_native_source_publication_support(
        repository=repo,
        space_id=root.space_id,
        source_revision_id=root.source_revision_id,
        span_id=root.bindings[0].span_id,
    )
    assert ref is not None
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        request_for(
            repo,
            domain,
            profile,
            root,
            mode="existing_support",
            support=[ref.model_dump(mode="json")],
        )
    assert access(repo, domain, root, ref.evidence_ref_id).status == "unavailable"
    assert (
        access(repo, domain, root, ref.evidence_ref_id, audience=("role:gm",)).status == "available"
    )


def test_new_standalone_schema_is_reproducible():
    import json
    from pathlib import Path

    path = (
        Path(__file__).parents[2]
        / "Docs/Contracts/vnext/dm_governed_native_source_publication_v1.json"
    )
    assert path.read_text() == json.dumps(contract_bundle(), sort_keys=True, indent=2) + "\n"


def destructive_request(repo, mode, kind):
    from dungeonmind.application.vnext.native_source_admission import (
        publish_native_text_source_evidence,
    )
    from tests.unit.test_vnext_native_source_admission import NOW, _request

    domain, profile, first_root, _, first = exercise_success(repo, "new_intervals")
    # Another actual source B must never authorize deletion/mutation of A facts.
    source_b = _request(
        space_id=first_root.space_id,
        admission_id="admit:second",
        parent_revision_id=first.publication_receipt.published_revision_id,
    )
    second_root = publish_native_text_source_evidence(
        repository=repo, request=source_b, domain_contract=domain, semantic_profile=profile
    )
    request = request_for(
        repo, domain, profile, second_root, mode=mode, operation="composed:second"
    )
    target = next(b.durable_id for b in first.result_bindings if b.result_kind == "assertion")
    entity = next(b.durable_id for b in first.result_bindings if b.result_kind == "entity")
    if kind == "retract_assertion":
        item = dict(kind=kind, item_id="destructive", target_assertion_id=target)
    elif kind == "supersede_assertion":
        stored = repo.get_revision(
            first_root.space_id, first.publication_receipt.published_revision_id
        )
        assertion = stored.graph_payload["assertions"][0]
        assertion["assertion_id"] = "asrt:replacement"
        item = dict(
            kind=kind,
            item_id="destructive",
            target_assertion_id=target,
            replacement_assertion=assertion,
        )
    else:
        item = dict(
            kind=kind,
            item_id="destructive",
            decision=dict(
                decision_id="decision:destructive",
                space_id=first_root.space_id,
                decision_kind="alias_remove",
                subject_entity_ids=[entity],
                alias="Exact 🐉 name",
                created_at=NOW,
            ),
        )
    data = request.model_dump(mode="json")
    data["contribution"]["items"].append(item)
    data["dispositions"].append(dict(item_id="destructive", disposition="accepted"))
    return domain, profile, request, data


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
@pytest.mark.parametrize(
    "kind", ["retract_assertion", "supersede_assertion", "propose_identity_decision"]
)
def test_destructive_governance_refused_before_io(mode, kind):
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, valid, data = destructive_request(repo, mode, kind)
    before = snapshot(repo)
    with pytest.raises(ValidationError, match="create-only"):
        GovernedNativeSourcePublicationV1.model_validate(data)
    # A constructed/corrupted caller model cannot bypass revalidation at entry.
    from dungeonmind.contracts.vnext.contribution import ContributionDisposition
    from dungeonmind.contracts.vnext.prospective import ProspectiveKnowledgeContribution

    request = valid.model_copy(
        update={
            "contribution": ProspectiveKnowledgeContribution.model_validate(data["contribution"]),
            "dispositions": [
                ContributionDisposition.model_validate(d) for d in data["dispositions"]
            ],
        }
    )
    with pytest.raises(ValidationError, match="create-only"):
        publish(repo, domain, profile, request)
    assert snapshot(repo) == before


def test_rejected_destructive_intent_is_sealed_but_never_applied():
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, data = destructive_request(repo, "existing_support", "retract_assertion")
    data["dispositions"][-1]["disposition"] = "rejected"
    request = GovernedNativeSourcePublicationV1.model_validate(data)
    before = repo.get_revision(request.space_id, request.expected_parent_revision_id).graph_payload
    receipt = publish(repo, domain, profile, request)
    child = repo.get_revision(
        request.space_id, receipt.publication_receipt.published_revision_id
    ).graph_payload
    assert all(a in child["assertions"] for a in before["assertions"])
    request.contribution.items[-1].target_assertion_id = "asrt:other"
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        recover(repo, domain, profile, request)


@pytest.mark.parametrize("substitute", ["root", "extension", "publication"])
def test_valid_wrong_revision_substitution_refused(substitute):
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    intermediate = extension(repo, root, operation="intermediate:extension", start=9, end=10)
    introduced = publish_extension(repo, domain, profile, intermediate)
    first_request = request_for(repo, domain, profile, root)
    first = publish(repo, domain, profile, first_request)
    if substitute == "root":
        request, result = first_request, first
        target = root.published_revision_id
    else:
        original = introduced if substitute == "extension" else first
        proof = original.proofs[0]
        request = request_for(
            repo,
            domain,
            profile,
            root,
            mode="existing_support",
            operation="reuse:tested",
            support=[support_ref(original, proof, substitute)],
        )
        result = publish(repo, domain, profile, request)
        target = original.publication_receipt.published_revision_id
    replacement = repo.get_revision(root.space_id, result.publication_receipt.published_revision_id)

    class WrongValidRow:
        def __getattr__(self, name):
            return getattr(repo, name)

        def get_revision(self, space_id, revision_id):
            if revision_id == target:
                return replacement
            return repo.get_revision(space_id, revision_id)

    before = snapshot(repo)
    with pytest.raises(PersistenceIntegrityError):
        recover(WrongValidRow(), domain, profile, request)
    assert snapshot(repo) == before


@pytest.mark.parametrize(
    "field", ["command_sha256", "graph_payload_sha256", "expected_parent_revision_id"]
)
def test_original_publication_commitments_verified(field):
    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, root, request, _ = exercise_success(repo, "new_intervals")
    actual = root.publication_receipt
    changed = actual.model_copy(
        update={field: "0" * 64 if field.endswith("sha256") else "rev:foreign"}
    )

    class WrongOriginalCommitment:
        def __getattr__(self, name):
            return getattr(repo, name)

        def get_native_source_publication_source(self, space, admission):
            revision, proofs, receipt = repo.get_native_source_publication_source(space, admission)
            return revision, proofs, receipt.model_copy(update={"publication_receipt": changed})

        def get_publication_receipt(self, space, operation):
            return (
                changed
                if operation == root.admission_id
                else repo.get_publication_receipt(space, operation)
            )

    before = snapshot(repo)
    with pytest.raises(PersistenceIntegrityError):
        recover(WrongOriginalCommitment(), domain, profile, request)
    assert snapshot(repo) == before


def test_original_context_proof_cannot_be_upgraded_to_support():
    from dungeonmind.application.vnext import get_native_source_publication_support
    from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
    from dungeonmind.application.vnext.native_source_admission import (
        publish_native_text_source_evidence,
    )
    from dungeonmind.contracts.vnext.domain import SemanticProfilePredicate
    from tests.unit.test_vnext_native_source_admission import NOW, _domain, _profile, _request

    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile = _domain(), _profile()
    domain.claim_modes = ["test:source"]
    profile.predicates = [
        SemanticProfilePredicate(term="test:name", allowed_value_kinds=["literal"])
    ]
    genesis = initialize_empty_knowledge_space(
        repository=repo,
        space_id="space:context",
        initialization_id="context:init",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    admission = _request(space_id="space:context", parent_revision_id=genesis.published_revision_id)
    admission.spans[0].evidence_role = "context"
    root = publish_native_text_source_evidence(
        repository=repo, request=admission, domain_contract=domain, semantic_profile=profile
    )
    view = repo.open_native_source_view(root.space_id)
    proof = view.get_native_text_source(
        source_artifact_id=root.source_artifact_id,
        source_revision_id=root.source_revision_id,
        span_id=root.bindings[0].span_id,
    ).span_proof
    assert (
        get_native_source_publication_support(
            repository=repo,
            space_id=root.space_id,
            source_revision_id=root.source_revision_id,
            span_id=proof.span_id,
        )
        is None
    )
    before = snapshot(repo)
    with pytest.raises(NativeTextSourceAdmissionIntegrityError):
        request_for(
            repo,
            domain,
            profile,
            root,
            mode="existing_support",
            support=[support_ref(root, proof, "admission")],
        )
    assert snapshot(repo) == before


@pytest.mark.parametrize("mode", ["new_intervals", "existing_support"])
def test_memory_lock_held_publication_excludes_withdrawal(mode):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event

    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, _, root = setup_source(repo)
    request = request_for(repo, domain, profile, root, mode=mode)
    entered, release, started = Event(), Event(), Event()

    def hold():
        entered.set()
        assert release.wait(5)

    repo._after_revision_insert = hold

    def withdraw():
        started.set()
        return repo.withdraw_native_source(
            space_id=root.space_id,
            source_artifact_id=root.source_artifact_id,
            source_revision_id=root.source_revision_id,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        publication = pool.submit(publish, repo, domain, profile, request)
        try:
            assert entered.wait(5)
            withdrawal = pool.submit(withdraw)
            assert started.wait(5)
            with pytest.raises(TimeoutError):
                withdrawal.result(timeout=0.1)
        finally:
            release.set()
        receipt = publication.result(timeout=5)
        epoch = withdrawal.result(timeout=5)
    assert epoch == receipt.source_authority_epoch_after + 1
    assert recover(repo, domain, profile, request) == receipt


def test_same_computed_child_but_changed_preparation_time_conflicts():
    from dungeonmind.application.vnext.authority import revision_from_command
    from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand

    repo = InMemoryNativeSourceEvidenceRepository()
    domain, profile, root, request, receipt = exercise_success(repo, "new_intervals")
    stored = repo.get_revision(root.space_id, receipt.publication_receipt.published_revision_id)
    command = PublishKnowledgeRevisionCommand(
        space_id=root.space_id,
        parent_revision_id=stored.revision.parent_revision_id,
        expected_parent_revision_id=stored.revision.parent_revision_id,
        operation_ids=stored.revision.operation_ids,
        graph_schema=stored.revision.graph_schema,
        graph_payload=stored.graph_payload,
        domain_contract_ref=stored.revision.domain_contract_ref,
        semantic_profile_ref=stored.revision.semantic_profile_ref,
        migration_origin_ref=stored.revision.migration_origin_ref,
        created_at=stored.revision.created_at,
    )
    altered = command.model_copy(update={"created_at": command.created_at + timedelta(seconds=1)})
    assert revision_from_command(command).revision_id == revision_from_command(altered).revision_id
    request.created_at = altered.created_at
    before = snapshot(repo)
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        publish(repo, domain, profile, request)
    assert snapshot(repo) == before
