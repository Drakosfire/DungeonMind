"""Application seam for existing-world adoption source-classification repair.

The seam consumes raw sealed bundle bytes plus a strict repair intent, validates
every requested correction against the sealed bundle, constructs full target
SourceArtifactV2 models from the sealed originals (never from current database
payloads), and delegates exactly once to the atomic repository operation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NoReturn

from pydantic import ValidationError

from ..contracts.evidence import SourceArtifactRecord, SourceArtifactV2, SourceRevision
from ..contracts.existing_world_adoption import (
    EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA,
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
    ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1,
    ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    ExistingWorldAdoptionSourceClassificationRepairIntentV1,
)
from ..contracts.vocabulary import Visibility
from ..domain.canonical import canonical_sha256
from ..domain.errors import (
    DungeonMindError,
    ExistingWorldAdoptionOutcomeUnknownError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
)
from ..domain.existing_world_membership import (
    existing_world_adoption_membership_sha256,
)
from .existing_world_adoption import parse_existing_world_adoption_bundle
from .graph_snapshot import GraphSnapshotReader
from .repositories import (
    DurableExistingWorldAdoptionReceipt,
    DurableGraphContribution,
    DurableIdentityDecision,
    ExistingWorldAdoptionRepository,
)

VERSIONED_ADOPTION_FIELDS = frozenset(
    {
        "schema_version",
        "membership_sha256",
        "effective_membership_sha256",
        "membership_manifest",
        "source_classification_repair",
    }
)


def _integrity(reason: str, **details: Any) -> NoReturn:
    raise PersistenceIntegrityError(
        "existing-world adoption source-classification repair failed "
        "persistence-integrity validation",
        details={"reason": reason, **details},
    ) from None


def record_fingerprint(model: object) -> str:
    return canonical_sha256(model.model_dump(mode="json"))  # type: ignore[attr-defined]


def adoption_identity_facts(receipt: DurableExistingWorldAdoptionReceipt) -> dict[str, Any]:
    """Adoption facts shared across v2/v3/v4 except versioned representation."""
    return receipt.model_dump(mode="json", exclude=set(VERSIONED_ADOPTION_FIELDS))


def derive_membership_manifest(
    bundle: ExistingWorldAdoptionBundleV2,
) -> ExistingWorldAdoptionMembershipManifestV1:
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


def compute_repair_id(
    bundle_sha256: str,
    intent: ExistingWorldAdoptionSourceClassificationRepairIntentV1,
) -> str:
    """Content-bound repair identity; wall-clock is stored, not hashed."""
    return canonical_sha256(
        {
            "bundle_sha256": bundle_sha256,
            "intent": intent.model_dump(mode="json"),
        }
    )


def derive_target_artifact(
    artifact: SourceArtifactV2,
    repair: ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1,
) -> SourceArtifactV2:
    updates: dict[str, Any] = {}
    if repair.set_visibility_to_gm:
        updates["visibility"] = Visibility.GM
    if repair.clear_campaign_id:
        updates["campaign_id"] = None
    return artifact.model_copy(update=updates)


def validate_repair_intent(
    intent: ExistingWorldAdoptionSourceClassificationRepairIntentV1,
    bundle: ExistingWorldAdoptionBundleV2,
) -> None:
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
        if repair.set_visibility_to_gm and artifact.visibility is not None:
            _integrity(
                "repair_intent_visibility_not_none",
                source_artifact_id=repair.source_artifact_id,
                current_visibility=artifact.visibility,
            )
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


def _corrections_and_targets(
    bundle: ExistingWorldAdoptionBundleV2,
    intent: ExistingWorldAdoptionSourceClassificationRepairIntentV1,
) -> tuple[
    list[ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1],
    list[SourceArtifactV2],
    list[SourceArtifactV2],
    str,
]:
    artifacts_by_id = {
        artifact.source_artifact_id: artifact for artifact in bundle.source_artifacts
    }
    corrections: list[ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1] = []
    target_artifacts: list[SourceArtifactV2] = []
    repaired_ids = {repair.source_artifact_id for repair in intent.repairs}
    target_by_id: dict[str, SourceArtifactV2] = {}
    for repair in intent.repairs:
        artifact = artifacts_by_id[repair.source_artifact_id]
        target = derive_target_artifact(artifact, repair)
        changed_fields: list[str] = []
        if repair.set_visibility_to_gm:
            changed_fields.append("visibility")
        if repair.clear_campaign_id:
            changed_fields.append("campaign_id")
        corrections.append(
            ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1(
                source_artifact_id=repair.source_artifact_id,
                original_record_fingerprint=record_fingerprint(artifact),
                effective_record_fingerprint=record_fingerprint(target),
                changed_fields=changed_fields,  # type: ignore[arg-type]
                original_visibility=(
                    artifact.visibility.value if artifact.visibility else None
                ),
                effective_visibility=(
                    target.visibility.value if target.visibility else None
                ),
                original_campaign_id=artifact.campaign_id,
                effective_campaign_id=target.campaign_id,
            )
        )
        target_artifacts.append(target)
        target_by_id[target.source_artifact_id] = target

    effective_artifacts = [
        target_by_id[artifact.source_artifact_id]
        if artifact.source_artifact_id in repaired_ids
        else artifact
        for artifact in bundle.source_artifacts
    ]
    m1 = existing_world_adoption_membership_sha256(
        source_artifacts=effective_artifacts,
        source_revisions=bundle.source_revisions,
        contributions=bundle.contributions,
        identity_decisions=bundle.identity_decisions,
    )
    return corrections, target_artifacts, effective_artifacts, m1


def sealed_membership_sha256(bundle: ExistingWorldAdoptionBundleV2) -> str:
    return existing_world_adoption_membership_sha256(
        source_artifacts=bundle.source_artifacts,
        source_revisions=bundle.source_revisions,
        contributions=bundle.contributions,
        identity_decisions=bundle.identity_decisions,
    )


@dataclass(frozen=True)
class LoadedAdoptedMembership:
    artifacts: dict[str, SourceArtifactRecord]
    revisions: dict[str, SourceRevision]
    contributions: dict[str, DurableGraphContribution]
    identity_decisions: dict[str, DurableIdentityDecision]


@dataclass(frozen=True)
class PreparedSourceClassificationRepair:
    bundle: ExistingWorldAdoptionBundleV2
    observed_pre_repair_membership_sha256: str
    artifacts_to_write: list[SourceArtifactV2]
    v4_receipt: ExistingWorldAdoptionReceiptV4


def parse_sealed_bundle_v2(raw: bytes) -> ExistingWorldAdoptionBundleV2:
    try:
        payload = json.loads(raw.decode("utf-8"))
        bundle = ExistingWorldAdoptionBundleV2.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValidationError, ValueError):
        _integrity("repair_bundle_parse_failed")
    canonical = existing_world_adoption_bundle_v2_canonical_bytes(bundle)
    if canonical != raw:
        _integrity("repair_bundle_not_canonical")
    return bundle


def authenticate_repair_command(
    command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
) -> ExistingWorldAdoptionBundleV2:
    """Re-derive sealed facts inside the UoW; do not trust caller targets."""
    raw = bytes(command.sealed_bundle_bytes)
    if sha256_bytes(raw) != command.bundle_sha256:
        _integrity("repair_command_bundle_sha256_mismatch")
    bundle = parse_sealed_bundle_v2(raw)
    if bundle.schema_version != EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA:
        _integrity("repair_bundle_schema_unsupported", bundle_schema=bundle.schema_version)
    if bundle.world_id != command.world_id:
        _integrity("repair_command_world_id_mismatch")
    if bundle.adoption_id != command.adoption_id:
        _integrity("repair_command_adoption_id_mismatch")
    validate_repair_intent(command.repair_intent, bundle)
    manifest = derive_membership_manifest(bundle)
    if manifest != command.membership_manifest:
        _integrity("repair_command_manifest_mismatch")
    m0 = sealed_membership_sha256(bundle)
    if m0 != command.original_membership_sha256:
        _integrity("repair_command_original_membership_mismatch")
    corrections, targets, _effective, m1 = _corrections_and_targets(
        bundle, command.repair_intent
    )
    if m1 != command.effective_membership_sha256:
        _integrity("repair_command_effective_membership_mismatch")
    if compute_repair_id(command.bundle_sha256, command.repair_intent) != command.repair_id:
        _integrity("repair_command_repair_id_mismatch")
    command_targets = {
        item.source_artifact_id: record_fingerprint(item)
        for item in command.target_artifacts
    }
    derived_targets = {
        item.source_artifact_id: record_fingerprint(item) for item in targets
    }
    if command_targets != derived_targets:
        _integrity("repair_command_target_fingerprint_mismatch")
    command_corrections = {
        item.source_artifact_id: record_fingerprint(item) for item in command.corrections
    }
    derived_corrections = {
        item.source_artifact_id: record_fingerprint(item) for item in corrections
    }
    if command_corrections != derived_corrections:
        _integrity("repair_command_correction_fingerprint_mismatch")
    return bundle


def intent_from_v4_repair(
    receipt: ExistingWorldAdoptionReceiptV4,
) -> ExistingWorldAdoptionSourceClassificationRepairIntentV1:
    """Reconstruct the only legal intent implied by a stored V4 repair record."""
    repairs = [
        ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
            source_artifact_id=correction.source_artifact_id,
            set_visibility_to_gm="visibility" in correction.changed_fields,
            clear_campaign_id="campaign_id" in correction.changed_fields,
        )
        for correction in receipt.source_classification_repair.corrections
    ]
    return ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=receipt.world_id,
        adoption_id=receipt.adoption_id,
        repairs=repairs,
    )


def authenticate_v4_repair_against_sealed_bundle(
    receipt: ExistingWorldAdoptionReceiptV4,
    bundle: ExistingWorldAdoptionBundleV2,
) -> dict[str, SourceArtifactV2]:
    """Prove V4 recorded corrections are exactly sealed originals plus allowed fields.

    For every repaired artifact:

    - sealed fingerprint equals the recorded original fingerprint
    - the sealed-derived target fingerprint equals the recorded effective
      fingerprint
    - only the exact recorded allowed fields change
    - every other field remains the sealed original

    Returns sealed-derived target artifacts keyed by id.
    """
    if bundle.world_id != receipt.world_id or bundle.adoption_id != receipt.adoption_id:
        _integrity("v4_repair_bundle_identity_mismatch")
    manifest = derive_membership_manifest(bundle)
    if manifest != receipt.membership_manifest:
        _integrity("v4_repair_manifest_mismatch")
    m0 = sealed_membership_sha256(bundle)
    if m0 != receipt.membership_sha256:
        _integrity("v4_repair_historical_membership_mismatch")
    intent = intent_from_v4_repair(receipt)
    validate_repair_intent(intent, bundle)
    corrections, targets, _effective, m1 = _corrections_and_targets(bundle, intent)
    if m1 != receipt.effective_membership_sha256:
        _integrity("v4_repair_effective_membership_mismatch")
    repair = receipt.source_classification_repair
    if m1 != repair.effective_membership_sha256:
        _integrity("v4_repair_record_effective_mismatch")
    stored = {
        item.source_artifact_id: record_fingerprint(item) for item in repair.corrections
    }
    derived = {item.source_artifact_id: record_fingerprint(item) for item in corrections}
    if stored != derived:
        _integrity("v4_repair_correction_fingerprint_mismatch")
    sealed_by_id = {
        item.source_artifact_id: item for item in bundle.source_artifacts
    }
    target_by_id = {item.source_artifact_id: item for item in targets}
    for correction in repair.corrections:
        sealed = sealed_by_id[correction.source_artifact_id]
        target = target_by_id[correction.source_artifact_id]
        if record_fingerprint(sealed) != correction.original_record_fingerprint:
            _integrity(
                "v4_repair_original_fingerprint_mismatch",
                source_artifact_id=correction.source_artifact_id,
            )
        if record_fingerprint(target) != correction.effective_record_fingerprint:
            _integrity(
                "v4_repair_effective_fingerprint_mismatch",
                source_artifact_id=correction.source_artifact_id,
            )
    return target_by_id


def expected_adopted_source_artifacts(
    bundle: ExistingWorldAdoptionBundleV2,
    targets: dict[str, SourceArtifactV2],
) -> dict[str, SourceArtifactV2]:
    return {
        artifact.source_artifact_id: targets.get(
            artifact.source_artifact_id, artifact
        )
        for artifact in bundle.source_artifacts
    }


def v4_is_exact_replay(
    stored: ExistingWorldAdoptionReceiptV4,
    command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
) -> bool:
    repair = stored.source_classification_repair
    stored_corrections = {
        item.source_artifact_id: record_fingerprint(item)
        for item in repair.corrections
    }
    command_corrections = {
        item.source_artifact_id: record_fingerprint(item)
        for item in command.corrections
    }
    return (
        stored.world_id == command.world_id
        and stored.adoption_id == command.adoption_id
        and stored.bundle_sha256 == command.bundle_sha256
        and stored.membership_sha256 == command.original_membership_sha256
        and stored.effective_membership_sha256 == command.effective_membership_sha256
        and stored.membership_manifest == command.membership_manifest
        and repair.repair_id == command.repair_id
        and repair.effective_membership_sha256 == command.effective_membership_sha256
        and stored_corrections == command_corrections
    )


def _require_fingerprint_equal(
    current: object,
    sealed: object,
    *,
    reason: str,
    record_id: str,
) -> None:
    if record_fingerprint(current) != record_fingerprint(sealed):
        _integrity(reason, record_id=record_id)


def prove_loaded_membership(
    *,
    command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    bundle: ExistingWorldAdoptionBundleV2,
    loaded: LoadedAdoptedMembership,
) -> str:
    """Prove original-or-target artifacts and sealed equality of other families."""
    manifest = command.membership_manifest
    sealed_artifacts = {
        item.source_artifact_id: item for item in bundle.source_artifacts
    }
    sealed_revisions = {
        item.source_revision_id: item for item in bundle.source_revisions
    }
    sealed_contributions = {
        item.contribution_id: item for item in bundle.contributions
    }
    sealed_identity = {item.decision_id: item for item in bundle.identity_decisions}
    targets = {item.source_artifact_id: item for item in command.target_artifacts}

    if set(loaded.artifacts) != set(manifest.source_artifact_ids):
        _integrity("adoption_repair_artifact_membership_mismatch")
    if set(loaded.revisions) != set(manifest.source_revision_ids):
        _integrity("adoption_repair_revision_membership_mismatch")
    if set(loaded.contributions) != set(manifest.contribution_ids):
        _integrity("adoption_repair_contribution_membership_mismatch")
    if set(loaded.identity_decisions) != set(manifest.identity_decision_ids):
        _integrity("adoption_repair_identity_membership_mismatch")

    for artifact_id in manifest.source_artifact_ids:
        current = loaded.artifacts[artifact_id]
        sealed = sealed_artifacts[artifact_id]
        if artifact_id not in targets:
            _require_fingerprint_equal(
                current,
                sealed,
                reason="adoption_repair_artifact_corruption",
                record_id=artifact_id,
            )
            continue
        current_fp = record_fingerprint(current)
        original_fp = record_fingerprint(sealed)
        target_fp = record_fingerprint(targets[artifact_id])
        if current_fp not in {original_fp, target_fp}:
            _integrity(
                "adoption_repair_artifact_corruption",
                artifact_id=artifact_id,
                current_fingerprint=current_fp,
                original_fingerprint=original_fp,
                effective_fingerprint=target_fp,
            )

    for revision_id in manifest.source_revision_ids:
        _require_fingerprint_equal(
            loaded.revisions[revision_id],
            sealed_revisions[revision_id],
            reason="adoption_repair_revision_corruption",
            record_id=revision_id,
        )
    for contribution_id in manifest.contribution_ids:
        _require_fingerprint_equal(
            loaded.contributions[contribution_id],
            sealed_contributions[contribution_id],
            reason="adoption_repair_contribution_corruption",
            record_id=contribution_id,
        )
    for decision_id in manifest.identity_decision_ids:
        _require_fingerprint_equal(
            loaded.identity_decisions[decision_id],
            sealed_identity[decision_id],
            reason="adoption_repair_identity_corruption",
            record_id=decision_id,
        )

    for artifact_id in targets:
        if artifact_id not in loaded.artifacts:
            _integrity(
                "adoption_repair_non_adopted_artifact",
                artifact_id=artifact_id,
            )

    return existing_world_adoption_membership_sha256(
        source_artifacts=[
            loaded.artifacts[item_id] for item_id in manifest.source_artifact_ids
        ],
        source_revisions=[
            loaded.revisions[item_id] for item_id in manifest.source_revision_ids
        ],
        contributions=[
            loaded.contributions[item_id] for item_id in manifest.contribution_ids
        ],
        identity_decisions=[
            loaded.identity_decisions[item_id]
            for item_id in manifest.identity_decision_ids
        ],
    )


def artifacts_to_write(
    *,
    command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    bundle: ExistingWorldAdoptionBundleV2,
    loaded: LoadedAdoptedMembership,
) -> list[SourceArtifactV2]:
    sealed = {item.source_artifact_id: item for item in bundle.source_artifacts}
    pending: list[SourceArtifactV2] = []
    for target in command.target_artifacts:
        current = loaded.artifacts[target.source_artifact_id]
        current_fp = record_fingerprint(current)
        if current_fp == record_fingerprint(target):
            continue
        if current_fp == record_fingerprint(sealed[target.source_artifact_id]):
            pending.append(target)
            continue
        _integrity(
            "adoption_repair_artifact_corruption",
            artifact_id=target.source_artifact_id,
        )
    return pending


def build_v4_receipt(
    *,
    stored: ExistingWorldAdoptionReceiptV3,
    command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    observed_pre_repair_membership_sha256: str,
) -> ExistingWorldAdoptionReceiptV4:
    return ExistingWorldAdoptionReceiptV4(
        adoption_id=stored.adoption_id,
        world_id=stored.world_id,
        bundle_sha256=stored.bundle_sha256,
        source_provenance=stored.source_provenance,
        published_revision_id=stored.published_revision_id,
        graph_schema=stored.graph_schema,
        graph_payload_sha256=stored.graph_payload_sha256,
        adopted_at=stored.adopted_at,
        source_artifact_count=stored.source_artifact_count,
        source_revision_count=stored.source_revision_count,
        contribution_count=stored.contribution_count,
        identity_decision_count=stored.identity_decision_count,
        membership_sha256=command.original_membership_sha256,
        effective_membership_sha256=command.effective_membership_sha256,
        membership_manifest=command.membership_manifest,
        source_classification_repair=ExistingWorldAdoptionSourceClassificationRepairV1(
            repair_id=command.repair_id,
            repaired_at=command.repaired_at,
            observed_pre_repair_membership_sha256=(
                observed_pre_repair_membership_sha256
            ),
            effective_membership_sha256=command.effective_membership_sha256,
            corrections=command.corrections,
        ),
    )


def prove_v3_adoption_facts(
    *,
    stored: ExistingWorldAdoptionReceiptV3,
    command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    bundle: ExistingWorldAdoptionBundleV2,
) -> None:
    if stored.world_id != command.world_id or stored.world_id != bundle.world_id:
        _integrity("adoption_repair_world_id_mismatch", world_id=command.world_id)
    if stored.adoption_id != command.adoption_id:
        _integrity("adoption_repair_adoption_id_mismatch", world_id=command.world_id)
    if stored.bundle_sha256 != command.bundle_sha256:
        _integrity(
            "adoption_repair_bundle_sha256_mismatch", world_id=command.world_id
        )
    if stored.source_provenance != bundle.source_provenance:
        _integrity("adoption_repair_source_provenance_mismatch")
    if stored.graph_schema != bundle.graph_schema:
        _integrity("adoption_repair_graph_schema_mismatch")
    if stored.graph_payload_sha256 != canonical_sha256(bundle.graph_payload):
        _integrity("adoption_repair_graph_payload_mismatch")
    if stored.source_artifact_count != len(bundle.source_artifacts):
        _integrity("adoption_repair_source_artifact_count_mismatch")
    if stored.source_revision_count != len(bundle.source_revisions):
        _integrity("adoption_repair_source_revision_count_mismatch")
    if stored.contribution_count != len(bundle.contributions):
        _integrity("adoption_repair_contribution_count_mismatch")
    if stored.identity_decision_count != len(bundle.identity_decisions):
        _integrity("adoption_repair_identity_decision_count_mismatch")


def prepare_source_classification_repair(
    *,
    command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    stored: DurableExistingWorldAdoptionReceipt,
    loaded: LoadedAdoptedMembership,
    published_graph_payload: dict[str, Any],
) -> ExistingWorldAdoptionReceiptV4 | PreparedSourceClassificationRepair:
    """Run in-boundary proofs. Return stored V4 on exact replay, else a plan."""
    bundle = authenticate_repair_command(command)
    if isinstance(stored, ExistingWorldAdoptionReceiptV4):
        authenticate_v4_repair_against_sealed_bundle(stored, bundle)
        if v4_is_exact_replay(stored, command):
            return stored
        raise PersistenceIntegrityError(
            "existing-world adoption repair conflicts with the stored v4 receipt",
            details={
                "reason": "adoption_repair_identity_mismatch",
                "world_id": command.world_id,
            },
        )
    if not isinstance(stored, ExistingWorldAdoptionReceiptV3):
        raise PersistenceIntegrityError(
            "existing-world adoption repair requires a v3 receipt",
            details={
                "reason": "adoption_repair_unsupported_schema",
                "world_id": command.world_id,
                "receipt_schema": stored.schema_version,
            },
        )
    prove_v3_adoption_facts(stored=stored, command=command, bundle=bundle)
    if canonical_sha256(published_graph_payload) != stored.graph_payload_sha256:
        _integrity("adoption_repair_published_graph_payload_mismatch")
    observed = prove_loaded_membership(command=command, bundle=bundle, loaded=loaded)
    if stored.membership_sha256 != observed:
        raise PersistenceIntegrityError(
            "existing-world adoption repair membership digest mismatch",
            details={
                "reason": "adoption_repair_membership_mismatch",
                "world_id": command.world_id,
                "expected_membership_sha256": stored.membership_sha256,
                "observed_membership_sha256": observed,
            },
        )
    pending = artifacts_to_write(command=command, bundle=bundle, loaded=loaded)
    return PreparedSourceClassificationRepair(
        bundle=bundle,
        observed_pre_repair_membership_sha256=observed,
        artifacts_to_write=pending,
        v4_receipt=build_v4_receipt(
            stored=stored,
            command=command,
            observed_pre_repair_membership_sha256=observed,
        ),
    )


def membership_from_loaded(
    loaded: LoadedAdoptedMembership,
    manifest: ExistingWorldAdoptionMembershipManifestV1,
) -> str:
    return existing_world_adoption_membership_sha256(
        source_artifacts=[
            loaded.artifacts[item_id] for item_id in manifest.source_artifact_ids
        ],
        source_revisions=[
            loaded.revisions[item_id] for item_id in manifest.source_revision_ids
        ],
        contributions=[
            loaded.contributions[item_id] for item_id in manifest.contribution_ids
        ],
        identity_decisions=[
            loaded.identity_decisions[item_id]
            for item_id in manifest.identity_decision_ids
        ],
    )


def _reload_v4_receipt(
    receipt: DurableExistingWorldAdoptionReceipt, *, world_id: str
) -> ExistingWorldAdoptionReceiptV4:
    schema = getattr(receipt, "schema_version", None)
    if schema != EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA:
        _integrity(
            "unsupported_adoption_receipt_schema",
            receipt_schema=schema,
        )
    try:
        reloaded = ExistingWorldAdoptionReceiptV4.model_validate(
            receipt.model_dump(mode="json")
        )
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("adoption_receipt_reload_validation")
    if reloaded.world_id != world_id:
        _integrity("adoption_receipt_identity_mismatch")
    return reloaded


def _recovered_v4_matches(
    recovered: DurableExistingWorldAdoptionReceipt,
    command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
) -> bool:
    if not isinstance(recovered, ExistingWorldAdoptionReceiptV4):
        return False
    if getattr(recovered, "schema_version", None) != EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA:
        return False
    if not v4_is_exact_replay(recovered, command):
        return False
    try:
        bundle = parse_sealed_bundle_v2(bytes(command.sealed_bundle_bytes))
        authenticate_v4_repair_against_sealed_bundle(recovered, bundle)
    except PersistenceIntegrityError:
        return False
    return True


def repair_existing_world_adoption_source_classification(
    raw_bundle: bytes,
    *,
    repair_intent: ExistingWorldAdoptionSourceClassificationRepairIntentV1,
    repaired_at: datetime,
    adoption_repository: ExistingWorldAdoptionRepository,
    graph_reader: GraphSnapshotReader,
    apply: bool = True,
) -> ExistingWorldAdoptionReceiptV4:
    """Repair the source classification of one already-adopted world.

    ``apply=False`` asks the repository for the real no-write preflight.
    Recovery after an uncertain mutation accepts only an exact durable V4
    repair identity — never an unchanged V3 receipt.
    """
    if not isinstance(raw_bundle, (bytes, bytearray)):
        _integrity("raw_bundle_not_bytes")
    raw = bytes(raw_bundle)
    bundle_sha256 = sha256_bytes(raw)
    bundle = parse_existing_world_adoption_bundle(raw, graph_reader=graph_reader)
    if not isinstance(bundle, ExistingWorldAdoptionBundleV2):
        _integrity(
            "repair_bundle_schema_unsupported",
            bundle_schema=bundle.schema_version,
        )
    if bundle.schema_version != EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA:
        _integrity("repair_bundle_schema_unsupported")
    validate_repair_intent(repair_intent, bundle)
    manifest = derive_membership_manifest(bundle)
    m0 = sealed_membership_sha256(bundle)
    corrections, target_artifacts, _effective, m1 = _corrections_and_targets(
        bundle, repair_intent
    )
    command = ExistingWorldAdoptionSourceClassificationRepairCommandV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        bundle_sha256=bundle_sha256,
        sealed_bundle_bytes=raw,
        repair_intent=repair_intent,
        membership_manifest=manifest,
        target_artifacts=target_artifacts,
        corrections=corrections,
        original_membership_sha256=m0,
        effective_membership_sha256=m1,
        repair_id=compute_repair_id(bundle_sha256, repair_intent),
        repaired_at=repaired_at,
    )
    try:
        receipt = adoption_repository.repair_source_classification(
            command, dry_run=not apply
        )
        return _reload_v4_receipt(receipt, world_id=bundle.world_id)
    except Exception as exc:
        try:
            recovered = adoption_repository.get_for_world(bundle.world_id)
        except Exception:
            recovered = None
        if recovered is not None and _recovered_v4_matches(recovered, command):
            return _reload_v4_receipt(recovered, world_id=bundle.world_id)
        if isinstance(exc, DungeonMindError) and not isinstance(
            exc, PersistenceUnavailableError
        ):
            raise
        raise ExistingWorldAdoptionOutcomeUnknownError(
            world_id=bundle.world_id,
            adoption_id=bundle.adoption_id,
            bundle_sha256=bundle_sha256,
            expected_published_revision_id="",
            reason="repair_attempt_or_recovery_probe_failed",
        ) from None
