"""Atomic admission of a legacy source artifact and its immutable revision."""

from __future__ import annotations

import hashlib
from datetime import datetime

from ..contracts.evidence import SourceArtifactRecord, SourceArtifactV2, SourceRevision
from ..contracts.source_admission import (
    SourceAdmissionReceiptV1,
)
from ..domain.canonical import canonical_sha256
from ..domain.errors import (
    HeadNotFoundError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    StaleParentRevisionError,
)
from .repositories import SourceRepository, WorldGraphRepository


def load_admitted_source_pair(
    *,
    world_id: str,
    source_artifact_id: str,
    source_revision_id: str,
    source_repository: SourceRepository,
) -> tuple[SourceArtifactRecord, SourceRevision] | None:
    """Read one coherent catalog pair; missing records never grant authority.

    This read checks pair ownership and the current revision, not whether source
    claims support a graph fact. It neither reads bodies nor admits records.
    """
    snapshot = source_repository.get_provenance_snapshot(
        artifact_ids=[source_artifact_id],
        revision_ids=[source_revision_id],
    )
    artifact = snapshot.get_artifact(source_artifact_id)
    revision = snapshot.get_revision(source_revision_id)
    if artifact is None and revision is None:
        return None
    if artifact is None or revision is None:
        raise PersistenceIntegrityError("source catalog contains only one half of the source pair")
    if (
        artifact.source_artifact_id != source_artifact_id
        or revision.source_revision_id != source_revision_id
        or revision.source_artifact_id != source_artifact_id
        or artifact.current_revision_id != source_revision_id
        or artifact.world_id != world_id
    ):
        raise IdempotencyConflictError("source pair changed identity, World, or current revision")
    locator = revision.locator
    if (revision.body_storage != "postgres" and not locator) or (
        locator is not None and (not locator.strip() or any(ord(c) < 32 for c in locator))
    ):
        raise PersistenceIntegrityError("source revision has an invalid body locator")
    return artifact, revision


def match_admitted_source_revision(
    *,
    artifact: SourceArtifactV2,
    revision: SourceRevision,
    verified_input_sha256: str | None,
    source_repository: SourceRepository,
) -> tuple[SourceArtifactV2, SourceRevision] | None:
    """Compare producer input with native catalog scope and protection.

    Return the exact stored records without rewriting locators, timestamps or
    catalog-owned lineage. A verified digest permits a different input mirror;
    it is supplied by the body owner, not established by this catalog read.
    Actual admission/body hashing belongs to ``admit_source_revision`` below.
    """
    if (
        artifact.current_revision_id != revision.source_revision_id
        or revision.source_artifact_id != artifact.source_artifact_id
    ):
        raise IdempotencyConflictError("incoming artifact does not name its source revision")
    pair = load_admitted_source_pair(
        world_id=artifact.world_id,
        source_artifact_id=artifact.source_artifact_id,
        source_revision_id=revision.source_revision_id,
        source_repository=source_repository,
    )
    if pair is None:
        return None
    stored_artifact, stored_revision = pair
    if not isinstance(stored_artifact, SourceArtifactV2):
        raise IdempotencyConflictError("source artifact schema differs from incoming source")
    exact_fields = (
        "source_domain_key",
        "source_domain",
        "world_id",
        "campaign_id",
        "session_id",
        "visibility",
        "artifact_kind",
        "document_class",
        "review_state",
        "source_visibility_state",
        "status",
    )
    if (
        any(getattr(stored_artifact, key) != getattr(artifact, key) for key in exact_fields)
        or (
            artifact.workspace_document_ref is not None
            and stored_artifact.workspace_document_ref != artifact.workspace_document_ref
        )
        or any(stored_artifact.lineage.get(key) != value for key, value in artifact.lineage.items())
        or (artifact.authority is not None and stored_artifact.authority != artifact.authority)
        or stored_revision.body_storage != revision.body_storage
        or stored_revision.content_sha256 != revision.content_sha256
    ):
        raise IdempotencyConflictError("source scope, protection, or body differs from catalog")
    verified = (
        verified_input_sha256.removeprefix("sha256:").strip().lower()
        if verified_input_sha256 is not None
        else None
    )
    if verified is not None and verified != stored_revision.content_sha256:
        raise IdempotencyConflictError("verified input differs from admitted source body")
    incoming_uri = artifact.uri or revision.locator
    if incoming_uri not in {stored_artifact.uri, stored_revision.locator} and (
        verified != stored_revision.content_sha256
    ):
        raise IdempotencyConflictError("alternate source mirror has no matching byte verification")
    return stored_artifact, stored_revision


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
