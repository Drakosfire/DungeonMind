"""One-source authorized atomic graph publication and immutable metadata recovery."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, NoReturn, TypeVar

from pydantic import ValidationError

from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
)
from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.native_source import (
    NativeSourceAdmissionReceiptV1,
    NativeSourceEvidenceExtensionReceiptV1,
    NativeSourceEvidenceExtensionV1,
    NativeTextSourceAdmissionBindingV1,
    NativeUtf8SpanProofV1,
)
from dungeonmind.contracts.vnext.native_source_publication import (
    GovernedNativeSourcePublicationReceiptV1,
    GovernedNativeSourcePublicationV1,
    NativeSourcePublicationBasisV1,
    NativeSourcePublicationSupportRefV1,
)
from dungeonmind.contracts.vnext.prospective import ProspectiveResultBinding
from dungeonmind.contracts.vnext.prospective_aliases import ProspectiveAliasContributionV1
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .authority import verify_stored_revision
from .builder import build_parsed_knowledge_revision
from .errors import KnowledgePublicationIdempotencyConflictError, KnowledgeStaleParentRevisionError
from .materialization import GovernedPublicationIdentity, decode_native_graph_payload
from .model import ParsedKnowledgeRevision
from .native_source_access import (
    NativeTextSourceAccessContext,
    open_admitted_native_text,
    open_native_text_source_access_context,
)
from .native_source_admission import _descriptor_refs, _fail
from .native_source_extension import (
    _reconstruct_extension_plan,
    _require_original_ancestor,
)
from .ports import NativeSourcePublicationRepository
from .prospective import _plan_prospective_publication
from .prospective_aliases import _plan_prospective_alias_contribution
from .publication import _command_from_stored, _verify_receipt
from .records import StoredKnowledgeRevision


@dataclass(frozen=True)
class SourcePublicationPlan:
    command: PublishKnowledgeRevisionCommand
    root: NativeSourceAdmissionReceiptV1
    intent_sha256: str
    proofs: tuple[NativeUtf8SpanProofV1, ...]
    bindings: tuple[NativeTextSourceAdmissionBindingV1, ...]
    result_bindings: tuple[ProspectiveResultBinding, ...]


RequestT = TypeVar("RequestT", bound=NativeSourcePublicationBasisV1)


def snapshot_inputs(
    request: RequestT,
    domain: DomainContractDescriptor,
    profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> tuple[
    RequestT,
    DomainContractDescriptor,
    SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
]:
    if type(request) not in (NativeSourcePublicationBasisV1, GovernedNativeSourcePublicationV1):
        _fail("source_publication_request_type")
    request = type(request).model_validate(request.model_dump(mode="json"))
    domain = DomainContractDescriptor.model_validate(domain.model_dump(mode="json"))
    if type(profile) not in (SemanticProfileDescriptorV2, SemanticProfileDescriptorV3):
        _fail("source_publication_profile_type")
    profile = type(profile).model_validate(profile.model_dump(mode="json"))
    return request, domain, profile


def publication_intent(
    request: NativeSourcePublicationBasisV1,
    domain: DomainContractDescriptor,
    profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> str:
    return canonical_sha256(
        {
            "request": request.model_dump(mode="json"),
            "domain": domain.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
        }
    )


def _conflict(request: NativeSourcePublicationBasisV1) -> NoReturn:
    raise KnowledgePublicationIdempotencyConflictError(
        space_id=request.space_id, publication_id=request.publication_id
    )


def _verify_original_publication(
    repository: NativeSourcePublicationRepository,
    publication: KnowledgePublicationReceipt,
    space_id: str,
    publication_id: str,
    revision_id: str,
) -> StoredKnowledgeRevision:
    if (publication.space_id, publication.publication_id, publication.published_revision_id) != (
        space_id,
        publication_id,
        revision_id,
    ):
        raise PersistenceIntegrityError("original publication identity mismatch")
    stored = repository.get_revision(space_id, revision_id)
    if stored is None or (stored.revision.space_id, stored.revision.revision_id) != (
        space_id,
        revision_id,
    ):
        raise PersistenceIntegrityError("original publication requested revision mismatch")
    verify_stored_revision(stored)
    command = _command_from_stored(stored)
    if (
        canonical_sha256(command.model_dump(mode="json")) != publication.command_sha256
        or stored.graph_payload_sha256 != publication.graph_payload_sha256
        or stored.revision.parent_revision_id != publication.expected_parent_revision_id
    ):
        raise PersistenceIntegrityError("original publication command or child drift")
    return stored


def _source(
    repository: NativeSourcePublicationRepository,
    request: NativeSourcePublicationBasisV1,
    *,
    strict: bool,
) -> tuple[NativeSourceAdmissionReceiptV1, tuple[NativeUtf8SpanProofV1, ...]]:
    source_revision, proofs, root = repository.get_native_source_publication_source(
        request.space_id, request.original_admission_id
    )
    if root is None or (
        root.space_id,
        root.admission_id,
        root.source_artifact_id,
        root.source_revision_id,
    ) != (
        request.space_id,
        request.original_admission_id,
        request.source_artifact_id,
        request.source_revision_id,
    ):
        _fail("source_publication_original_admission_mismatch")
    if (
        source_revision.source_artifact_id,
        source_revision.source_revision_id,
        source_revision.content_sha256,
    ) != (request.source_artifact_id, request.source_revision_id, request.expected_body_sha256):
        _fail("source_publication_body_commitment_mismatch")
    if (
        repository.get_publication_receipt(request.space_id, root.admission_id)
        != root.publication_receipt
    ):
        raise PersistenceIntegrityError("original publication receipt drift")
    if strict:
        _verify_original_publication(
            repository,
            root.publication_receipt,
            request.space_id,
            root.admission_id,
            root.published_revision_id,
        )
    return root, proofs


def _verify_support(
    repository: NativeSourcePublicationRepository,
    request: NativeSourcePublicationBasisV1,
    ref: NativeSourcePublicationSupportRefV1,
    root: NativeSourceAdmissionReceiptV1,
    root_proofs: Sequence[NativeUtf8SpanProofV1],
    *,
    strict: bool,
) -> EvidenceRefV3:
    if ref.introducing_kind == "admission":
        origin = root
        if ref.introducing_operation_id != root.admission_id:
            _fail("source_publication_support_origin_mismatch")
        proofs, epoch = root_proofs, root.source_authority_epoch
    elif ref.introducing_kind == "extension":
        origin = repository.get_native_source_publication_extension_receipt(
            request.space_id, ref.introducing_operation_id
        )
        if origin is None:
            _fail("source_publication_support_origin_missing")
        proofs, epoch = origin.proofs, origin.source_authority_epoch
    else:
        origin = repository.get_native_source_publication_receipt(
            request.space_id, ref.introducing_operation_id
        )
        if origin is None or origin.mode != "new_intervals":
            _fail("source_publication_support_not_introduced")
        proofs, epoch = origin.proofs, origin.source_authority_epoch_after
    if (origin.source_artifact_id, origin.source_revision_id) != (
        request.source_artifact_id,
        request.source_revision_id,
    ):
        _fail("source_publication_support_foreign_source")
    if not isinstance(origin, NativeSourceAdmissionReceiptV1) and (
        origin.original_admission_id != root.admission_id
        or origin.original_admission_sha256 != canonical_sha256(root.model_dump(mode="json"))
    ):
        raise PersistenceIntegrityError("support original admission drift")
    if (
        canonical_sha256(origin.model_dump(mode="json")) != ref.introducing_receipt_sha256
        or ref.proof_authority_epoch != epoch
        or ref.proof not in proofs
    ):
        _fail("source_publication_support_proof_mismatch")
    pub = origin.publication_receipt
    if repository.get_publication_receipt(request.space_id, ref.introducing_operation_id) != pub:
        raise PersistenceIntegrityError("support publication receipt drift")
    _require_original_ancestor(
        repository,
        request.space_id,
        pub.published_revision_id,
        request.expected_parent_revision_id,
        verify_envelopes=strict,
    )
    stored = repository.get_revision(request.space_id, pub.published_revision_id)
    if stored is None or (stored.revision.space_id, stored.revision.revision_id) != (
        request.space_id,
        pub.published_revision_id,
    ):
        raise PersistenceIntegrityError("support introducing requested revision mismatch")
    if strict:
        stored = _verify_original_publication(
            repository,
            pub,
            request.space_id,
            ref.introducing_operation_id,
            pub.published_revision_id,
        )
    original = {
        e.evidence_ref_id: e for e in decode_native_graph_payload(stored.graph_payload).evidence
    }.get(ref.evidence_ref_id)
    if original is None or (
        original.evidence_role,
        original.source_artifact_id,
        original.source_revision_id,
        original.source_span_ref_id,
    ) != ("support", request.source_artifact_id, request.source_revision_id, ref.span_id):
        _fail("source_publication_support_original_role_mismatch")
    return original


def _evidence_plan(
    repository: NativeSourcePublicationRepository,
    request: NativeSourcePublicationBasisV1,
    domain: DomainContractDescriptor,
    profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    *,
    body: bytes | None,
    intervals: set[tuple[int, int]],
    strict: bool,
    source_context: NativeTextSourceAccessContext | None = None,
) -> tuple[
    NativeSourceAdmissionReceiptV1,
    ParsedKnowledgeRevision,
    tuple[EvidenceRefV3, ...],
    tuple[NativeUtf8SpanProofV1, ...],
    tuple[NativeTextSourceAdmissionBindingV1, ...],
]:
    root, root_proofs = _source(repository, request, strict=strict)
    parent = repository.get_revision(request.space_id, request.expected_parent_revision_id)
    if parent is None or (parent.revision.space_id, parent.revision.revision_id) != (
        request.space_id,
        request.expected_parent_revision_id,
    ):
        _fail("source_publication_parent_missing")
    if strict:
        verify_stored_revision(parent)
    if (
        parent.revision.domain_contract_ref,
        parent.revision.semantic_profile_ref,
    ) != _descriptor_refs(domain, profile):
        _fail("source_publication_descriptor_mismatch")
    _require_original_ancestor(
        repository,
        request.space_id,
        root.published_revision_id,
        request.expected_parent_revision_id,
        verify_envelopes=strict,
    )
    content = decode_native_graph_payload(parent.graph_payload)
    parsed = build_parsed_knowledge_revision(revision=parent.revision, decoded_content=content)
    if request.evidence.mode == "new_intervals":
        ext = NativeSourceEvidenceExtensionV1(
            **{
                k: getattr(request, k)
                for k in (
                    "space_id",
                    "original_admission_id",
                    "source_artifact_id",
                    "source_revision_id",
                    "expected_body_sha256",
                    "expected_parent_revision_id",
                    "expected_source_authority_epoch",
                    "created_at",
                )
            },
            extension_id=request.publication_id,
            spans=request.evidence.spans,
        )
        # Immutable recovery reconstructs requested proof identities without reopening bytes.
        plan = _reconstruct_extension_plan(
            repository=repository,
            request=ext,
            domain_contract=domain,
            semantic_profile=profile,
            root=root,
            intent="",
            body=body,
            registered_intervals=intervals,
            prior=None,
            verify_envelopes=False,
        )
        introduced = decode_native_graph_payload(plan.command.graph_payload).evidence
        selected = {p.evidence_ref_id for p in plan.proofs}
        evidence = tuple(e for e in introduced if e.evidence_ref_id in selected)
        return root, parsed, evidence, plan.proofs, plan.bindings
    evidence = []
    for ref in request.evidence.support:
        original = _verify_support(repository, request, ref, root, root_proofs, strict=strict)
        e = {e.evidence_ref_id: e for e in content.evidence}.get(ref.evidence_ref_id)
        if (
            e is None
            or e != original
            or (
                e.source_artifact_id,
                e.source_revision_id,
                e.source_span_ref_id,
                e.evidence_role,
            )
            != (request.source_artifact_id, request.source_revision_id, ref.span_id, "support")
        ):
            _fail("source_publication_support_not_in_parent")
        if source_context is not None:
            opened = open_admitted_native_text(source_context, ref.evidence_ref_id)
            if opened.status != "available" or opened.body_sha256 != request.expected_body_sha256:
                _fail("source_publication_selected_support_inaccessible")
            actual = source_context.source_view.get_native_text_source(
                source_artifact_id=request.source_artifact_id,
                source_revision_id=request.source_revision_id,
                span_id=ref.span_id,
            )
            if (
                actual is None
                or actual.span_proof != ref.proof
                or actual.authority_epoch != ref.proof_authority_epoch
            ):
                _fail("source_publication_selected_support_drift")
        if body is not None:
            if not 0 <= ref.proof.start_byte < ref.proof.end_byte <= len(body):
                _fail("source_publication_support_bounds")
            selected = body[ref.proof.start_byte : ref.proof.end_byte]
            import hashlib

            if hashlib.sha256(selected).hexdigest() != ref.proof.slice_sha256:
                _fail("source_publication_support_slice_mismatch")
            try:
                body[: ref.proof.start_byte].decode("utf8")
                selected.decode("utf8")
            except UnicodeDecodeError:
                _fail("source_publication_support_utf8")
        evidence.append(e)
    return root, parsed, tuple(evidence), (), ()


def _compose(
    repository: NativeSourcePublicationRepository,
    request: GovernedNativeSourcePublicationV1,
    domain: DomainContractDescriptor,
    profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    *,
    body: bytes | None,
    intervals: set[tuple[int, int]],
    strict: bool = False,
    source_context: NativeTextSourceAccessContext | None = None,
) -> SourcePublicationPlan:
    root, parent, evidence, proofs, bindings = _evidence_plan(
        repository,
        request,
        domain,
        profile,
        body=body,
        intervals=intervals,
        strict=strict,
        source_context=source_context,
    )
    selected = {e.evidence_ref_id for e in evidence}
    accepted = {d.item_id for d in request.dispositions if d.disposition == "accepted"}
    for item in request.contribution.items:
        if item.item_id not in accepted:
            continue
        refs = None
        if item.kind == "create_assertion":
            refs = item.metadata.evidence_ref_ids
        elif item.kind == "propose_assertion":
            refs = item.assertion.metadata.evidence_ref_ids
        if refs is not None and (not refs or not set(refs) <= selected):
            _fail("source_publication_fact_evidence_outside_selection")
    for alias in request.aliases:
        if alias.item_id in accepted and not set(alias.evidence_ref_ids) <= selected:
            _fail("source_publication_alias_evidence_outside_selection")
    identity = GovernedPublicationIdentity(
        operation_ids=(request.publication_id,),
        created_at=request.created_at,
        expected_parent_revision_id=request.expected_parent_revision_id,
    )
    if request.aliases:
        _, resolved, command = _plan_prospective_alias_contribution(
            parent=parent,
            request=ProspectiveAliasContributionV1(
                contribution=request.contribution, aliases=request.aliases
            ),
            dispositions=request.dispositions,
            publication=identity,
            publication_id=request.publication_id,
            domain_contract=domain,
            semantic_profile=profile,
            admitted_evidence=evidence if proofs else (),
        )
    else:
        _, resolved, command = _plan_prospective_publication(
            parent=parent,
            prospective_contribution=request.contribution,
            dispositions=request.dispositions,
            publication=identity,
            publication_id=request.publication_id,
            domain_contract=domain,
            semantic_profile=profile,
            admitted_evidence=evidence if proofs else (),
        )
    # Enforce closure on every newly produced/changed fact and alias, including
    # ordinary contribution forms; parent membership alone is never admission.
    allowed = {e.evidence_ref_id for e in evidence}
    original_parent = repository.get_revision(request.space_id, request.expected_parent_revision_id)
    if original_parent is None:
        raise PersistenceIntegrityError("publication original parent disappeared")
    old = decode_native_graph_payload(original_parent.graph_payload)
    old_assertions = {a.assertion_id: a for a in old.assertions}
    old_aliases = {a.alias_id: a for a in old.aliases}
    child = decode_native_graph_payload(command.graph_payload)
    for a in child.assertions:
        if old_assertions.get(a.assertion_id) != a:
            refs = a.metadata.evidence_ref_ids
            if not refs or not set(refs) <= allowed:
                _fail("source_publication_fact_evidence_outside_selection")
    for a in child.aliases:
        if old_aliases.get(a.alias_id) != a and (
            not a.evidence_ref_ids or not set(a.evidence_ref_ids) <= allowed
        ):
            _fail("source_publication_alias_evidence_outside_selection")
    return SourcePublicationPlan(
        command,
        root,
        publication_intent(request, domain, profile),
        tuple(proofs),
        tuple(bindings),
        resolved.committed_result_bindings,
    )


def make_receipt(
    request: GovernedNativeSourcePublicationV1,
    plan: SourcePublicationPlan,
    publication: KnowledgePublicationReceipt,
) -> GovernedNativeSourcePublicationReceiptV1:
    return GovernedNativeSourcePublicationReceiptV1(
        space_id=request.space_id,
        publication_id=request.publication_id,
        original_admission_id=request.original_admission_id,
        original_admission_sha256=canonical_sha256(plan.root.model_dump(mode="json")),
        source_artifact_id=request.source_artifact_id,
        source_revision_id=request.source_revision_id,
        intent_sha256=plan.intent_sha256,
        mode=request.evidence.mode,
        source_authority_epoch_before=request.expected_source_authority_epoch,
        source_authority_epoch_after=request.expected_source_authority_epoch
        + int(request.evidence.mode == "new_intervals"),
        bindings=list(plan.bindings),
        proofs=list(plan.proofs),
        reused_support=request.evidence.support
        if request.evidence.mode == "existing_support"
        else [],
        publication_receipt=publication,
        result_bindings=list(plan.result_bindings),
    )


def publication_plan(
    repository: NativeSourcePublicationRepository,
    request: GovernedNativeSourcePublicationV1,
    domain: DomainContractDescriptor,
    profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    *,
    audience_labels: Sequence[str],
    intervals: set[tuple[int, int]],
) -> SourcePublicationPlan | GovernedNativeSourcePublicationReceiptV1:
    root, _ = _source(repository, request, strict=False)
    head = repository.get_head(request.space_id)
    if head is None:
        _fail("source_publication_world_missing")
    context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=head.head_revision_id,
        domain_contract=domain,
        audience_labels=audience_labels,
    )
    access = open_admitted_native_text(context, root.bindings[0].evidence_ref_id)
    if (
        access.status != "available"
        or access.body_sha256 != request.expected_body_sha256
        or access.body_text is None
    ):
        _fail("source_publication_source_inaccessible")
    prior = repository.get_native_source_publication_receipt(
        request.space_id, request.publication_id
    )
    if prior is not None:
        selected_ids = (
            [p.evidence_ref_id for p in prior.proofs]
            if prior.mode == "new_intervals"
            else [r.evidence_ref_id for r in prior.reused_support]
        )
        for evidence_id in selected_ids:
            selected_access = open_admitted_native_text(context, evidence_id)
            if (
                selected_access.status != "available"
                or selected_access.body_sha256 != request.expected_body_sha256
            ):
                _fail("source_publication_selected_support_inaccessible")
        recovered = recover_governed_native_source_publication(
            repository=repository, request=request, domain_contract=domain, semantic_profile=profile
        )
        if recovered is None:
            raise PersistenceIntegrityError("composed receipt disappeared during recovery")
        return recovered
    if repository.get_publication_receipt(request.space_id, request.publication_id) is not None:
        _conflict(request)
    if head.head_revision_id != request.expected_parent_revision_id:
        raise KnowledgeStaleParentRevisionError(
            space_id=request.space_id,
            expected_parent_revision_id=request.expected_parent_revision_id,
            actual_head_revision_id=head.head_revision_id,
        )
    if context.source_view.epoch != request.expected_source_authority_epoch:
        _fail("source_publication_epoch_stale")
    return _compose(
        repository,
        request,
        domain,
        profile,
        body=access.body_text.encode("utf8"),
        intervals=intervals,
        source_context=context,
    )


def preview_native_source_publication_evidence(
    *,
    repository: NativeSourcePublicationRepository,
    request: NativeSourcePublicationBasisV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    audience_labels: Sequence[str] = (),
) -> tuple[EvidenceRefV3, ...]:
    request, domain, profile = snapshot_inputs(request, domain_contract, semantic_profile)
    if type(request) is not NativeSourcePublicationBasisV1:
        _fail("source_publication_preview_requires_basis")
    root, _ = _source(repository, request, strict=False)
    context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=request.expected_parent_revision_id,
        domain_contract=domain,
        audience_labels=audience_labels,
    )
    head = repository.get_head(request.space_id)
    if (
        head is None
        or head.head_revision_id != request.expected_parent_revision_id
        or context.source_view.epoch != request.expected_source_authority_epoch
    ):
        _fail("source_publication_preview_stale")
    access = open_admitted_native_text(context, root.bindings[0].evidence_ref_id)
    if access.status != "available" or access.body_text is None:
        _fail("source_publication_source_inaccessible")
    # Registry collision checks remain transaction-owned; previews do not reserve.
    _, _, evidence, _, _ = _evidence_plan(
        repository,
        request,
        domain,
        profile,
        body=access.body_text.encode("utf8"),
        intervals=set(),
        strict=False,
        source_context=context,
    )
    return evidence


def publish_governed_native_source_publication(
    *,
    repository: NativeSourcePublicationRepository,
    request: GovernedNativeSourcePublicationV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    audience_labels: Sequence[str] = (),
) -> GovernedNativeSourcePublicationReceiptV1:
    request, domain, profile = snapshot_inputs(request, domain_contract, semantic_profile)
    if type(request) is not GovernedNativeSourcePublicationV1:
        _fail("source_publication_requires_governed_request")
    return repository.publish_governed_native_source_publication(
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
        audience_labels=tuple(audience_labels),
    )


def recover_governed_native_source_publication(
    *,
    repository: NativeSourcePublicationRepository,
    request: GovernedNativeSourcePublicationV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> GovernedNativeSourcePublicationReceiptV1 | None:
    """Privileged metadata only; host authorizes ownership BEFORE IO. Never retry."""
    request, domain, profile = snapshot_inputs(request, domain_contract, semantic_profile)
    if type(request) is not GovernedNativeSourcePublicationV1:
        _fail("source_publication_recovery_requires_governed_request")
    try:
        receipt = repository.get_native_source_publication_receipt(
            request.space_id, request.publication_id
        )
        pub = repository.get_publication_receipt(request.space_id, request.publication_id)
        if receipt is None:
            if pub is None:
                return None
            receipt = repository.get_native_source_publication_receipt(
                request.space_id, request.publication_id
            )
            if receipt is None:
                raise PersistenceIntegrityError("publication missing composed receipt")
        if receipt.intent_sha256 != publication_intent(request, domain, profile):
            _conflict(request)
        if pub is None or pub != receipt.publication_receipt:
            raise PersistenceIntegrityError("composed publication receipt drift")
        plan = _compose(
            repository, request, domain, profile, body=None, intervals=set(), strict=True
        )
        if receipt != make_receipt(request, plan, pub):
            raise PersistenceIntegrityError("composed immutable proof/results drift")
        _verify_receipt(
            pub, plan.command, publication_id=request.publication_id, repository=repository
        )
        return receipt.model_copy(deep=True)
    except (KnowledgePublicationIdempotencyConflictError, PersistenceIntegrityError):
        raise
    except Exception as exc:
        raise PersistenceIntegrityError("composed immutable reconstruction failed") from exc


def _support_reference(
    repository: NativeSourcePublicationRepository,
    source_revision_id: str,
    span_id: str,
    kind: Literal["admission", "extension", "publication"],
    receipt: NativeSourceAdmissionReceiptV1
    | NativeSourceEvidenceExtensionReceiptV1
    | GovernedNativeSourcePublicationReceiptV1,
    proofs: Sequence[NativeUtf8SpanProofV1],
) -> NativeSourcePublicationSupportRefV1 | None:
    """Decode one indexed immutable introduction; no body or mutable authorization."""
    if receipt.source_revision_id != source_revision_id:
        return None
    if (
        isinstance(receipt, GovernedNativeSourcePublicationReceiptV1)
        and receipt.mode != "new_intervals"
    ):
        raise PersistenceIntegrityError("reuse receipt is not an introduction")
    if not isinstance(receipt, NativeSourceAdmissionReceiptV1):
        source_revision, _, root = repository.get_native_source_publication_source(
            receipt.space_id, receipt.original_admission_id
        )
        if canonical_sha256(root.model_dump(mode="json")) != receipt.original_admission_sha256 or (
            root.source_artifact_id,
            source_revision.source_revision_id,
        ) != (receipt.source_artifact_id, source_revision_id):
            raise PersistenceIntegrityError("support lookup original source lineage drift")
    matches = [p for p in proofs if p.span_id == span_id]
    if len(matches) != 1:
        raise PersistenceIntegrityError("indexed source proof missing or ambiguous")
    proof = matches[0]
    pub = receipt.publication_receipt
    if repository.get_publication_receipt(receipt.space_id, pub.publication_id) != pub:
        raise PersistenceIntegrityError("support lookup publication receipt drift")
    child = repository.get_revision(receipt.space_id, pub.published_revision_id)
    if child is None or (child.revision.space_id, child.revision.revision_id) != (
        receipt.space_id,
        pub.published_revision_id,
    ):
        raise PersistenceIntegrityError("support lookup introducing child identity drift")
    # Repository get_revision owns ordinary envelope verification. Do not add
    # another whole-history hash pass to preparation.
    evidence = {
        e.evidence_ref_id: e for e in decode_native_graph_payload(child.graph_payload).evidence
    }.get(proof.evidence_ref_id)
    if evidence is None or (
        evidence.source_revision_id,
        evidence.source_artifact_id,
        evidence.source_span_ref_id,
    ) != (source_revision_id, receipt.source_artifact_id, span_id):
        raise PersistenceIntegrityError("support lookup introducing evidence drift")
    if evidence.evidence_role != "support":
        return None
    epoch = (
        receipt.source_authority_epoch_after
        if isinstance(receipt, GovernedNativeSourcePublicationReceiptV1)
        else receipt.source_authority_epoch
    )
    return NativeSourcePublicationSupportRefV1(
        evidence_ref_id=proof.evidence_ref_id,
        span_id=span_id,
        proof=proof,
        introducing_kind=kind,
        introducing_operation_id=pub.publication_id,
        introducing_receipt_sha256=canonical_sha256(receipt.model_dump(mode="json")),
        proof_authority_epoch=epoch,
    )


def get_native_source_publication_support(
    *,
    repository: NativeSourcePublicationRepository,
    space_id: str,
    source_revision_id: str,
    span_id: str,
) -> NativeSourcePublicationSupportRefV1 | None:
    """Privileged metadata lookup; host authorizes World ownership before IO.

    No current-source or citation authority is granted. Publication separately
    revalidates exact parent, selected evidence, current source and epoch.
    """
    if any(
        not isinstance(v, str) or not v.strip() for v in (space_id, source_revision_id, span_id)
    ):
        _fail("source_publication_support_lookup_identity_blank")
    try:
        result = repository.get_native_source_publication_support(
            space_id, source_revision_id, span_id
        )
        return (
            None
            if result is None
            else NativeSourcePublicationSupportRefV1.model_validate(result.model_dump(mode="json"))
        )
    except ValidationError as exc:
        raise PersistenceIntegrityError("support lookup persisted metadata invalid") from exc
