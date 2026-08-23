"""Application seam for existing-world adoption source-classification repair.

The seam consumes raw sealed bundle bytes plus a strict repair intent, validates
every requested correction against the sealed bundle, constructs full target
SourceArtifactV2 models from the sealed originals (never from current database
payloads), and delegates exactly once to the atomic repository operation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, NoReturn

from pydantic import ValidationError

from ..contracts.evidence import SourceArtifactV2
from ..contracts.existing_world_adoption import (
    EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA,
    ExistingWorldAdoptionBundleV2,
    ExistingWorldAdoptionMembershipManifestV1,
    ExistingWorldAdoptionReceiptV3,
    ExistingWorldAdoptionReceiptV4,
    ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1,
    ExistingWorldAdoptionSourceClassificationRepairV1,
    existing_world_adoption_bundle_v2_canonical_bytes,
    sha256_bytes,
)
from ..contracts.existing_world_adoption_repair import (
    ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    ExistingWorldAdoptionSourceClassificationRepairIntentV1,
)
from ..contracts.vocabulary import Visibility
from ..domain.canonical import canonical_sha256
from ..domain.errors import (
    DungeonMindError,
    ExistingWorldAdoptionOutcomeUnknownError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
)
from ..domain.existing_world_membership import (
    existing_world_adoption_membership_sha256,
)
from .graph_snapshot import GraphSnapshotReader
from .repositories import (
    DurableExistingWorldAdoptionReceipt,
    ExistingWorldAdoptionRepository,
)


def _integrity(reason: str, **details: Any) -> NoReturn:
    raise PersistenceIntegrityError(
        "existing-world adoption source-classification repair failed persistence-integrity validation",
        details={"reason": reason, **details},
    ) from None


def _reload_receipt(
    receipt: DurableExistingWorldAdoptionReceipt, *, world_id: str
) -> DurableExistingWorldAdoptionReceipt:
    schema = getattr(receipt, "schema_version", None)
    if schema == EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA:
        receipt_type: type[DurableExistingWorldAdoptionReceipt] = ExistingWorldAdoptionReceiptV3
    elif schema == EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA:
        receipt_type = ExistingWorldAdoptionReceiptV4
    else:
        _integrity("unsupported_adoption_receipt_schema")
    try:
        reloaded = receipt_type.model_validate(receipt.model_dump(mode="json"))
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("adoption_receipt_reload_validation")
    if reloaded.world_id != world_id:
        _integrity("adoption_receipt_identity_mismatch")
    return reloaded


def _derive_membership_manifest(
    bundle: ExistingWorldAdoptionBundleV2,
) -> ExistingWorldAdoptionMembershipManifestV1:
    """Derive the exact adopted-member manifest from the sealed bundle."""
    return ExistingWorldAdoptionMembershipManifestV1(
        source_artifact_ids=sorted(
            artifact.source_artifact_id for artifact in bundle.source_artifacts
        ),
        source_revision_ids=sorted(
            revision.source_revision_id for revision in bundle.source_revisions
        ),
        contribution_ids=sorted(
            contribution.contribution_id for contribution in bundle.contributions
        ),
        identity_decision_ids=sorted(
            decision.decision_id for decision in bundle.identity_decisions
        ),
    )


def _validate_repair_intent(
    intent: ExistingWorldAdoptionSourceClassificationRepairIntentV1,
    bundle: ExistingWorldAdoptionBundleV2,
) -> None:
    """Validate every requested correction against the sealed bundle."""
    if intent.world_id != bundle.world_id:
        _integrity("repair_intent_world_id_mismatch")
    if intent.adoption_id != bundle.adoption_id:
        _integrity("repair_intent_adoption_id_mismatch")

    artifacts_by_id = {
        artifact.source_artifact_id: artifact for artifact in bundle.source_artifacts
    }

    for repair in intent.repairs:
        artifact = artifacts_by_id.get(repair.source_artifact_id)
        if artifact is None:
            _integrity(
                "repair_intent_unknown_artifact",
                source_artifact_id=repair.source_artifact_id,
            )

        # Validate visibility repair: only None → GM
        if repair.set_visibility_to_gm:
            if artifact.visibility is not None:
                _integrity(
                    "repair_intent_visibility_not_none",
                    source_artifact_id=repair.source_artifact_id,
                    current_visibility=artifact.visibility,
                )

        # Validate campaign repair: only campaign-owned → world-owned for
        # session-less worldbuilding artifacts
        if repair.clear_campaign_id:
            if artifact.campaign_id is None:
                _integrity(
                    "repair_intent_campaign_already_none",
                    source_artifact_id=repair.source_artifact_id,
                )
            if artifact.source_domain != "worldbuilding":
                _integrity(
                    "repair_intent_campaign_not_worldbuilding",
                    source_artifact_id=repair.source_artifact_id,
                    source_domain=artifact.source_domain,
                )
            if artifact.session_id is not None:
                _integrity(
                    "repair_intent_campaign_has_session",
                    source_artifact_id=repair.source_artifact_id,
                    session_id=artifact.session_id,
                )


def _derive_target_artifact(
    artifact: SourceArtifactV2,
    repair: ExistingWorldAdoptionSourceClassificationRepairIntentV1,
) -> SourceArtifactV2:
    """Construct the full target SourceArtifactV2 from the sealed original."""
    updates: dict[str, Any] = {}
    if repair.set_visibility_to_gm:
        updates["visibility"] = Visibility.GM
    if repair.clear_campaign_id:
        updates["campaign_id"] = None
    return artifact.model_copy(update=updates)


def _compute_repair_id(
    bundle_sha256: str,
    intent: ExistingWorldAdoptionSourceClassificationRepairIntentV1,
    repaired_at: datetime,
) -> str:
    """Compute a deterministic repair ID from the bundle SHA, intent, and timestamp."""
    payload = {
        "bundle_sha256": bundle_sha256,
        "intent": intent.model_dump(mode="json"),
        "repaired_at": repaired_at.isoformat(),
    }
    return canonical_sha256(payload)


def repair_existing_world_adoption_source_classification(
    raw_bundle: bytes,
    *,
    repair_intent: ExistingWorldAdoptionSourceClassificationRepairIntentV1,
    repaired_at: datetime,
    adoption_repository: ExistingWorldAdoptionRepository,
    graph_reader: GraphSnapshotReader,
) -> ExistingWorldAdoptionReceiptV4:
    """Repair the source classification of one already-adopted world.

    The seam consumes raw sealed bundle bytes plus a strict repair intent,
    validates every requested correction against the sealed bundle, constructs
    full target SourceArtifactV2 models from the sealed originals (never from
    current database payloads), and delegates exactly once to the atomic
    repository operation.
    """
    if not isinstance(raw_bundle, (bytes, bytearray)):
        _integrity("raw_bundle_not_bytes")
    raw = bytes(raw_bundle)
    bundle_sha256 = sha256_bytes(raw)

    # Parse the raw bundle through the existing canonical adoption parser
    from .existing_world_adoption import parse_existing_world_adoption_bundle

    bundle = parse_existing_world_adoption_bundle(raw, graph_reader=graph_reader)
    if not isinstance(bundle, ExistingWorldAdoptionBundleV2):
        _integrity(
            "repair_bundle_schema_unsupported",
            bundle_schema=bundle.schema_version,
        )

    # Require the exact sealed bundle
    if bundle.schema_version != EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA:
        _integrity("repair_bundle_schema_unsupported")

    # Validate the repair intent against the sealed bundle
    _validate_repair_intent(repair_intent, bundle)

    # Derive the exact adopted-member manifest from the sealed bundle
    manifest = _derive_membership_manifest(bundle)

    # Derive original adopted membership M0 from the sealed bundle
    m0 = existing_world_adoption_membership_sha256(
        source_artifacts=bundle.source_artifacts,
        source_revisions=bundle.source_revisions,
        contributions=bundle.contributions,
        identity_decisions=bundle.identity_decisions,
    )

    # Construct full target SourceArtifactV2 models from the sealed originals
    artifacts_by_id = {
        artifact.source_artifact_id: artifact for artifact in bundle.source_artifacts
    }
    corrections: list[ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1] = []
    target_artifacts: list[SourceArtifactV2] = []

    for repair in repair_intent.repairs:
        artifact = artifacts_by_id[repair.source_artifact_id]
        target = _derive_target_artifact(artifact, repair)

        # Compute fingerprints
        original_fingerprint = canonical_sha256(artifact.model_dump(mode="json"))
        effective_fingerprint = canonical_sha256(target.model_dump(mode="json"))

        # Determine changed fields
        changed_fields: list[str] = []
        if repair.set_visibility_to_gm:
            changed_fields.append("visibility")
        if repair.clear_campaign_id:
            changed_fields.append("campaign_id")

        correction = ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1(
            source_artifact_id=repair.source_artifact_id,
            original_record_fingerprint=original_fingerprint,
            effective_record_fingerprint=effective_fingerprint,
            changed_fields=changed_fields,
            original_visibility=artifact.visibility.value if artifact.visibility else None,
            effective_visibility=target.visibility.value if target.visibility else None,
            original_campaign_id=artifact.campaign_id,
            effective_campaign_id=target.campaign_id,
        )
        corrections.append(correction)
        target_artifacts.append(target)

    # Compute effective membership M1 from the target adopted member set
    # Build effective artifacts by replacing repaired artifacts
    effective_artifacts = []
    repaired_ids = {repair.source_artifact_id for repair in repair_intent.repairs}
    target_by_id = {target.source_artifact_id: target for target in target_artifacts}
    for artifact in bundle.source_artifacts:
        if artifact.source_artifact_id in repaired_ids:
            effective_artifacts.append(target_by_id[artifact.source_artifact_id])
        else:
            effective_artifacts.append(artifact)

    m1 = existing_world_adoption_membership_sha256(
        source_artifacts=effective_artifacts,
        source_revisions=bundle.source_revisions,
        contributions=bundle.contributions,
        identity_decisions=bundle.identity_decisions,
    )

    # Compute deterministic repair ID
    repair_id = _compute_repair_id(bundle_sha256, repair_intent, repaired_at)

    # Construct the repair record
    repair_record = ExistingWorldAdoptionSourceClassificationRepairV1(
        repair_id=repair_id,
        repaired_at=repaired_at,
        observed_pre_repair_membership_sha256=m0,
        effective_membership_sha256=m1,
        corrections=corrections,
    )

    # Construct the repository command
    command = ExistingWorldAdoptionSourceClassificationRepairCommandV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        bundle_sha256=bundle_sha256,
        sealed_bundle_bytes=raw,
        repair_intent=repair_intent,
        membership_manifest=manifest,
        corrections=corrections,
        repaired_at=repaired_at,
    )

    # Delegate exactly once to the atomic repository operation
    try:
        receipt = adoption_repository.repair_source_classification(command)
        return _reload_receipt(receipt, world_id=bundle.world_id)
    except Exception as exc:
        # On uncertain outcome, perform one exact repair-receipt probe
        try:
            recovered = adoption_repository.get_for_world(bundle.world_id)
            if recovered is not None and recovered.bundle_sha256 == bundle_sha256:
                return _reload_receipt(recovered, world_id=bundle.world_id)
        except Exception:
            pass
        if isinstance(exc, DungeonMindError) and not isinstance(exc, PersistenceUnavailableError):
            raise
        raise ExistingWorldAdoptionOutcomeUnknownError(
            world_id=bundle.world_id,
            adoption_id=bundle.adoption_id,
            bundle_sha256=bundle_sha256,
            expected_published_revision_id="",
            reason="repair_attempt_or_recovery_probe_failed",
        ) from None