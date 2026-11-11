"""Reopen a retained native PDF region before or after Graph publication."""

from collections.abc import Callable
from hashlib import sha256

from dungeonmind.contracts.vnext.pdf_region import NativePdfRegionV1
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3, SourceRevisionV2

from .admission import _contract_visibility_visible


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
