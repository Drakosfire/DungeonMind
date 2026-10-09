"""Atomic admission of a legacy source artifact and its immutable revision."""

from __future__ import annotations

import hashlib
from datetime import datetime

from ..contracts.evidence import SourceArtifactRecord, SourceRevision
from ..contracts.source_admission import (
    SourceAdmissionReceiptV1,
)
from ..domain.canonical import canonical_sha256
from ..domain.errors import (
    HeadNotFoundError,
    IdempotencyConflictError,
    StaleParentRevisionError,
)
from .repositories import SourceRepository, WorldGraphRepository


def source_admission_command_sha256(
    *,
    world_id: str,
    expected_head_revision_id: str,
    artifact: SourceArtifactRecord,
    revision: SourceRevision,
) -> str:
    """Canonical binding repeated by both repository adapters."""
    return canonical_sha256(
        {
            "world_id": world_id,
            "expected_head_revision_id": expected_head_revision_id,
            "artifact": artifact.model_dump(mode="json"),
            "revision": revision.model_dump(mode="json"),
        }
    )


def admit_source_revision(
    *,
    world_id: str,
    admission_id: str,
    expected_head_revision_id: str,
    artifact: SourceArtifactRecord,
    revision: SourceRevision,
    source_body: bytes,
    admitted_at: datetime,
    world_graph_repository: WorldGraphRepository,
    source_repository: SourceRepository,
) -> SourceAdmissionReceiptV1:
    """Atomically admit one exact source pair to an existing legacy World.

    The body is passed only to prove its digest; storage remains with the
    caller's existing source-body store. This operation never touches graph
    revisions or performs graph publication.
    """
    if artifact.world_id != world_id:
        raise ValueError("source artifact belongs to a different World")
    if revision.source_artifact_id != artifact.source_artifact_id:
        raise ValueError("source revision belongs to a different artifact")
    if artifact.current_revision_id != revision.source_revision_id:
        raise ValueError("artifact current_revision_id must name the admitted revision")
    actual_content_sha256 = hashlib.sha256(source_body).hexdigest()
    if actual_content_sha256 != revision.content_sha256:
        raise ValueError("source body does not match the immutable revision digest")

    command_sha256 = source_admission_command_sha256(
        world_id=world_id,
        expected_head_revision_id=expected_head_revision_id,
        artifact=artifact,
        revision=revision,
    )
    prior = source_repository.get_source_admission(admission_id)
    if prior is not None:
        if (
            prior.world_id != world_id
            or prior.command_sha256 != command_sha256
            or prior.content_sha256 != actual_content_sha256
        ):
            raise IdempotencyConflictError(
                f"source admission {admission_id!r} was replayed with different input"
            )
        return prior

    head = world_graph_repository.get_head(world_id)
    if head is None:
        raise HeadNotFoundError(f"World {world_id!r} has no existing graph head")
    if head.head_revision_id != expected_head_revision_id:
        raise StaleParentRevisionError(
            world_id=world_id,
            expected_parent_revision_id=expected_head_revision_id,
            actual_head_revision_id=head.head_revision_id,
        )

    receipt = SourceAdmissionReceiptV1(
        admission_id=admission_id,
        world_id=world_id,
        expected_head_revision_id=expected_head_revision_id,
        source_artifact_id=artifact.source_artifact_id,
        source_revision_id=revision.source_revision_id,
        content_sha256=actual_content_sha256,
        command_sha256=command_sha256,
        admitted_at=admitted_at,
    )
    # Adapter performs durable-first replay and repeats the head CAS under
    # the same transaction that stores the pair and receipt.
    try:
        return source_repository.admit_source_revision(
            receipt=receipt,
            artifact=artifact,
            revision=revision,
            source_body=source_body,
        )
    except Exception as attempt_error:
        # A transport/connection failure may occur after the adapter committed.
        # Probe once by the durable idempotency key; an exact receipt proves the
        # operation completed. If recovery itself is unavailable, preserve the
        # original failure so callers can retry with the same admission_id.
        try:
            recovered = source_repository.get_source_admission(admission_id)
        except Exception:
            raise attempt_error from None
        if recovered is None:
            raise attempt_error from None
        if (
            recovered.world_id != world_id
            or recovered.command_sha256 != command_sha256
            or recovered.content_sha256 != actual_content_sha256
        ):
            raise IdempotencyConflictError(
                f"source admission {admission_id!r} recovery found a conflicting receipt"
            ) from None
        return recovered
