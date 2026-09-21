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

from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .authority import revision_from_command
from .builder import build_parsed_knowledge_revision
from .errors import KnowledgePublicationIntegrityError
from .materialization import (
    NATIVE_VNEXT_GRAPH_SCHEMA,
    GovernedMaterializationResult,
    decode_native_graph_payload,
)
from .ports import KnowledgeRevisionRepository
from .records import PublishedKnowledgeRevision


def publish_governed_materialization(
    materialization: GovernedMaterializationResult,
    *,
    repository: KnowledgeRevisionRepository,
) -> PublishedKnowledgeRevision:
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
    stored = repository.publish_revision(command)
    if stored.revision.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise PersistenceIntegrityError("repository returned a different revision envelope")
    if stored.graph_payload_sha256 != payload_sha:
        raise PersistenceIntegrityError("repository returned a different payload digest")
    return PublishedKnowledgeRevision.from_stored(stored)
