"""Expected-parent CAS for one native PublishKnowledgeRevisionCommand.

Adapters supply the locked reads and writes. This module does not retry, probe
after failure, or rebase a stale parent.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from dungeonmind.contracts.vnext.knowledge import (
    KnowledgeHead,
    KnowledgeRevision,
    PublishKnowledgeRevisionCommand,
)
from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.domain.errors import ImmutableRevisionConflictError, PersistenceIntegrityError

from .errors import KnowledgeStaleParentRevisionError
from .materialization import NATIVE_VNEXT_GRAPH_SCHEMA
from .records import KnowledgeHeadEvent, StoredKnowledgeRevision
from .revision_ids import compute_knowledge_revision_id


def revision_from_command(command: PublishKnowledgeRevisionCommand) -> KnowledgeRevision:
    """Build the immutable revision envelope. Does not consult a head."""
    payload_sha = canonical_sha256(command.graph_payload)
    revision_id = compute_knowledge_revision_id(
        space_id=command.space_id,
        parent_revision_id=command.parent_revision_id,
        operation_ids=command.operation_ids,
        graph_schema=command.graph_schema,
        graph_payload_sha256=payload_sha,
        domain_contract_ref=command.domain_contract_ref,
        semantic_profile_ref=command.semantic_profile_ref,
        migration_origin_ref=command.migration_origin_ref,
    )
    return KnowledgeRevision(
        space_id=command.space_id,
        revision_id=revision_id,
        parent_revision_id=command.parent_revision_id,
        created_at=command.created_at,
        operation_ids=list(command.operation_ids),
        graph_schema=command.graph_schema,
        graph_payload_sha256=payload_sha,
        domain_contract_ref=command.domain_contract_ref,
        semantic_profile_ref=command.semantic_profile_ref,
        migration_origin_ref=command.migration_origin_ref,
        status="published",
    )


def verify_stored_revision(
    stored: StoredKnowledgeRevision,
    *,
    expected: KnowledgeRevision | None = None,
    graph_payload: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed when a stored row disagrees with its envelope or identity."""
    revision = stored.revision
    payload = stored.graph_payload
    if canonical_sha256(payload) != stored.graph_payload_sha256:
        raise PersistenceIntegrityError("stored graph payload hash mismatch")
    if revision.graph_payload_sha256 != stored.graph_payload_sha256:
        raise PersistenceIntegrityError("revision envelope payload hash mismatch")
    recomputed = compute_knowledge_revision_id(
        space_id=revision.space_id,
        parent_revision_id=revision.parent_revision_id,
        operation_ids=revision.operation_ids,
        graph_schema=revision.graph_schema,
        graph_payload_sha256=revision.graph_payload_sha256,
        domain_contract_ref=revision.domain_contract_ref,
        semantic_profile_ref=revision.semantic_profile_ref,
        migration_origin_ref=revision.migration_origin_ref,
    )
    if recomputed != revision.revision_id:
        raise PersistenceIntegrityError("recomputed native revision id disagrees with stored id")
    if expected is not None and revision.model_dump(mode="json") != expected.model_dump(
        mode="json"
    ):
        raise ImmutableRevisionConflictError(
            f"revision {revision.revision_id!r} already exists with a different envelope"
        )
    if graph_payload is not None and canonical_json(payload) != canonical_json(dict(graph_payload)):
        raise ImmutableRevisionConflictError(
            f"revision {revision.revision_id!r} already exists with a different graph payload"
        )


def commit_expected_parent(
    command: PublishKnowledgeRevisionCommand,
    *,
    read_head: Callable[[], KnowledgeHead | None],
    read_revision: Callable[[str], StoredKnowledgeRevision | None],
    insert_revision: Callable[[StoredKnowledgeRevision], None],
    advance_head: Callable[[KnowledgeHead, KnowledgeHeadEvent], None],
) -> StoredKnowledgeRevision:
    """Compare expected parent to the locked head, then insert and advance."""
    if command.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        raise PersistenceIntegrityError(f"native publication requires {NATIVE_VNEXT_GRAPH_SCHEMA}")
    expected = revision_from_command(command)
    head = read_head()
    actual_head_id = None if head is None else head.head_revision_id
    if (
        command.expected_parent_revision_id != actual_head_id
        or command.parent_revision_id != actual_head_id
    ):
        raise KnowledgeStaleParentRevisionError(
            space_id=command.space_id,
            expected_parent_revision_id=command.expected_parent_revision_id,
            actual_head_revision_id=actual_head_id,
        )
    existing = read_revision(expected.revision_id)
    if existing is not None:
        verify_stored_revision(
            existing,
            expected=expected,
            graph_payload=command.graph_payload,
        )
        advance_head(
            KnowledgeHead(
                space_id=command.space_id,
                head_revision_id=expected.revision_id,
                updated_at=command.created_at,
            ),
            KnowledgeHeadEvent(
                space_id=command.space_id,
                event_kind="publish",
                previous_revision_id=actual_head_id,
                target_revision_id=expected.revision_id,
                occurred_at=command.created_at,
            ),
        )
        return existing
    stored = StoredKnowledgeRevision.seal(expected, command.graph_payload)
    insert_revision(stored)
    advance_head(
        KnowledgeHead(
            space_id=command.space_id,
            head_revision_id=expected.revision_id,
            updated_at=command.created_at,
        ),
        KnowledgeHeadEvent(
            space_id=command.space_id,
            event_kind="publish",
            previous_revision_id=actual_head_id,
            target_revision_id=expected.revision_id,
            occurred_at=command.created_at,
        ),
    )
    return stored
