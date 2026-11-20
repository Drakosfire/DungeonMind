"""Privileged historical metadata reads, never permission to publish or open sources.

The host authorizes ownership before this read and independently binds its retained
request to the returned history. Absence does not resolve an unknown outcome.
"""

from ...contracts.review_publication import (
    decode_finalized_review_publication,
    publication_record_payload,
)
from ...domain.errors import CapabilityDeniedError, PersistenceIntegrityError
from ..repositories import HistoricalFinalizedPublicationReader, VerifiedPublicationHistoryEntry

_RECEIPT_SCHEMAS = frozenset(
    {"dm_finalized_review_publication_v1", "dm_finalized_review_publication_v2"}
)


def read_historical_finalized_publication(
    world_id: str,
    operation_id: str,
    *,
    reader: HistoricalFinalizedPublicationReader,
    allowed_receipt_schemas: frozenset[str] = _RECEIPT_SCHEMAS,
) -> VerifiedPublicationHistoryEntry | None:
    """Read one original verified terminal aggregate through a read-only port.

    No current-source eligibility or complete host-request equivalence is proved.
    Unavailability and integrity errors propagate; neither becomes absence.
    """
    if (
        type(allowed_receipt_schemas) is not frozenset
        or not allowed_receipt_schemas
        or any(type(schema) is not str for schema in allowed_receipt_schemas)
        or not allowed_receipt_schemas <= _RECEIPT_SCHEMAS
    ):
        raise CapabilityDeniedError(
            "Publication access denied.",
            details={"reason": "publication_receipt_transport_unsupported"},
        )
    entry = reader.read_verified_publication(world_id, operation_id)
    if entry is None:
        return None
    if not isinstance(entry, VerifiedPublicationHistoryEntry):
        raise PersistenceIntegrityError("historical terminal aggregate is invalid")
    publication, review = entry.publication, entry.review
    if publication is None or review is None:
        raise PersistenceIntegrityError("historical terminal publication is incomplete")
    family = getattr(publication, "schema_version", None)
    if type(family) is not str or family not in _RECEIPT_SCHEMAS:
        raise PersistenceIntegrityError("historical terminal publication family is unknown")
    if family not in allowed_receipt_schemas:
        raise CapabilityDeniedError(
            "Publication access denied.",
            details={"reason": "publication_receipt_transport_unsupported"},
        )
    try:
        publication = decode_finalized_review_publication(publication_record_payload(publication))
        record, revision = review.record, entry.revision
        if (
            publication.world_id != world_id
            or publication.operation_id != operation_id
            or record.world_id != world_id
            or record.review_id != publication.review_id
            or record.operation_id != operation_id
            or record.reviewed_contribution_id != publication.reviewed_contribution_id
            or record.reviewed_contribution_sha256 != publication.reviewed_contribution_sha256
            or record.review_intent_sha256 != publication.review_intent_sha256
            or record.confirmation_id != publication.confirmation_id
            or record.plan_ref.expected_parent_revision_id
            != publication.expected_parent_revision_id
            or record.plan_ref.base_graph_payload_sha256 != publication.parent_graph_payload_sha256
            or record.plan_ref.base_graph_schema != publication.graph_schema
            or revision.world_id != world_id
            or revision.revision_id != publication.published_revision_id
            or revision.parent_revision_id != publication.expected_parent_revision_id
            or revision.graph_schema != publication.graph_schema
            or revision.graph_payload_sha256 != publication.graph_payload_sha256
            or revision.created_at != publication.published_at
            or revision.operation_ids != [operation_id]
            or revision.status != "published"
        ):
            raise PersistenceIntegrityError("historical publication selector correspondence failed")
    except (AttributeError, TypeError, ValueError) as exc:
        raise PersistenceIntegrityError("historical terminal publication is invalid") from exc
    return VerifiedPublicationHistoryEntry(entry.revision, publication, review)
