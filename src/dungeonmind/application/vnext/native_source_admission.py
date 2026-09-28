"""Atomic admission of immutable UTF-8 source bytes into native vNext authority."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, NoReturn

from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    DomainMetadataEntry,
    LabelsAllVisibility,
    LabelsAnyVisibility,
    PublicVisibility,
)
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    DomainContractRef,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
)
from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.native_source import (
    NATIVE_TEXT_BODY_STORAGE,
    NativeSourceAdmissionReceiptV1,
    NativeTextEvidenceSpanRequestV1,
    NativeTextSourceAdmissionBindingV1,
    NativeTextSourceAdmissionV1,
    NativeUtf8SpanProofV1,
)
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    ImmutableRevisionConflictError,
    PersistenceIntegrityError,
)

from .authority import revision_from_command
from .builder import build_parsed_knowledge_revision
from .errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationIntegrityError,
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
    NativeTextSourceAdmissionIntegrityError,
)
from .materialization import (
    NATIVE_VNEXT_GRAPH_SCHEMA,
    decode_native_graph_payload,
    encode_native_graph_payload,
)
from .ports import NativeSourceEvidenceRepository
from .publication import _verify_receipt
from .records import StoredKnowledgeRevision

_IDENTITY_SCHEMA = "dm_native_source_identity_v1"


@dataclass(frozen=True, slots=True)
class NativeSourceWriteParts:
    """Deterministic source identities constructed from one admission request."""

    artifact: SourceArtifactV3
    revision: SourceRevisionV2
    evidence: tuple[EvidenceRefV3, ...]
    span_proofs: tuple[NativeUtf8SpanProofV1, ...]
    body_bytes: bytes


def _fail(reason: str) -> NoReturn:
    raise NativeTextSourceAdmissionIntegrityError(reason) from None


def allocate_native_source_id(
    *,
    space_id: str,
    admission_id: str,
    identity_kind: Literal["artifact", "revision", "span", "evidence"],
    client_ref: str,
) -> str:
    """Allocate one deterministic ID from the complete space/admission/kind/ref key."""
    if not all(value.strip() for value in (space_id, admission_id, client_ref)):
        _fail("allocation_identity_blank")
    digest = canonical_sha256(
        {
            "schema": _IDENTITY_SCHEMA,
            "space_id": space_id,
            "admission_id": admission_id,
            "identity_kind": identity_kind,
            "client_ref": client_ref,
        }
    )
    prefix = {
        "artifact": "src",
        "revision": "srev",
        "span": "span",
        "evidence": "ev",
    }[identity_kind]
    return f"{prefix}:{digest}"


def native_source_command_sha256(
    *,
    request: NativeTextSourceAdmissionV1,
    command: PublishKnowledgeRevisionCommand,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> str:
    """Fingerprint every input that can affect durable source or child authority."""
    return canonical_sha256(
        {
            "request": request.model_dump(mode="json"),
            "domain_contract": domain_contract.model_dump(mode="json"),
            "semantic_profile": semantic_profile.model_dump(mode="json"),
            "publication_command": command.model_dump(mode="json"),
        }
    )


def _descriptor_refs(
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> tuple[DomainContractRef, SemanticProfileRef]:
    return (
        DomainContractRef(
            domain_id=domain_contract.domain_id,
            domain_revision=domain_contract.domain_revision,
            descriptor_sha256=canonical_sha256(domain_contract.model_dump(mode="json")),
        ),
        SemanticProfileRef(
            profile_id=semantic_profile.profile_id,
            profile_revision=semantic_profile.profile_revision,
            descriptor_sha256=canonical_sha256(semantic_profile.model_dump(mode="json")),
        ),
    )


def _metadata_declared(
    entries: Sequence[DomainMetadataEntry],
    *,
    declared: frozenset[str],
) -> bool:
    return all(entry.schema_term in declared for entry in entries)


def _visibility_declared(artifact: SourceArtifactV3, *, declared: frozenset[str]) -> bool:
    visibility = artifact.visibility
    if isinstance(visibility, PublicVisibility):
        return True
    if isinstance(visibility, (LabelsAnyVisibility, LabelsAllVisibility)):
        return set(visibility.labels).issubset(declared)
    return False


def _span_slice(body: bytes, span: NativeTextEvidenceSpanRequestV1) -> bytes:
    if span.end_byte > len(body):
        _fail("span_out_of_bounds")
    selected = body[span.start_byte : span.end_byte]
    try:
        selected.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _fail("span_not_utf8_aligned")
    return selected


def build_native_source_write_parts(
    *, request: NativeTextSourceAdmissionV1
) -> NativeSourceWriteParts:
    """Build exact immutable artifact/revision/evidence values without side effects."""
    try:
        body = request.body_text.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        _fail("body_not_valid_utf8")
    body_sha256 = hashlib.sha256(body).hexdigest()
    if body_sha256 != request.expected_body_sha256:
        _fail("body_digest_mismatch")

    artifact_id = allocate_native_source_id(
        space_id=request.space_id,
        admission_id=request.admission_id,
        identity_kind="artifact",
        client_ref="source",
    )
    revision_id = allocate_native_source_id(
        space_id=request.space_id,
        admission_id=request.admission_id,
        identity_kind="revision",
        client_ref="source",
    )
    artifact = SourceArtifactV3(
        source_artifact_id=artifact_id,
        source_classification=request.source_classification,
        current_revision_id=revision_id,
        authority=request.authority,
        visibility=request.visibility.model_copy(deep=True),
        status="active",
        uri=None,
        foreign_refs=list(request.foreign_refs),
        domain_metadata=[item.model_copy(deep=True) for item in request.domain_metadata],
        created_at=request.created_at,
        updated_at=request.created_at,
    )
    revision = SourceRevisionV2(
        source_revision_id=revision_id,
        source_artifact_id=artifact_id,
        content_sha256=body_sha256,
        body_storage=NATIVE_TEXT_BODY_STORAGE,
        locator=None,
        created_at=request.created_at,
    )

    evidence: list[EvidenceRefV3] = []
    proofs: list[NativeUtf8SpanProofV1] = []
    for span in request.spans:
        selected = _span_slice(body, span)
        slice_sha256 = hashlib.sha256(selected).hexdigest()
        if slice_sha256 != span.expected_slice_sha256:
            _fail("span_digest_mismatch")
        span_id = allocate_native_source_id(
            space_id=request.space_id,
            admission_id=request.admission_id,
            identity_kind="span",
            client_ref=span.client_ref,
        )
        evidence_id = allocate_native_source_id(
            space_id=request.space_id,
            admission_id=request.admission_id,
            identity_kind="evidence",
            client_ref=span.client_ref,
        )
        evidence.append(
            EvidenceRefV3(
                evidence_ref_id=evidence_id,
                source_artifact_id=artifact_id,
                source_revision_id=revision_id,
                evidence_role=span.evidence_role,
                can_open_source=True,
                can_highlight_span=True,
                locator=None,
                uri=None,
                source_locator=None,
                line_ref=None,
                source_span_ref_id=span_id,
                domain_metadata=[item.model_copy(deep=True) for item in span.domain_metadata],
            )
        )
        proofs.append(
            NativeUtf8SpanProofV1(
                span_id=span_id,
                source_revision_id=revision_id,
                evidence_ref_id=evidence_id,
                start_byte=span.start_byte,
                end_byte=span.end_byte,
                slice_sha256=slice_sha256,
            )
        )
    return NativeSourceWriteParts(
        artifact=artifact,
        revision=revision,
        evidence=tuple(evidence),
        span_proofs=tuple(proofs),
        body_bytes=body,
    )


def validate_native_source_write(
    *,
    request: NativeTextSourceAdmissionV1,
    command: PublishKnowledgeRevisionCommand,
    command_sha256: str,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    source_artifact: SourceArtifactV3,
    source_revision: SourceRevisionV2,
    body_bytes: bytes,
    span_proofs: Sequence[NativeUtf8SpanProofV1],
    parent: StoredKnowledgeRevision,
) -> NativeSourceWriteParts:
    """Recompute every durable binding at both application and repository edges."""
    parts = build_native_source_write_parts(request=request)
    if command.space_id != request.space_id:
        _fail("command_space_mismatch")
    if (
        command.parent_revision_id != request.expected_parent_revision_id
        or command.expected_parent_revision_id != request.expected_parent_revision_id
    ):
        _fail("expected_parent_mismatch")
    if command.operation_ids != [request.admission_id]:
        _fail("operation_identity_mismatch")
    if command.created_at != request.created_at:
        _fail("created_at_mismatch")
    if command.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        _fail("graph_schema_not_native")
    if parent.revision.space_id != request.space_id:
        _fail("parent_space_mismatch")
    if parent.revision.revision_id != request.expected_parent_revision_id:
        _fail("parent_revision_mismatch")
    if parent.revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        _fail("parent_graph_schema_not_native")
    domain_ref, profile_ref = _descriptor_refs(domain_contract, semantic_profile)
    if command.domain_contract_ref != parent.revision.domain_contract_ref or (
        command.semantic_profile_ref != parent.revision.semantic_profile_ref
    ):
        _fail("child_descriptor_ref_drift")
    if command.domain_contract_ref != domain_ref or command.semantic_profile_ref != profile_ref:
        _fail("descriptor_snapshot_mismatch")
    if command.migration_origin_ref != parent.revision.migration_origin_ref:
        _fail("migration_origin_drift")

    declared_source_schemas = frozenset(domain_contract.source_annotation_schemas)
    if not _metadata_declared(parts.artifact.domain_metadata, declared=declared_source_schemas):
        _fail("artifact_source_annotation_undeclared")
    if not _visibility_declared(
        parts.artifact, declared=frozenset(domain_contract.visibility_labels)
    ):
        _fail("artifact_visibility_undeclared")
    for item in parts.evidence:
        if not _metadata_declared(item.domain_metadata, declared=declared_source_schemas):
            _fail("evidence_source_annotation_undeclared")

    if source_artifact != parts.artifact:
        _fail("source_artifact_binding_mismatch")
    if source_revision != parts.revision:
        _fail("source_revision_binding_mismatch")
    if bytes(body_bytes) != parts.body_bytes:
        _fail("body_bytes_binding_mismatch")
    if tuple(span_proofs) != parts.span_proofs:
        _fail("span_proof_binding_mismatch")
    expected_command_sha = native_source_command_sha256(
        request=request,
        command=command,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
    )
    if command_sha256 != expected_command_sha:
        _fail("command_fingerprint_mismatch")

    try:
        parent_content = decode_native_graph_payload(parent.graph_payload)
        child_content = decode_native_graph_payload(command.graph_payload)
    except Exception:
        _fail("native_payload_invalid")
    if {item.entity_id: item for item in child_content.entities} != {
        item.entity_id: item for item in parent_content.entities
    }:
        _fail("entity_content_changed")
    if {item.assertion_id: item for item in child_content.assertions} != {
        item.assertion_id: item for item in parent_content.assertions
    }:
        _fail("assertion_content_changed")
    if {item.alias_id: item for item in child_content.aliases} != {
        item.alias_id: item for item in parent_content.aliases
    }:
        _fail("alias_content_changed")
    parent_evidence = {item.evidence_ref_id: item for item in parent_content.evidence}
    expected_evidence = {item.evidence_ref_id: item for item in parts.evidence}
    child_evidence = {item.evidence_ref_id: item for item in child_content.evidence}
    if len(parent_evidence) != len(parent_content.evidence):
        _fail("parent_evidence_duplicate")
    if len(expected_evidence) != len(parts.evidence):
        _fail("allocated_evidence_collision")
    if set(parent_evidence) & set(expected_evidence):
        _fail("allocated_evidence_present_in_parent")
    if child_evidence != parent_evidence | expected_evidence:
        _fail("child_evidence_membership_mismatch")
    return parts


def _build_command(
    *,
    request: NativeTextSourceAdmissionV1,
    parent: StoredKnowledgeRevision,
    parts: NativeSourceWriteParts,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> PublishKnowledgeRevisionCommand:
    parent_content = decode_native_graph_payload(parent.graph_payload)
    entities = {item.entity_id: item for item in parent_content.entities}
    assertions = {item.assertion_id: item for item in parent_content.assertions}
    aliases = {item.alias_id: item for item in parent_content.aliases}
    evidence = {item.evidence_ref_id: item for item in parent_content.evidence}
    for item in parts.evidence:
        if item.evidence_ref_id in evidence:
            _fail("allocated_evidence_present_in_parent")
        evidence[item.evidence_ref_id] = item
    domain_ref, profile_ref = _descriptor_refs(domain_contract, semantic_profile)
    return PublishKnowledgeRevisionCommand(
        space_id=request.space_id,
        parent_revision_id=request.expected_parent_revision_id,
        expected_parent_revision_id=request.expected_parent_revision_id,
        operation_ids=[request.admission_id],
        graph_schema=NATIVE_VNEXT_GRAPH_SCHEMA,
        graph_payload=encode_native_graph_payload(
            entities=entities,
            assertions=assertions,
            aliases=aliases,
            evidence=evidence,
        ),
        domain_contract_ref=domain_ref,
        semantic_profile_ref=profile_ref,
        migration_origin_ref=parent.revision.migration_origin_ref,
        created_at=request.created_at,
    )


def _verify_admission_receipt(
    *,
    receipt: NativeSourceAdmissionReceiptV1,
    request: NativeTextSourceAdmissionV1,
    command: PublishKnowledgeRevisionCommand,
    command_sha256: str,
    parts: NativeSourceWriteParts,
    repository: NativeSourceEvidenceRepository,
) -> NativeSourceAdmissionReceiptV1:
    if receipt.space_id != request.space_id or receipt.admission_id != request.admission_id:
        raise PersistenceIntegrityError("native source admission receipt identity drift")
    if receipt.command_sha256 != command_sha256:
        raise KnowledgePublicationIdempotencyConflictError(
            space_id=request.space_id,
            publication_id=request.admission_id,
        )
    if receipt.source_artifact_id != parts.artifact.source_artifact_id:
        raise PersistenceIntegrityError("native source artifact receipt drift")
    if receipt.source_revision_id != parts.revision.source_revision_id:
        raise PersistenceIntegrityError("native source revision receipt drift")
    if receipt.origin != request.origin:
        raise PersistenceIntegrityError("native source origin receipt drift")
    if receipt.bindings != [
        NativeTextSourceAdmissionBindingV1(
            client_ref=span.client_ref,
            span_id=proof.span_id,
            evidence_ref_id=proof.evidence_ref_id,
        )
        for span, proof in zip(request.spans, parts.span_proofs, strict=True)
    ]:
        raise PersistenceIntegrityError("native source span receipt drift")
    _verify_receipt(
        receipt.publication_receipt,
        command,
        publication_id=request.admission_id,
        repository=repository,
    )
    child = repository.get_revision(request.space_id, receipt.published_revision_id)
    if child is None:
        raise PersistenceIntegrityError("native source receipt references missing child")
    parsed = build_parsed_knowledge_revision(
        revision=child.revision,
        decoded_content=decode_native_graph_payload(child.graph_payload),
    )
    view = repository.open_native_source_view(request.space_id)
    if receipt.source_authority_epoch > view.epoch:
        raise PersistenceIntegrityError("native source receipt epoch is ahead of the store")
    for proof in parts.span_proofs:
        evidence = parsed.get_evidence(proof.evidence_ref_id)
        if evidence is None or evidence.source_artifact_id != receipt.source_artifact_id:
            raise PersistenceIntegrityError("native source receipt evidence membership drift")
        source = view.get_native_text_source(
            source_artifact_id=receipt.source_artifact_id,
            source_revision_id=receipt.source_revision_id,
            span_id=proof.span_id,
        )
        if source is None:
            raise PersistenceIntegrityError("native source receipt references missing source")
        if (
            source.authority_epoch != receipt.source_authority_epoch
            or source.source_artifact != parts.artifact
            or source.source_revision != parts.revision
            or source.body_bytes != parts.body_bytes
            or source.span_proof != proof
        ):
            raise PersistenceIntegrityError("native source receipt source binding drift")
    return receipt


def publish_native_text_source_evidence(
    *,
    repository: NativeSourceEvidenceRepository,
    request: NativeTextSourceAdmissionV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> NativeSourceAdmissionReceiptV1:
    """Atomically admit one immutable UTF-8 source and its evidence in a native child."""
    try:
        request_snapshot = NativeTextSourceAdmissionV1.model_validate(
            request.model_dump(mode="json")
        )
        domain_snapshot = DomainContractDescriptor.model_validate(
            domain_contract.model_dump(mode="json")
        )
        profile_type = type(semantic_profile)
        if profile_type not in (SemanticProfileDescriptorV2, SemanticProfileDescriptorV3):
            _fail("semantic_profile_type_invalid")
        profile_snapshot = profile_type.model_validate(semantic_profile.model_dump(mode="json"))
    except NativeTextSourceAdmissionIntegrityError:
        raise
    except Exception as exc:
        raise NativeTextSourceAdmissionIntegrityError("request_snapshot_invalid") from exc

    request = request_snapshot
    parent = repository.get_revision(request.space_id, request.expected_parent_revision_id)
    if parent is None:
        raise NativeTextSourceAdmissionIntegrityError("expected_parent_missing")

    parts = build_native_source_write_parts(request=request)
    command = _build_command(
        request=request,
        parent=parent,
        parts=parts,
        domain_contract=domain_snapshot,
        semantic_profile=profile_snapshot,
    )
    parsed_parent = build_parsed_knowledge_revision(
        revision=parent.revision,
        decoded_content=decode_native_graph_payload(parent.graph_payload),
    )
    parsed_child = build_parsed_knowledge_revision(
        revision=revision_from_command(command),
        decoded_content=decode_native_graph_payload(command.graph_payload),
    )
    if (
        parsed_child.entities_by_id != parsed_parent.entities_by_id
        or parsed_child.assertions_by_id != parsed_parent.assertions_by_id
        or parsed_child.aliases_by_id != parsed_parent.aliases_by_id
    ):
        raise NativeTextSourceAdmissionIntegrityError("child_changed_non_evidence_content")
    command_sha = native_source_command_sha256(
        request=request,
        command=command,
        domain_contract=domain_snapshot,
        semantic_profile=profile_snapshot,
    )
    prior = repository.get_native_source_admission_receipt(request.space_id, request.admission_id)
    if prior is not None:
        if prior.command_sha256 != command_sha:
            raise KnowledgePublicationIdempotencyConflictError(
                space_id=request.space_id,
                publication_id=request.admission_id,
            )
        return _verify_admission_receipt(
            receipt=prior,
            request=request,
            command=command,
            command_sha256=command_sha,
            parts=parts,
            repository=repository,
        )
    if repository.get_publication_receipt(request.space_id, request.admission_id) is not None:
        raise KnowledgePublicationIdempotencyConflictError(
            space_id=request.space_id,
            publication_id=request.admission_id,
        )

    head = repository.get_head(request.space_id)
    actual_head_id = None if head is None else head.head_revision_id
    if actual_head_id != request.expected_parent_revision_id:
        raise KnowledgeStaleParentRevisionError(
            space_id=request.space_id,
            expected_parent_revision_id=request.expected_parent_revision_id,
            actual_head_revision_id=actual_head_id,
        )
    validate_native_source_write(
        request=request,
        command=command,
        command_sha256=command_sha,
        domain_contract=domain_snapshot,
        semantic_profile=profile_snapshot,
        source_artifact=parts.artifact,
        source_revision=parts.revision,
        body_bytes=parts.body_bytes,
        span_proofs=parts.span_proofs,
        parent=parent,
    )
    try:
        receipt = repository.publish_native_text_source_evidence(
            request=request,
            command=command,
            command_sha256=command_sha,
            domain_contract=domain_snapshot,
            semantic_profile=profile_snapshot,
            source_artifact=parts.artifact,
            source_revision=parts.revision,
            body_bytes=parts.body_bytes,
            span_proofs=parts.span_proofs,
        )
    except (
        KnowledgePublicationIdempotencyConflictError,
        KnowledgeStaleParentRevisionError,
        KnowledgePublicationIntegrityError,
        NativeTextSourceAdmissionIntegrityError,
        PersistenceIntegrityError,
        ImmutableRevisionConflictError,
    ):
        raise
    except Exception as exc:
        try:
            recovered = repository.get_native_source_admission_receipt(
                request.space_id, request.admission_id
            )
        except PersistenceIntegrityError:
            raise
        except Exception as probe_exc:
            raise KnowledgePublicationOutcomeUnknownError(
                space_id=request.space_id,
                publication_id=request.admission_id,
                expected_published_revision_id=revision_from_command(command).revision_id,
                reason=f"publish={type(exc).__name__}; probe={type(probe_exc).__name__}",
            ) from exc
        if recovered is None:
            raise KnowledgePublicationOutcomeUnknownError(
                space_id=request.space_id,
                publication_id=request.admission_id,
                expected_published_revision_id=revision_from_command(command).revision_id,
                reason=f"publish={type(exc).__name__}; receipt=missing",
            ) from exc
        return _verify_admission_receipt(
            receipt=recovered,
            request=request,
            command=command,
            command_sha256=command_sha,
            parts=parts,
            repository=repository,
        )
    return _verify_admission_receipt(
        receipt=receipt,
        request=request,
        command=command,
        command_sha256=command_sha,
        parts=parts,
        repository=repository,
    )
