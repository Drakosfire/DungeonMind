"""Reopen a retained native PDF region before or after Graph publication."""

from collections.abc import Callable

from dungeonmind.contracts.vnext.pdf_region import NativePdfRegionV1
from dungeonmind.contracts.vnext.source import SourceArtifactV3, SourceRevisionV2

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
    record = load(authorized_space_id, region.source_revision_id)
    if record is None:
        return None
    artifact, revision, page_count, body = record
    if artifact.status != "active" or not _contract_visibility_visible(
        artifact, audience=audience, declared_labels=declared_labels
    ):
        return None
    region.validate_source(revision, body=body, page_count=page_count)
    return body
