"""Governed publication of one V5.1 materialization.

This module consumes a sealed materialization. It does not accept arbitrary
graph JSON as a product write API.

A thrown publication call may have an unknown commit outcome. Identical
automatic retry is not yet promised safe. V5.3 adds the durable identity and
exact recovery probe required to make that promise. This module does not
retry, and it does not read the head or scan revisions after a repository
failure.
"""

from __future__ import annotations

from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision, PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import ImmutableRevisionConflictError, PersistenceIntegrityError

from .authority import revision_from_command
from .builder import build_parsed_knowledge_revision
from .errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationIntegrityError,
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
)
from .materialization import (
    NATIVE_VNEXT_GRAPH_SCHEMA,
    GovernedMaterializationResult,
    decode_native_graph_payload,
)
from .ports import KnowledgeRevisionRepository
from .records import StoredKnowledgeRevision


def publish_governed_materialization(
    materialization: GovernedMaterializationResult,
    *,
    repository: KnowledgeRevisionRepository,
    publication_id: str,
) -> KnowledgePublicationReceipt:
    """Publish one sealed V5.1 command under repository CAS."""
    command = materialization.command
    if command.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        raise KnowledgePublicationIntegrityError(
            "graph_schema_not_native",
            details={"graph_schema": command.graph_schema},
        )
    payload_sha = canonical_sha256(command.graph_payload)
    if payload_sha != materialization.graph_payload_sha256:
        raise KnowledgePublicationIntegrityError("payload_digest_mismatch")
    if command.parent_revision_id != command.expected_parent_revision_id:
        raise KnowledgePublicationIntegrityError("parent_binding_mismatch")
    decoded = decode_native_graph_payload(command.graph_payload)
    expected: KnowledgeRevision = revision_from_command(command)
    build_parsed_knowledge_revision(revision=expected, decoded_content=decoded)
    if not publication_id.strip():
        raise KnowledgePublicationIntegrityError("publication_id_blank")
    try:
        receipt = repository.publish_publication(command, publication_id)
    except (KnowledgePublicationIdempotencyConflictError, KnowledgeStaleParentRevisionError):
        raise
    except (ImmutableRevisionConflictError, PersistenceIntegrityError):
        raise
    except Exception as exc:
        try:
            recovered = get_publication_receipt(
                command.space_id, publication_id, repository=repository
            )
        except PersistenceIntegrityError:
            raise
        except Exception as probe_exc:
            raise KnowledgePublicationOutcomeUnknownError(
                space_id=command.space_id,
                publication_id=publication_id,
                expected_published_revision_id=expected.revision_id,
                reason=f"publish={type(exc).__name__}; probe={type(probe_exc).__name__}",
            ) from exc
        if recovered is not None:
            return recovered
        raise KnowledgePublicationOutcomeUnknownError(
            space_id=command.space_id,
            publication_id=publication_id,
            expected_published_revision_id=expected.revision_id,
            reason=f"publish={type(exc).__name__}; receipt=missing",
        ) from exc
    return _verify_receipt(
        receipt, command, publication_id=publication_id, repository=repository
    )


def _command_from_stored(stored: StoredKnowledgeRevision) -> PublishKnowledgeRevisionCommand:
    revision = stored.revision
    return PublishKnowledgeRevisionCommand(
        space_id=revision.space_id,
        parent_revision_id=revision.parent_revision_id,
        expected_parent_revision_id=revision.parent_revision_id,
        operation_ids=list(revision.operation_ids),
        graph_schema=revision.graph_schema,
        graph_payload=stored.graph_payload,
        domain_contract_ref=revision.domain_contract_ref,
        semantic_profile_ref=revision.semantic_profile_ref,
        migration_origin_ref=revision.migration_origin_ref,
        created_at=revision.created_at,
    )


def _verify_receipt(
    receipt: KnowledgePublicationReceipt,
    command: PublishKnowledgeRevisionCommand,
    *,
    publication_id: str,
    repository: KnowledgeRevisionRepository,
) -> KnowledgePublicationReceipt:
    if receipt.space_id != command.space_id:
        raise PersistenceIntegrityError("publication receipt space drift")
    if receipt.publication_id != publication_id:
        raise PersistenceIntegrityError("publication receipt publication identity drift")
    if receipt.expected_parent_revision_id != command.expected_parent_revision_id:
        raise PersistenceIntegrityError("publication receipt expected parent drift")
    if receipt.command_sha256 != canonical_sha256(command.model_dump(mode="json")):
        raise PersistenceIntegrityError("publication receipt command digest mismatch")
    stored = repository.get_revision(command.space_id, receipt.published_revision_id)
    if stored is None:
        raise PersistenceIntegrityError("publication receipt references missing revision")
    reconstructed = _command_from_stored(stored)
    if canonical_sha256(reconstructed.model_dump(mode="json")) != receipt.command_sha256:
        raise PersistenceIntegrityError("publication receipt reconstruction mismatch")
    if stored.graph_payload_sha256 != receipt.graph_payload_sha256:
        raise PersistenceIntegrityError("publication receipt payload digest mismatch")
    if stored.revision.revision_id != receipt.published_revision_id:
        raise PersistenceIntegrityError("publication receipt revision mismatch")
    return receipt


def get_publication_receipt(
    space_id: str,
    publication_id: str,
    *,
    repository: KnowledgeRevisionRepository,
) -> KnowledgePublicationReceipt | None:
    """Recover only by the exact durable publication identity."""
    receipt = repository.get_publication_receipt(space_id, publication_id)
    if receipt is None:
        return None
    if receipt.space_id != space_id or receipt.publication_id != publication_id:
        raise PersistenceIntegrityError("publication receipt identity column drift")
    stored = repository.get_revision(space_id, receipt.published_revision_id)
    if stored is None:
        raise PersistenceIntegrityError("publication receipt references missing revision")
    reconstructed = _command_from_stored(stored)
    if canonical_sha256(reconstructed.model_dump(mode="json")) != receipt.command_sha256:
        raise PersistenceIntegrityError("publication receipt command digest mismatch")
    if stored.graph_payload_sha256 != receipt.graph_payload_sha256:
        raise PersistenceIntegrityError("publication receipt payload digest mismatch")
    if stored.revision.parent_revision_id != receipt.expected_parent_revision_id:
        raise PersistenceIntegrityError("publication receipt expected parent drift")
    return receipt
