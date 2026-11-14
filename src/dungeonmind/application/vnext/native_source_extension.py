"""Additional evidence on an immutable source; no source or semantic replacement."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
)
from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.native_source import (
    GovernedNativeSourceEvidenceExtensionReceiptV1,
    GovernedNativeSourceEvidenceExtensionV1,
    NativeSourceAdmissionReceiptV1,
    NativeSourceEvidenceExtensionReceiptV1,
    NativeSourceEvidenceExtensionV1,
    NativeTextSourceAdmissionBindingV1,
    NativeUtf8SpanProofV1,
)
from dungeonmind.contracts.vnext.prospective import ProspectiveResultBinding
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .builder import build_parsed_knowledge_revision
from .errors import KnowledgePublicationIdempotencyConflictError, KnowledgeStaleParentRevisionError
from .materialization import (
    NATIVE_VNEXT_GRAPH_SCHEMA,
    GovernedPublicationIdentity,
    decode_native_graph_payload,
    encode_native_graph_payload,
)
from .native_source_access import open_admitted_native_text, open_native_text_source_access_context
from .native_source_admission import (
    _descriptor_refs,
    _fail,
    _metadata_declared,
    _span_slice,
    allocate_native_source_id,
)
from .prospective import _plan_prospective_publication
from .publication import _verify_receipt


@dataclass(frozen=True)
class ExtensionPlan:
    command: PublishKnowledgeRevisionCommand
    root: NativeSourceAdmissionReceiptV1
    proofs: tuple[NativeUtf8SpanProofV1, ...]
    bindings: tuple[NativeTextSourceAdmissionBindingV1, ...]
    intent_sha256: str
    result_bindings: tuple[ProspectiveResultBinding, ...] | None = None


def extension_intent(
    request: NativeSourceEvidenceExtensionV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> str:
    return canonical_sha256(
        {
            "request": request.model_dump(mode="json"),
            "domain": domain_contract.model_dump(mode="json"),
            "profile": semantic_profile.model_dump(mode="json"),
        }
    )


def _require_original_ancestor(
    repository: Any, space_id: str, root_revision: str, revision_id: str
) -> None:
    seen = set()
    current = revision_id
    while current != root_revision:
        if current in seen:
            _fail("extension_source_lineage_cycle")
        seen.add(current)
        stored = repository.get_revision(space_id, current)
        if (
            stored is None
            or stored.revision.space_id != space_id
            or stored.revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA
        ):
            _fail("extension_source_lineage_missing")
        current = stored.revision.parent_revision_id
        if current is None:
            _fail("extension_original_admission_not_ancestor")


def extension_plan(
    *,
    repository: Any,
    request: NativeSourceEvidenceExtensionV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    audience_labels: Sequence[str],
    registered_intervals: set[tuple[int, int]],
) -> ExtensionPlan | NativeSourceEvidenceExtensionReceiptV1:
    """Called while the owning repository holds its epoch and publication lock."""
    head = repository.get_head(request.space_id)
    if head is None:
        _fail("extension_world_missing")
    root = repository.get_native_source_admission_receipt(
        request.space_id, request.original_admission_id
    )
    if root is None or (root.source_artifact_id, root.source_revision_id) != (
        request.source_artifact_id,
        request.source_revision_id,
    ):
        _fail("extension_original_admission_mismatch")
    context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=head.head_revision_id,
        domain_contract=domain_contract,
        audience_labels=audience_labels,
    )
    access = open_admitted_native_text(context, root.bindings[0].evidence_ref_id)
    if access.status != "available" or (
        access.source_artifact_id,
        access.source_revision_id,
        access.body_sha256,
    ) != (request.source_artifact_id, request.source_revision_id, request.expected_body_sha256):
        _fail("extension_source_inaccessible")
    _require_original_ancestor(
        repository, request.space_id, root.published_revision_id, head.head_revision_id
    )
    if access.body_text is None:
        _fail("extension_source_body_missing")
    body = access.body_text.encode("utf-8")
    intent = extension_intent(request, domain_contract, semantic_profile)
    prior = repository.get_native_source_evidence_extension_receipt(
        request.space_id, request.extension_id
    )
    if prior is not None and prior.intent_sha256 != intent:
        raise KnowledgePublicationIdempotencyConflictError(
            space_id=request.space_id, publication_id=request.extension_id
        )
    # Replay is authorized above, but independent of today's parent and epoch.
    if prior is None:
        if head.head_revision_id != request.expected_parent_revision_id:
            raise KnowledgeStaleParentRevisionError(
                space_id=request.space_id,
                expected_parent_revision_id=request.expected_parent_revision_id,
                actual_head_revision_id=head.head_revision_id,
            )
        if context.source_view.epoch != request.expected_source_authority_epoch:
            _fail("extension_source_epoch_stale")
        if repository.get_publication_receipt(request.space_id, request.extension_id) is not None:
            raise KnowledgePublicationIdempotencyConflictError(
                space_id=request.space_id, publication_id=request.extension_id
            )
    parent = repository.get_revision(request.space_id, request.expected_parent_revision_id)
    if parent is None or parent.revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        _fail("extension_parent_missing")
    _require_original_ancestor(
        repository,
        request.space_id,
        root.published_revision_id,
        request.expected_parent_revision_id,
    )
    domain_ref, profile_ref = _descriptor_refs(domain_contract, semantic_profile)
    if (
        parent.revision.domain_contract_ref != domain_ref
        or parent.revision.semantic_profile_ref != profile_ref
    ):
        _fail("extension_descriptor_mismatch")
    content = decode_native_graph_payload(parent.graph_payload)
    evidence = {e.evidence_ref_id: e for e in content.evidence}
    if len(evidence) != len(content.evidence):
        _fail("extension_parent_evidence_duplicate")
    proofs, bindings = [], []
    for span in request.spans:
        if prior is None and (span.start_byte, span.end_byte) in registered_intervals:
            _fail("extension_interval_already_registered")
        selected = _span_slice(body, span)
        if hashlib.sha256(selected).hexdigest() != span.expected_slice_sha256:
            _fail("extension_slice_digest_mismatch")
        if not _metadata_declared(
            span.domain_metadata, declared=frozenset(domain_contract.source_annotation_schemas)
        ):
            _fail("extension_source_annotation_undeclared")
        ids = {
            kind: allocate_native_source_id(
                space_id=request.space_id,
                admission_id=request.extension_id,
                identity_kind=kind,
                client_ref=span.client_ref,
            )
            for kind in ("span", "evidence")
        }
        if ids["evidence"] in evidence:
            _fail("extension_evidence_identity_collision")
        evidence[ids["evidence"]] = EvidenceRefV3(
            evidence_ref_id=ids["evidence"],
            source_artifact_id=request.source_artifact_id,
            source_revision_id=request.source_revision_id,
            evidence_role=span.evidence_role,
            can_open_source=True,
            can_highlight_span=True,
            source_span_ref_id=ids["span"],
            domain_metadata=span.domain_metadata,
        )
        proofs.append(
            NativeUtf8SpanProofV1(
                span_id=ids["span"],
                source_revision_id=request.source_revision_id,
                evidence_ref_id=ids["evidence"],
                start_byte=span.start_byte,
                end_byte=span.end_byte,
                slice_sha256=span.expected_slice_sha256,
            )
        )
        bindings.append(
            NativeTextSourceAdmissionBindingV1(
                client_ref=span.client_ref, span_id=ids["span"], evidence_ref_id=ids["evidence"]
            )
        )
    command = PublishKnowledgeRevisionCommand(
        space_id=request.space_id,
        parent_revision_id=request.expected_parent_revision_id,
        expected_parent_revision_id=request.expected_parent_revision_id,
        operation_ids=[request.extension_id],
        graph_schema=NATIVE_VNEXT_GRAPH_SCHEMA,
        graph_payload=encode_native_graph_payload(
            entities={e.entity_id: e for e in content.entities},
            assertions={a.assertion_id: a for a in content.assertions},
            aliases={a.alias_id: a for a in content.aliases},
            evidence=evidence,
        ),
        domain_contract_ref=domain_ref,
        semantic_profile_ref=profile_ref,
        migration_origin_ref=parent.revision.migration_origin_ref,
        created_at=request.created_at,
    )
    result_bindings = None
    if isinstance(request, GovernedNativeSourceEvidenceExtensionV1):
        parsed_parent = build_parsed_knowledge_revision(
            revision=parent.revision,
            decoded_content=content,
        )
        materialization, resolved = _plan_prospective_publication(
            parent=parsed_parent,
            prospective_contribution=request.contribution,
            dispositions=request.dispositions,
            publication_id=request.extension_id,
            publication=GovernedPublicationIdentity(
                operation_ids=(request.extension_id,),
                created_at=request.created_at,
                expected_parent_revision_id=request.expected_parent_revision_id,
            ),
            domain_contract=domain_contract,
            semantic_profile=semantic_profile,
            admitted_evidence=tuple(evidence[binding.evidence_ref_id] for binding in bindings),
        )
        command = materialization.command
        result_bindings = resolved.committed_result_bindings
    plan = ExtensionPlan(command, root, tuple(proofs), tuple(bindings), intent, result_bindings)
    if prior is not None:
        verify_extension_receipt(repository, prior, plan)
        return prior.model_copy(deep=True)
    return plan


def make_extension_receipt(
    plan: ExtensionPlan, epoch: int, publication_receipt: KnowledgePublicationReceipt
) -> NativeSourceEvidenceExtensionReceiptV1:
    receipt = NativeSourceEvidenceExtensionReceiptV1(
        space_id=plan.root.space_id,
        extension_id=publication_receipt.publication_id,
        original_admission_id=plan.root.admission_id,
        original_admission_sha256=canonical_sha256(plan.root.model_dump(mode="json")),
        intent_sha256=plan.intent_sha256,
        source_artifact_id=plan.root.source_artifact_id,
        source_revision_id=plan.root.source_revision_id,
        origin=plan.root.origin,
        source_authority_epoch=epoch,
        bindings=list(plan.bindings),
        proofs=list(plan.proofs),
        publication_receipt=publication_receipt,
    )
    if plan.result_bindings is None:
        return receipt
    return GovernedNativeSourceEvidenceExtensionReceiptV1(
        **receipt.model_dump(),
        result_bindings=list(plan.result_bindings),
    )


def verify_extension_receipt(
    repository: Any, receipt: NativeSourceEvidenceExtensionReceiptV1, plan: ExtensionPlan
) -> None:
    if receipt != make_extension_receipt(
        plan, receipt.source_authority_epoch, receipt.publication_receipt
    ):
        raise PersistenceIntegrityError("extension receipt lineage or proof drift")
    _verify_receipt(
        receipt.publication_receipt,
        plan.command,
        publication_id=receipt.extension_id,
        repository=repository,
    )
    view = repository.open_native_source_view(receipt.space_id)
    if receipt.source_authority_epoch > view.epoch:
        raise PersistenceIntegrityError("extension receipt epoch ahead of source authority")
    for proof in plan.proofs:
        source = view.get_native_text_source(
            source_artifact_id=receipt.source_artifact_id,
            source_revision_id=receipt.source_revision_id,
            span_id=proof.span_id,
        )
        if (
            source is None
            or source.span_proof != proof
            or source.authority_epoch != receipt.source_authority_epoch
        ):
            raise PersistenceIntegrityError("extension receipt source proof drift")


def snapshot_extension_inputs(
    request: NativeSourceEvidenceExtensionV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> tuple[
    NativeSourceEvidenceExtensionV1,
    DomainContractDescriptor,
    SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
]:
    request_snapshot = type(request).model_validate(request.model_dump(mode="json"))
    domain_snapshot = DomainContractDescriptor.model_validate(
        domain_contract.model_dump(mode="json")
    )
    if type(semantic_profile) not in (SemanticProfileDescriptorV2, SemanticProfileDescriptorV3):
        _fail("extension_profile_invalid")
    profile_snapshot = type(semantic_profile).model_validate(
        semantic_profile.model_dump(mode="json")
    )
    return request_snapshot, domain_snapshot, profile_snapshot


def preview_native_source_evidence_extension(
    *,
    repository: Any,
    request: NativeSourceEvidenceExtensionV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    audience_labels: Sequence[str] = (),
) -> tuple[EvidenceRefV3, ...]:
    """Validate candidate evidence at a pin without reserving it.

    Publication revalidates under the repository locks, including registered
    intervals and the source authority epoch.
    """
    if type(request) is not NativeSourceEvidenceExtensionV1:
        _fail("extension_preview_requires_evidence_only")
    request, domain, profile = snapshot_extension_inputs(request, domain_contract, semantic_profile)
    plan = extension_plan(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
        audience_labels=tuple(audience_labels),
        registered_intervals=set(),
    )
    if isinstance(plan, NativeSourceEvidenceExtensionReceiptV1):
        _fail("extension_preview_already_published")
    evidence = {
        item.evidence_ref_id: item
        for item in decode_native_graph_payload(plan.command.graph_payload).evidence
    }
    return tuple(evidence[binding.evidence_ref_id] for binding in plan.bindings)


def publish_native_source_evidence_extension(
    *,
    repository: Any,
    request: NativeSourceEvidenceExtensionV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    audience_labels: Sequence[str] = (),
) -> NativeSourceEvidenceExtensionReceiptV1:
    """Trusted host supplies its current audience; repository atomically owns all validation."""
    request, domain, profile = snapshot_extension_inputs(request, domain_contract, semantic_profile)
    return repository.publish_native_source_evidence_extension(
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
        audience_labels=tuple(audience_labels),
    )
