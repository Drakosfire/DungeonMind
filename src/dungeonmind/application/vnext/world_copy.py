"""Copy a pinned native World into a separately allocated native space.

This is an application boundary, not an authorization or product API: the
caller must authorize the source, keep an incomplete destination private, and
choose a unique durable operation identity for each destination.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
)
from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.native_source import (
    MAX_NATIVE_TEXT_SPANS,
    NativeTextEvidenceSpanRequestV1,
    NativeTextSourceAdmissionV1,
    NativeTextSourceOriginV1,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .admission import visibility_visible
from .authority import revision_from_command
from .builder import build_parsed_knowledge_revision
from .materialization import NATIVE_VNEXT_GRAPH_SCHEMA, decode_native_graph_payload
from .native_source_access import open_admitted_native_text, open_native_text_source_access_context
from .native_source_admission import publish_native_text_source_evidence
from .ports import NativeSourceEvidenceRepository
from .publication import _publish_validated_command, get_publication_receipt
from .records import StoredKnowledgeRevision
from .space_provisioning import create_empty_space


class NativeWorldCopyError(ValueError):
    """A snapshot cannot be copied without losing authority or fidelity."""


@dataclass(frozen=True, slots=True)
class NativeWorldCopyResult:
    space_id: str
    revision_id: str
    source_space_id: str
    source_revision_id: str
    binding_sha256: str


def _source_material(
    repository: NativeSourceEvidenceRepository,
    source_space_id: str,
    source_revision_id: str,
    domain_contract: DomainContractDescriptor,
    audience_labels: Sequence[str],
) -> tuple[StoredKnowledgeRevision, dict[str, Any], dict[tuple[str, str], Any]]:
    context = open_native_text_source_access_context(
        repository=repository,
        space_id=source_space_id,
        revision_id=source_revision_id,
        domain_contract=domain_contract,
        audience_labels=audience_labels,
    )
    stored = repository.get_revision(source_space_id, source_revision_id)
    if stored is None or stored.revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        raise NativeWorldCopyError("source revision unavailable")
    graph = copy.deepcopy(stored.graph_payload)
    if any(
        not visibility_visible(
            assertion.metadata.visibility,
            audience=context.audience_labels,
            declared_labels=context.declared_visibility_labels,
        )
        for assertion in context.parsed.assertions_by_id.values()
    ):
        raise NativeWorldCopyError(
            "source graph contains assertions outside the authorized audience"
        )
    groups = {}
    with context.source_view.read_scope() as view:
        scoped = replace(context, source_view=view)
        for evidence in graph["evidence"]:
            evidence_id = evidence["evidence_ref_id"]
            # Native text admission cannot reproduce opaque external locators.
            if any(evidence.get(key) for key in ("locator", "uri", "source_locator", "line_ref")):
                raise NativeWorldCopyError("source evidence contains unsupported locators")
            if (
                not evidence.get("can_open_source")
                or not evidence.get("can_highlight_span")
                or not evidence.get("source_span_ref_id")
            ):
                raise NativeWorldCopyError("source evidence is not an openable native text span")
            opened = open_admitted_native_text(scoped, evidence_id)
            if opened.status != "available":
                raise NativeWorldCopyError(
                    "source evidence is unavailable to the authorized audience"
                )
            native = view.get_native_text_source(
                source_artifact_id=evidence["source_artifact_id"],
                source_revision_id=evidence["source_revision_id"],
                span_id=evidence["source_span_ref_id"],
            )
            if native is None or native.source_artifact.status != "active":
                raise NativeWorldCopyError("source text is unavailable")
            if native.source_artifact.uri or native.source_revision.locator:
                raise NativeWorldCopyError("source contains unsupported external locators")
            if native.body_bytes != opened.body_text.encode("utf-8"):
                raise NativeWorldCopyError("source body differs from verified evidence")
            key = (evidence["source_artifact_id"], evidence["source_revision_id"])
            snapshot = view.get_native_metadata_snapshot(
                artifact_ids=[key[0]], revision_ids=[key[1]]
            )
            origin = snapshot.get_origin(*key)
            if origin is None:
                origin = NativeTextSourceOriginV1(
                    namespace="dungeonmind.native-copy", object_id=key[0], revision_id=key[1]
                )
            group = groups.setdefault(key, {"native": native, "origin": origin, "spans": []})
            previous = group["native"]
            if (
                previous.body_bytes != native.body_bytes
                or previous.source_artifact != native.source_artifact
                or previous.source_revision != native.source_revision
                or group["origin"] != origin
            ):
                raise NativeWorldCopyError("source revision is inconsistent")
            group["spans"].append(
                NativeTextEvidenceSpanRequestV1(
                    client_ref=evidence_id,
                    evidence_role=evidence["evidence_role"],
                    start_byte=opened.span_start_byte,
                    end_byte=opened.span_end_byte,
                    expected_slice_sha256=opened.span_sha256,
                    domain_metadata=evidence.get("domain_metadata", []),
                )
            )
    if any(len(group["spans"]) > MAX_NATIVE_TEXT_SPANS for group in groups.values()):
        raise NativeWorldCopyError("source has too many spans for one native admission")
    return stored, graph, groups


def _check_profile(
    source: StoredKnowledgeRevision,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> None:
    ref = source.revision.semantic_profile_ref
    if (
        ref.profile_id != semantic_profile.profile_id
        or ref.profile_revision != semantic_profile.profile_revision
        or ref.descriptor_sha256 != canonical_sha256(semantic_profile.model_dump(mode="json"))
    ):
        raise NativeWorldCopyError("source semantic profile differs")


def _command(
    space_id: str,
    parent: StoredKnowledgeRevision,
    payload: dict[str, Any],
    operation_id: str,
    created_at: datetime,
) -> PublishKnowledgeRevisionCommand:
    command = PublishKnowledgeRevisionCommand(
        space_id=space_id,
        parent_revision_id=parent.revision.revision_id,
        expected_parent_revision_id=parent.revision.revision_id,
        operation_ids=[operation_id],
        graph_schema=NATIVE_VNEXT_GRAPH_SCHEMA,
        graph_payload=payload,
        domain_contract_ref=parent.revision.domain_contract_ref,
        semantic_profile_ref=parent.revision.semantic_profile_ref,
        migration_origin_ref=None,
        created_at=created_at,
    )
    build_parsed_knowledge_revision(
        revision=revision_from_command(command),
        decoded_content=decode_native_graph_payload(payload),
    )
    return command


def copy_native_world(
    *,
    repository: NativeSourceEvidenceRepository,
    operation_id: str,
    source_space_id: str,
    source_revision_id: str,
    created_at: datetime,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    audience_labels: Sequence[str] = (),
) -> NativeWorldCopyResult:
    """Copy all supported source records and return the isolated baseline revision.

    The same operation ID and exact inputs replay to the same result. The caller
    must keep the destination private until this method succeeds. Unsupported or
    inaccessible source evidence fails closed; it is never omitted.
    """
    if any(
        not isinstance(v, str) or not v.strip() or v != v.strip()
        for v in (operation_id, source_space_id, source_revision_id)
    ):
        raise NativeWorldCopyError("exact operation and source identities are required")
    if created_at.utcoffset() is None:
        raise NativeWorldCopyError("copy time must be timezone-aware")
    if any(not isinstance(v, str) or not v.strip() or v != v.strip() for v in audience_labels):
        raise NativeWorldCopyError("invalid audience labels")
    labels = tuple(sorted(set(audience_labels)))
    binding = canonical_sha256(
        {
            "source_space_id": source_space_id,
            "source_revision_id": source_revision_id,
            "created_at": created_at.isoformat(),
            "domain": domain_contract.model_dump(mode="json"),
            "profile": semantic_profile.model_dump(mode="json"),
            "audience_labels": labels,
        }
    )
    allocation = f"native-world-copy:{operation_id}"
    get_allocation = getattr(repository, "get_space_provisioning_receipt", None)
    if not callable(get_allocation):
        raise NativeWorldCopyError("repository does not support allocation recovery")
    existing = get_allocation(allocation)
    material = None
    if existing is None:
        material = _source_material(
            repository, source_space_id, source_revision_id, domain_contract, labels
        )
        _check_profile(material[0], semantic_profile)
    genesis = create_empty_space(
        repository=repository,
        allocation_id=allocation,
        created_at=created_at,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
    )
    target = genesis.space_id
    if target == source_space_id:
        raise PersistenceIntegrityError("copy destination equals source")
    initial = repository.get_revision(target, genesis.publication_receipt.published_revision_id)
    if initial is None:
        raise PersistenceIntegrityError("copy genesis unavailable")
    bind = _command(
        target, initial, initial.graph_payload, f"native-copy-binding:{binding}", created_at
    )
    bound = _publish_validated_command(
        bind, publication_id="native-copy-binding", repository=repository
    )
    complete = get_publication_receipt(target, "native-copy-complete", repository=repository)
    if complete is not None:
        result = repository.get_revision(target, complete.published_revision_id)
        if result is None or result.revision.operation_ids != [f"native-copy-graph:{binding}"]:
            raise PersistenceIntegrityError("copy completion binding differs")
        return NativeWorldCopyResult(
            target, complete.published_revision_id, source_space_id, source_revision_id, binding
        )
    if material is None:
        material = _source_material(
            repository, source_space_id, source_revision_id, domain_contract, labels
        )
    source, graph, groups = material
    _check_profile(source, semantic_profile)
    evidence_map = {}
    parent_id = bound.published_revision_id
    for key in sorted(groups):
        group = groups[key]
        native = group["native"]
        artifact = native.source_artifact
        source_binding = canonical_sha256(
            {"binding": binding, "artifact": key[0], "revision": key[1]}
        )
        admission_id = f"native-copy-source:{source_binding}"
        request = NativeTextSourceAdmissionV1(
            space_id=target,
            admission_id=admission_id,
            expected_parent_revision_id=parent_id,
            created_at=created_at,
            body_text=native.body_bytes.decode("utf-8"),
            expected_body_sha256=hashlib.sha256(native.body_bytes).hexdigest(),
            source_classification=artifact.source_classification,
            authority=artifact.authority,
            visibility=artifact.visibility,
            foreign_refs=artifact.foreign_refs,
            domain_metadata=artifact.domain_metadata,
            origin=group["origin"],
            spans=group["spans"],
        )
        receipt = publish_native_text_source_evidence(
            repository=repository,
            request=request,
            domain_contract=domain_contract,
            semantic_profile=semantic_profile,
        )
        for item in receipt.bindings:
            if item.client_ref in evidence_map:
                raise PersistenceIntegrityError("duplicate copied evidence binding")
            evidence_map[item.client_ref] = item.evidence_ref_id
        parent_id = receipt.published_revision_id
    expected = {item["evidence_ref_id"] for item in graph["evidence"]}
    if set(evidence_map) != expected:
        raise PersistenceIntegrityError("copied evidence is incomplete")
    for assertion in graph["assertions"]:
        assertion["metadata"]["evidence_ref_ids"] = [
            evidence_map[x] for x in assertion["metadata"]["evidence_ref_ids"]
        ]
    for alias in graph["aliases"]:
        alias["evidence_ref_ids"] = [evidence_map[x] for x in alias["evidence_ref_ids"]]
    parent = repository.get_revision(target, parent_id)
    if parent is None:
        raise PersistenceIntegrityError("copied source parent unavailable")
    graph["evidence"] = parent.graph_payload["evidence"]
    command = _command(target, parent, graph, f"native-copy-graph:{binding}", created_at)
    receipt = _publish_validated_command(
        command, publication_id="native-copy-complete", repository=repository
    )
    return NativeWorldCopyResult(
        target, receipt.published_revision_id, source_space_id, source_revision_id, binding
    )
