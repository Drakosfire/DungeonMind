"""Reopen a retained native PDF region before or after Graph publication."""

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256

from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.pdf_region import NativePdfRegionV1
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3, SourceRevisionV2

from .admission import _contract_visibility_visible
from .authority import revision_from_command
from .builder import build_parsed_knowledge_revision
from .materialization import NATIVE_VNEXT_GRAPH_SCHEMA, decode_native_graph_payload
from .ports import KnowledgeRevisionRepository
from .publication import _publish_validated_command


def open_native_pdf_region(
    region: NativePdfRegionV1,
    *,
    authorized_space_id: str,
    audience: frozenset[str],
    declared_labels: frozenset[str],
    load: Callable[[str, str], tuple[SourceArtifactV3, SourceRevisionV2, int, bytes] | None],
) -> bytes | None:
    """Use space and audience derived from the authenticated application context."""
    record = _verified_pdf_record(region, authorized_space_id, audience, declared_labels, load)
    return record[3] if record is not None else None


def _verified_pdf_record(
    region: NativePdfRegionV1,
    authorized_space_id: str,
    audience: frozenset[str],
    declared_labels: frozenset[str],
    load: Callable[[str, str], tuple[SourceArtifactV3, SourceRevisionV2, int, bytes] | None],
) -> tuple[SourceArtifactV3, SourceRevisionV2, int, bytes] | None:
    record = load(authorized_space_id, region.source_revision_id)
    if record is None:
        return None
    artifact, revision, page_count, body = record
    if artifact.status != "active" or not _contract_visibility_visible(
        artifact, audience=audience, declared_labels=declared_labels
    ):
        return None
    region.validate_source(revision, body=body, page_count=page_count)
    if revision.source_artifact_id != artifact.source_artifact_id:
        raise ValueError("PDF revision does not belong to the retained source artifact")
    return record


def bind_native_pdf_evidence(
    region: NativePdfRegionV1,
    *,
    authorized_space_id: str,
    audience: frozenset[str],
    declared_labels: frozenset[str],
    load: Callable[[str, str], tuple[SourceArtifactV3, SourceRevisionV2, int, bytes] | None],
) -> EvidenceRefV3 | None:
    """Construct supporting evidence for review from a verified retained PDF region."""
    record = _verified_pdf_record(region, authorized_space_id, audience, declared_labels, load)
    if record is None:
        return None
    artifact, revision, _, _ = record
    locator = region.model_dump_json()
    return EvidenceRefV3(
        evidence_ref_id=f"pdf-region:{sha256(locator.encode()).hexdigest()}",
        source_artifact_id=artifact.source_artifact_id,
        source_revision_id=revision.source_revision_id,
        evidence_role="support",
        can_open_source=True,
        can_highlight_span=True,
        source_locator=locator,
    )


def register_native_pdf_evidence(
    region: NativePdfRegionV1,
    *,
    authorized_space_id: str,
    audience: frozenset[str],
    declared_labels: frozenset[str],
    load: Callable[[str, str], tuple[SourceArtifactV3, SourceRevisionV2, int, bytes] | None],
    repository: KnowledgeRevisionRepository,
    expected_parent_revision_id: str,
    publication_id: str,
    created_at: datetime,
) -> tuple[EvidenceRefV3, KnowledgePublicationReceipt] | None:
    """Register only PDF evidence under the exact parent, without asserting a fact."""
    evidence = bind_native_pdf_evidence(
        region,
        authorized_space_id=authorized_space_id,
        audience=audience,
        declared_labels=declared_labels,
        load=load,
    )
    if evidence is None:
        return None
    if not publication_id.strip():
        raise ValueError("PDF evidence registration requires a publication ID")
    parent = repository.get_revision(authorized_space_id, expected_parent_revision_id)
    if parent is None or parent.revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        raise ValueError("PDF evidence registration requires a native Graph parent")
    payload = dict(parent.graph_payload)
    decoded = decode_native_graph_payload(payload)
    if any(item.evidence_ref_id == evidence.evidence_ref_id for item in decoded.evidence):
        raise ValueError("PDF evidence is already registered on the expected parent")
    payload["evidence"] = [*payload["evidence"], evidence.model_dump(mode="json")]
    command = PublishKnowledgeRevisionCommand(
        space_id=authorized_space_id,
        parent_revision_id=expected_parent_revision_id,
        expected_parent_revision_id=expected_parent_revision_id,
        operation_ids=[publication_id],
        graph_schema=NATIVE_VNEXT_GRAPH_SCHEMA,
        graph_payload=payload,
        domain_contract_ref=parent.revision.domain_contract_ref,
        semantic_profile_ref=parent.revision.semantic_profile_ref,
        migration_origin_ref=parent.revision.migration_origin_ref,
        created_at=created_at,
    )
    build_parsed_knowledge_revision(
        revision=revision_from_command(command),
        decoded_content=decode_native_graph_payload(command.graph_payload),
    )
    receipt = _publish_validated_command(
        command, publication_id=publication_id, repository=repository
    )
    return evidence, receipt
