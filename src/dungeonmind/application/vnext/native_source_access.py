"""Context-bound preview of admitted native UTF-8 source evidence."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from dungeonmind.contracts.vnext.domain import DomainContractDescriptor
from dungeonmind.contracts.vnext.native_source import NativeTextSourceAccessV1
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError

from .admission import _contract_visibility_visible
from .builder import build_parsed_knowledge_revision
from .errors import KnowledgeReadContextIntegrityError, NativeTextSourceAccessIntegrityError
from .materialization import NATIVE_VNEXT_GRAPH_SCHEMA, decode_native_graph_payload
from .model import ParsedKnowledgeRevision
from .ports import NativeSourceEvidenceRepository, NativeTextSourceView


@dataclass(frozen=True, slots=True)
class NativeTextSourceAccessContext:
    """Exact child membership, pinned source epoch and immutable visibility inputs."""

    space_id: str
    revision_id: str
    parsed: ParsedKnowledgeRevision
    source_view: NativeTextSourceView
    audience_labels: frozenset[str]
    declared_visibility_labels: frozenset[str]
    source_annotation_schemas: frozenset[str]


def open_native_text_source_access_context(
    *,
    repository: NativeSourceEvidenceRepository,
    space_id: str,
    revision_id: str,
    domain_contract: DomainContractDescriptor,
    audience_labels: Sequence[str] = (),
) -> NativeTextSourceAccessContext:
    """Pin one exact native revision and one coherent source-authority epoch."""
    if not space_id.strip() or not revision_id.strip():
        raise KnowledgeReadContextIntegrityError("native source context identity is blank")
    stored = repository.get_revision(space_id, revision_id)
    if stored is None:
        raise KnowledgeReadContextIntegrityError("native source context revision is missing")
    if stored.revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        raise KnowledgeReadContextIntegrityError("native source context is not a native revision")
    domain_snapshot = DomainContractDescriptor.model_validate(
        domain_contract.model_dump(mode="json")
    )
    if (
        domain_snapshot.domain_id != stored.revision.domain_contract_ref.domain_id
        or domain_snapshot.domain_revision != stored.revision.domain_contract_ref.domain_revision
        or canonical_sha256(domain_snapshot.model_dump(mode="json"))
        != stored.revision.domain_contract_ref.descriptor_sha256
    ):
        raise KnowledgeReadContextIntegrityError("native source context domain pin mismatch")
    parsed = build_parsed_knowledge_revision(
        revision=stored.revision,
        decoded_content=decode_native_graph_payload(stored.graph_payload),
    )
    view = repository.open_native_source_view(space_id)
    return NativeTextSourceAccessContext(
        space_id=space_id,
        revision_id=revision_id,
        parsed=parsed,
        source_view=view,
        audience_labels=frozenset(audience_labels),
        declared_visibility_labels=frozenset(domain_snapshot.visibility_labels),
        source_annotation_schemas=frozenset(domain_snapshot.source_annotation_schemas),
    )


def _unavailable() -> NativeTextSourceAccessV1:
    return NativeTextSourceAccessV1(status="unavailable")


def open_admitted_native_text(
    context: NativeTextSourceAccessContext,
    evidence_ref_id: str,
) -> NativeTextSourceAccessV1:
    """Return exact verified body bytes only through evidence in the pinned child."""
    if not isinstance(evidence_ref_id, str) or not evidence_ref_id.strip():
        return _unavailable()
    parsed = context.parsed
    evidence = parsed.get_evidence(evidence_ref_id)
    if evidence is None:
        return _unavailable()
    if (
        not evidence.can_open_source
        or not evidence.can_highlight_span
        or evidence.source_revision_id is None
        or evidence.source_span_ref_id is None
    ):
        return _unavailable()
    if any(
        item.schema_term not in context.source_annotation_schemas
        for item in evidence.domain_metadata
    ):
        return _unavailable()

    try:
        source = context.source_view.get_native_text_source(
            source_artifact_id=evidence.source_artifact_id,
            source_revision_id=evidence.source_revision_id,
            span_id=evidence.source_span_ref_id,
        )
    except PersistenceUnavailableError:
        raise
    except PersistenceIntegrityError as exc:
        raise NativeTextSourceAccessIntegrityError("source record integrity failed") from exc
    if source is None:
        return _unavailable()

    artifact = source.source_artifact
    revision = source.source_revision
    proof = source.span_proof
    if artifact.source_artifact_id != evidence.source_artifact_id:
        raise NativeTextSourceAccessIntegrityError("artifact identity mismatch")
    if artifact.status != "active" or artifact.current_revision_id != revision.source_revision_id:
        return _unavailable()
    if revision.source_artifact_id != artifact.source_artifact_id:
        raise NativeTextSourceAccessIntegrityError("revision artifact binding mismatch")
    if revision.source_revision_id != evidence.source_revision_id:
        raise NativeTextSourceAccessIntegrityError("revision identity mismatch")
    if revision.body_storage != "dm_native_utf8_body_v1":
        raise NativeTextSourceAccessIntegrityError("body storage kind mismatch")
    if proof.source_revision_id != revision.source_revision_id:
        raise NativeTextSourceAccessIntegrityError("span revision binding mismatch")
    if proof.evidence_ref_id != evidence_ref_id:
        raise NativeTextSourceAccessIntegrityError("span evidence binding mismatch")
    if proof.span_id != evidence.source_span_ref_id:
        raise NativeTextSourceAccessIntegrityError("span identity mismatch")
    if evidence.source_artifact_id != artifact.source_artifact_id:
        raise NativeTextSourceAccessIntegrityError("evidence artifact binding mismatch")
    if not _contract_visibility_visible(
        artifact,
        audience=context.audience_labels,
        declared_labels=context.declared_visibility_labels,
    ):
        return _unavailable()
    if any(
        item.schema_term not in context.source_annotation_schemas
        for item in artifact.domain_metadata
    ):
        return _unavailable()

    body = source.body_bytes
    body_digest = hashlib.sha256(body).hexdigest()
    if body_digest != revision.content_sha256:
        raise NativeTextSourceAccessIntegrityError("body digest mismatch")
    if proof.end_byte > len(body):
        raise NativeTextSourceAccessIntegrityError("span exceeds body bounds")
    selected = body[proof.start_byte : proof.end_byte]
    try:
        body_text = body.decode("utf-8", errors="strict")
        selected.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise NativeTextSourceAccessIntegrityError(
            "stored body or span is not valid UTF-8"
        ) from exc
    if hashlib.sha256(selected).hexdigest() != proof.slice_sha256:
        raise NativeTextSourceAccessIntegrityError("span digest mismatch")

    return NativeTextSourceAccessV1(
        status="available",
        evidence_ref_id=evidence_ref_id,
        source_artifact_id=artifact.source_artifact_id,
        source_revision_id=revision.source_revision_id,
        body_sha256=body_digest,
        body_text=body_text,
        span_start_byte=proof.start_byte,
        span_end_byte=proof.end_byte,
        span_sha256=proof.slice_sha256,
        source_authority_epoch=source.authority_epoch,
    )
