"""Context-bound preview of admitted native UTF-8 source evidence."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import cast

from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, DomainContractRef
from dungeonmind.contracts.vnext.native_source import (
    NativeTextSourceAccessV1,
    NativeTextSourceOriginV1,
)
from dungeonmind.contracts.vnext.source import SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError

from .admission import _contract_visibility_visible
from .builder import build_parsed_knowledge_revision
from .errors import KnowledgeReadContextIntegrityError, NativeTextSourceAccessIntegrityError
from .materialization import NATIVE_VNEXT_GRAPH_SCHEMA, decode_native_graph_payload
from .model import ParsedKnowledgeRevision
from .ports import NativeSourceEvidenceRepository, NativeTextSourceView
from .records import ParsedEvidenceRef


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
    domain_contract: (
        DomainContractDescriptor
        | Callable[[DomainContractRef, SemanticProfileRef], DomainContractDescriptor]
    ),
    audience_labels: Sequence[str] = (),
) -> NativeTextSourceAccessContext:
    """Pin one exact native revision and one coherent source-authority epoch.

    A descriptor resolver receives both descriptor references from the loaded revision.
    Both descriptor forms undergo the same pin validation.
    """
    if not space_id.strip() or not revision_id.strip():
        raise KnowledgeReadContextIntegrityError("native source context identity is blank")
    stored = repository.get_revision(space_id, revision_id)
    if stored is None:
        raise KnowledgeReadContextIntegrityError("native source context revision is missing")
    if stored.revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        raise KnowledgeReadContextIntegrityError("native source context is not a native revision")
    if callable(domain_contract):
        domain_contract = domain_contract(
            stored.revision.domain_contract_ref, stored.revision.semantic_profile_ref
        )
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


def refresh_native_text_source_access_context(
    *,
    repository: NativeSourceEvidenceRepository,
    context: NativeTextSourceAccessContext,
) -> NativeTextSourceAccessContext:
    """Refresh source authority without reloading immutable Graph membership.

    The repository must be the authority that opened the original context. The
    exact parsed revision and its audience/domain inputs remain pinned; only
    the source view advances. Body reads still perform normal admission checks.
    """
    identity = context.parsed.identity
    if (
        not context.space_id.strip()
        or not context.revision_id.strip()
        or identity.space_id != context.space_id
        or identity.revision_id != context.revision_id
        or identity.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA
    ):
        raise KnowledgeReadContextIntegrityError("native source context identity mismatch")
    view = repository.open_native_source_view(context.space_id)
    if view.epoch < context.source_view.epoch:
        raise KnowledgeReadContextIntegrityError("native source authority epoch moved backwards")
    return replace(context, source_view=view)


@dataclass(frozen=True, slots=True)
class NativeTextSourceMetadata:
    """Authorized navigation metadata, not a body/span verification receipt."""

    source_artifact: SourceArtifactV3
    source_revision: SourceRevisionV2
    evidence_ref_ids: tuple[str, ...]
    origin: NativeTextSourceOriginV1 | None


@dataclass(frozen=True, slots=True)
class NativeTextSourceCatalog:
    """All eligible metadata in one pinned source context, without reading bodies."""

    space_id: str
    revision_id: str
    source_authority_epoch: int
    sources: tuple[NativeTextSourceMetadata, ...]
    complete: bool


def _eligible_evidence(
    context: NativeTextSourceAccessContext,
    evidence: ParsedEvidenceRef,
) -> bool:
    return (
        evidence.can_open_source
        and evidence.can_highlight_span
        and evidence.source_revision_id is not None
        and evidence.source_span_ref_id is not None
        and all(
            item.schema_term in context.source_annotation_schemas
            for item in evidence.domain_metadata
        )
    )


def _metadata_allowed(
    context: NativeTextSourceAccessContext,
    evidence: ParsedEvidenceRef,
    artifact: SourceArtifactV3,
    revision: SourceRevisionV2,
) -> bool:
    """One owner for the shared metadata identity and access decision."""
    if artifact.source_artifact_id != evidence.source_artifact_id:
        raise NativeTextSourceAccessIntegrityError("artifact identity mismatch")
    if artifact.status != "active" or artifact.current_revision_id != revision.source_revision_id:
        return False
    if revision.source_artifact_id != artifact.source_artifact_id:
        raise NativeTextSourceAccessIntegrityError("revision artifact binding mismatch")
    if revision.source_revision_id != evidence.source_revision_id:
        raise NativeTextSourceAccessIntegrityError("revision identity mismatch")
    if revision.body_storage != "dm_native_utf8_body_v1":
        raise NativeTextSourceAccessIntegrityError("body storage kind mismatch")
    return _contract_visibility_visible(
        artifact,
        audience=context.audience_labels,
        declared_labels=context.declared_visibility_labels,
    ) and all(
        item.schema_term in context.source_annotation_schemas for item in artifact.domain_metadata
    )


def list_admitted_native_text_sources(
    context: NativeTextSourceAccessContext,
    *,
    evidence_ref_ids: Sequence[str] | None = None,
) -> NativeTextSourceCatalog:
    """Discover authorized metadata; selected reads still verify bytes and proofs.

    Missing metadata yields partial discovery. Visibility exclusions do not disclose
    the excluded source or make an authorized audience's catalogue partial.
    """
    pairs = {}
    evidence_by_id = context.parsed.evidence_by_id
    candidates = (
        evidence_by_id.values()
        if evidence_ref_ids is None
        else (evidence_by_id.get(identity) for identity in dict.fromkeys(evidence_ref_ids))
    )
    for evidence in candidates:
        if evidence is not None and _eligible_evidence(context, evidence):
            pairs.setdefault((evidence.source_artifact_id, evidence.source_revision_id), []).append(
                evidence
            )
    try:
        snapshot = context.source_view.get_native_metadata_snapshot(
            artifact_ids=sorted({pair[0] for pair in pairs}),
            revision_ids=sorted({pair[1] for pair in pairs}),
        )
        complete, sources = True, []
        for (artifact_id, revision_id), evidence in sorted(pairs.items()):
            artifact, revision = (
                snapshot.provenance.get_artifact(artifact_id),
                snapshot.provenance.get_revision(revision_id),
            )
            if artifact is None or revision is None:
                complete = False
                continue
            allowed = tuple(
                sorted(
                    row.evidence_ref_id
                    for row in evidence
                    if _metadata_allowed(context, row, artifact, revision)
                )
            )
            if allowed:
                sources.append(
                    NativeTextSourceMetadata(
                        source_artifact=artifact.model_copy(deep=True),
                        source_revision=revision.model_copy(deep=True),
                        evidence_ref_ids=allowed,
                        origin=snapshot.get_origin(artifact_id, revision_id),
                    )
                )
    except PersistenceUnavailableError:
        raise
    except PersistenceIntegrityError as exc:
        raise NativeTextSourceAccessIntegrityError("source metadata integrity failed") from exc
    return NativeTextSourceCatalog(
        space_id=context.space_id,
        revision_id=context.revision_id,
        source_authority_epoch=context.source_view.epoch,
        sources=tuple(sources),
        complete=complete,
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
    if not _eligible_evidence(context, evidence):
        return _unavailable()

    try:
        source = context.source_view.get_native_text_source(
            source_artifact_id=evidence.source_artifact_id,
            # _eligible_evidence established both frozen fields are non-None.
            source_revision_id=cast(str, evidence.source_revision_id),
            span_id=cast(str, evidence.source_span_ref_id),
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
    if not _metadata_allowed(context, evidence, artifact, revision):
        return _unavailable()
    if proof.source_revision_id != revision.source_revision_id:
        raise NativeTextSourceAccessIntegrityError("span revision binding mismatch")
    if proof.evidence_ref_id != evidence_ref_id:
        raise NativeTextSourceAccessIntegrityError("span evidence binding mismatch")
    if proof.span_id != evidence.source_span_ref_id:
        raise NativeTextSourceAccessIntegrityError("span identity mismatch")

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
