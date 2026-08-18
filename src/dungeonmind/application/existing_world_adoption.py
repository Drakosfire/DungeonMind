"""Adopt one already-materialized world through a durable unit of work.

The seam consumes raw bundle bytes, hashes those bytes itself, and performs a
durable-first receipt probe. A completed adoption is historical correspondence:
exact replay returns the original receipt without parsing the graph or invoking
the repository mutation path. Success is never inferred from the current head.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, NoReturn

from pydantic import ValidationError

from ..contracts.contribution import (
    AcceptanceState,
    GraphContribution,
    GraphContributionV2,
)
from ..contracts.existing_world_adoption import (
    EXISTING_WORLD_ADOPTION_BUNDLE_SCHEMA,
    EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA,
    EXISTING_WORLD_ADOPTION_COMMAND_SCHEMA,
    EXISTING_WORLD_ADOPTION_COMMAND_V2_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA,
    ExistingWorldAdoptionBundleV1,
    ExistingWorldAdoptionBundleV2,
    ExistingWorldAdoptionCommandV1,
    ExistingWorldAdoptionCommandV2,
    ExistingWorldAdoptionReceiptV1,
    ExistingWorldAdoptionReceiptV2,
    ExistingWorldAdoptionReceiptV3,
    existing_world_adoption_bundle_canonical_bytes,
    existing_world_adoption_bundle_v2_canonical_bytes,
    sha256_bytes,
)
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
from ..domain.revision_ids import compute_revision_id
from .graph_snapshot import GRAPH_SCHEMA_V6, GraphSnapshotReader
from .repositories import (
    ContributionRepository,
    DurableExistingWorldAdoptionCommand,
    DurableExistingWorldAdoptionReceipt,
    ExistingWorldAdoptionRepository,
    IdentityDecisionRepository,
    SourceRepository,
)

if TYPE_CHECKING:
    from .existing_world_correspondence import ExistingWorldCorrespondenceService

_SUPPORTED_GRAPH_SCHEMA = GRAPH_SCHEMA_V6
ExistingWorldAdoptionBundle = ExistingWorldAdoptionBundleV1 | ExistingWorldAdoptionBundleV2


def _integrity(reason: str, **details: Any) -> NoReturn:
    raise PersistenceIntegrityError(
        "existing-world adoption failed persistence-integrity validation",
        details={"reason": reason, **details},
    ) from None


def _reload_receipt(
    receipt: DurableExistingWorldAdoptionReceipt, *, world_id: str
) -> DurableExistingWorldAdoptionReceipt:
    schema = getattr(receipt, "schema_version", None)
    if schema == EXISTING_WORLD_ADOPTION_RECEIPT_SCHEMA:
        receipt_type: type[DurableExistingWorldAdoptionReceipt] = ExistingWorldAdoptionReceiptV1
    elif schema == EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA:
        receipt_type = ExistingWorldAdoptionReceiptV2
    elif schema == EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA:
        receipt_type = ExistingWorldAdoptionReceiptV3
    else:
        _integrity("unsupported_adoption_receipt_schema")
    try:
        reloaded = receipt_type.model_validate(receipt.model_dump(mode="json"))
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("adoption_receipt_reload_validation")
    if reloaded.world_id != world_id:
        _integrity("adoption_receipt_identity_mismatch")
    return reloaded


def _peek_world_identity(raw: bytes) -> tuple[str | None, str | None, str | None]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, None, None
    if not isinstance(payload, dict):
        return None, None, None
    world_id = payload.get("world_id")
    adoption_id = payload.get("adoption_id")
    schema_version = payload.get("schema_version")
    peeked_world = world_id if isinstance(world_id, str) and world_id.strip() else None
    peeked_adoption = adoption_id if isinstance(adoption_id, str) and adoption_id.strip() else None
    peeked_schema = (
        schema_version if isinstance(schema_version, str) and schema_version.strip() else None
    )
    return peeked_world, peeked_adoption, peeked_schema


def _unique(ids: list[str], *, field_name: str) -> None:
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            _integrity("duplicate_durable_id", field=field_name)
        seen.add(item)


def _source_maps(
    bundle: ExistingWorldAdoptionBundle,
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifacts = {artifact.source_artifact_id: artifact for artifact in bundle.source_artifacts}
    revisions = {revision.source_revision_id: revision for revision in bundle.source_revisions}
    return artifacts, revisions


def _require_source_closure(
    *,
    source_artifact_id: str | None,
    source_revision_id: str | None,
    artifacts: dict[str, Any],
    revisions: dict[str, Any],
    field_name: str,
) -> None:
    if source_artifact_id is None and source_revision_id is None:
        return
    if source_artifact_id is not None and source_artifact_id not in artifacts:
        _integrity("source_artifact_not_in_bundle", field=field_name)
    if source_revision_id is not None:
        revision = revisions.get(source_revision_id)
        if revision is None:
            _integrity("source_revision_not_in_bundle", field=field_name)
        assert revision is not None
        if source_artifact_id is not None and revision.source_artifact_id != source_artifact_id:
            _integrity("source_revision_artifact_mismatch", field=field_name)


def _validate_uniqueness(bundle: ExistingWorldAdoptionBundle) -> None:
    _unique(
        [artifact.source_artifact_id for artifact in bundle.source_artifacts],
        field_name="source_artifact_id",
    )
    _unique(
        [revision.source_revision_id for revision in bundle.source_revisions],
        field_name="source_revision_id",
    )
    _unique(
        [contribution.contribution_id for contribution in bundle.contributions],
        field_name="contribution_id",
    )
    _unique(
        [decision.decision_id for decision in bundle.identity_decisions],
        field_name="decision_id",
    )
    _unique(
        [
            f"{ref.schema_}\0{ref.identifier}\0{ref.sha256}"
            for ref in bundle.source_provenance.authority_refs
        ],
        field_name="authority_ref",
    )


def _validate_world_binding(bundle: ExistingWorldAdoptionBundle) -> None:
    world_id = bundle.world_id
    for artifact in bundle.source_artifacts:
        if artifact.world_id != world_id:
            _integrity("world_id_drift", field="source_artifact")
    for contribution in bundle.contributions:
        if contribution.world_id != world_id:
            _integrity("world_id_drift", field="contribution")
    for decision in bundle.identity_decisions:
        if decision.world_id != world_id:
            _integrity("world_id_drift", field="identity_decision")


def _validate_source_revision_closure(bundle: ExistingWorldAdoptionBundle) -> None:
    artifacts, revisions = _source_maps(bundle)
    for artifact in bundle.source_artifacts:
        current = artifact.current_revision_id
        if current is None:
            continue
        revision = revisions.get(current)
        if revision is None:
            _integrity("artifact_current_revision_missing")
        if revision.source_artifact_id != artifact.source_artifact_id:
            _integrity("artifact_current_revision_owner_mismatch")
    for revision in bundle.source_revisions:
        if revision.source_artifact_id not in artifacts:
            _integrity("revision_artifact_missing")


def _validate_contribution_source_closure(
    contribution: GraphContribution | GraphContributionV2,
    *,
    artifacts: dict[str, Any],
    revisions: dict[str, Any],
) -> None:
    _require_source_closure(
        source_artifact_id=contribution.source_artifact_id,
        source_revision_id=contribution.source_revision_id,
        artifacts=artifacts,
        revisions=revisions,
        field_name="contribution",
    )
    for assertion in contribution.assertions:
        _require_source_closure(
            source_artifact_id=assertion.source_artifact_id,
            source_revision_id=assertion.source_revision_id,
            artifacts=artifacts,
            revisions=revisions,
            field_name="assertion",
        )


def _ledger_correction_fail(reason: str) -> NoReturn:
    raise PersistenceIntegrityError(
        "graph contribution correction history failed persistence-integrity validation",
        details={"reason": reason},
    ) from None


def require_v2_contribution_correction_closure(
    contribution: GraphContributionV2,
    *,
    resolve_target: Callable[[str], GraphContribution | GraphContributionV2 | None],
    fail: Callable[[str], NoReturn] = _ledger_correction_fail,
) -> None:
    """Fail closed when a v2 contribution's correction links do not resolve.

    Replacement assertion identity is local to ``contribution``. Target
    contribution/assertion identity is resolved through ``resolve_target``.
    Public ledger append supplies already-durable same-world records; adoption
    bundle validation supplies the in-bundle contribution map.
    """
    for correction in contribution.assertion_corrections:
        target = resolve_target(correction.target_contribution_id)
        if target is None:
            return fail("correction_target_contribution_missing")
        target_assertion = next(
            (
                assertion
                for assertion in target.assertions
                if assertion.assertion_id == correction.target_assertion_id
            ),
            None,
        )
        if target_assertion is None:
            return fail("correction_target_assertion_missing")
        if correction.replacement_assertion_id is None:
            continue
        replacement = next(
            (
                assertion
                for assertion in contribution.assertions
                if assertion.assertion_id == correction.replacement_assertion_id
            ),
            None,
        )
        if replacement is None:
            return fail("correction_replacement_assertion_missing")
        if replacement.acceptance_state is not AcceptanceState.ACCEPTED:
            return fail("correction_replacement_assertion_not_accepted")


def _validate_correction_closure(bundle: ExistingWorldAdoptionBundleV2) -> None:
    contributions = {item.contribution_id: item for item in bundle.contributions}
    for contribution in bundle.contributions:
        require_v2_contribution_correction_closure(
            contribution,
            resolve_target=lambda target_id: contributions.get(target_id),
            fail=_integrity,
        )


def _validate_bundle_closures(bundle: ExistingWorldAdoptionBundle) -> None:
    _validate_uniqueness(bundle)
    _validate_world_binding(bundle)
    _validate_source_revision_closure(bundle)
    artifacts, revisions = _source_maps(bundle)
    for contribution in bundle.contributions:
        _validate_contribution_source_closure(
            contribution, artifacts=artifacts, revisions=revisions
        )
    if isinstance(bundle, ExistingWorldAdoptionBundleV2):
        _validate_correction_closure(bundle)


def _validate_graph(
    bundle: ExistingWorldAdoptionBundle,
    graph_reader: GraphSnapshotReader,
) -> None:
    if bundle.graph_schema != _SUPPORTED_GRAPH_SCHEMA:
        _integrity("unsupported_graph_schema")
    try:
        snapshot = graph_reader.parse(
            graph_schema=bundle.graph_schema,
            graph_payload=bundle.graph_payload,
        )
    except PersistenceIntegrityError:
        raise
    except (TypeError, ValidationError, ValueError) as exc:
        raise PersistenceIntegrityError(
            "existing-world adoption failed persistence-integrity validation",
            details={"reason": "graph_payload_parse_failed"},
        ) from exc
    if snapshot.world_id != bundle.world_id:
        _integrity("world_id_drift", field="graph_payload")
    if snapshot.graph_schema != _SUPPORTED_GRAPH_SCHEMA:
        _integrity("unsupported_graph_schema")
    artifacts, revisions = _source_maps(bundle)
    for evidence in snapshot.evidence.values():
        _require_source_closure(
            source_artifact_id=evidence.source_artifact_id,
            source_revision_id=evidence.source_revision_id,
            artifacts=artifacts,
            revisions=revisions,
            field_name="graph_evidence",
        )


def bind_existing_world_adoption_command(
    command: DurableExistingWorldAdoptionCommand,
) -> DurableExistingWorldAdoptionCommand:
    """Reload one command and bind its caller-supplied hashes to the bundle.

    Repository adapters must invoke this before any replay, pristine-target,
    or mutation branch. Caller-minted digests cannot manufacture a receipt.
    """
    schema = getattr(command, "schema_version", None)
    if schema == EXISTING_WORLD_ADOPTION_COMMAND_SCHEMA:
        command_type: type[DurableExistingWorldAdoptionCommand] = ExistingWorldAdoptionCommandV1
        canonical_bytes = existing_world_adoption_bundle_canonical_bytes
    elif schema == EXISTING_WORLD_ADOPTION_COMMAND_V2_SCHEMA:
        command_type = ExistingWorldAdoptionCommandV2
        canonical_bytes = existing_world_adoption_bundle_v2_canonical_bytes
    else:
        _integrity("unsupported_adoption_command_schema")
    try:
        validated = command_type.model_validate(command.model_dump(mode="json"))
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("adoption_command_validation")
    bundle = validated.bundle
    expected_bundle_sha256 = sha256_bytes(canonical_bytes(bundle))  # type: ignore[arg-type]
    expected_graph_payload_sha256 = canonical_sha256(bundle.graph_payload)
    expected_published_revision_id = compute_revision_id(
        world_id=bundle.world_id,
        parent_revision_id=None,
        operation_ids=[bundle.adoption_id],
        graph_schema=bundle.graph_schema,
        graph_payload_sha256=expected_graph_payload_sha256,
    )
    if validated.bundle_sha256 != expected_bundle_sha256:
        _integrity("unbound_bundle_sha256")
    if validated.graph_payload_sha256 != expected_graph_payload_sha256:
        _integrity("unbound_graph_payload_sha256")
    if validated.expected_published_revision_id != expected_published_revision_id:
        _integrity("unbound_expected_published_revision_id")
    return validated


def parse_existing_world_adoption_bundle(
    raw_bundle: bytes,
    *,
    graph_reader: GraphSnapshotReader,
) -> ExistingWorldAdoptionBundle:
    """Parse, canonicalize, and close one adoption bundle before mutation."""
    if not isinstance(raw_bundle, (bytes, bytearray)):
        _integrity("raw_bundle_not_bytes")
    raw = bytes(raw_bundle)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _integrity("raw_bundle_not_json")
    if not isinstance(payload, dict):
        _integrity("bundle_shape_invalid")
    schema = payload.get("schema_version")
    if schema == EXISTING_WORLD_ADOPTION_BUNDLE_SCHEMA:
        bundle_type: type[ExistingWorldAdoptionBundle] = ExistingWorldAdoptionBundleV1
        canonical_bytes = existing_world_adoption_bundle_canonical_bytes
    elif schema == EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA:
        bundle_type = ExistingWorldAdoptionBundleV2
        canonical_bytes = existing_world_adoption_bundle_v2_canonical_bytes
    else:
        _integrity("unsupported_adoption_bundle_schema")
    try:
        bundle = bundle_type.model_validate(payload)
    except (TypeError, ValidationError, ValueError):
        _integrity("bundle_shape_invalid")
    canonical = canonical_bytes(bundle)  # type: ignore[arg-type]
    if canonical != raw:
        _integrity("non_canonical_bundle_bytes")
    _validate_bundle_closures(bundle)
    _validate_graph(bundle, graph_reader)
    return bundle


def terminal_existing_world_adoption_receipt(
    command: DurableExistingWorldAdoptionCommand,
    *,
    published_revision_id: str,
) -> DurableExistingWorldAdoptionReceipt:
    """Build the terminal receipt for one bound adoption command.

    V2 commands emit a V3 receipt: the exact adopted-membership checkpoint is
    computed from the sealed bundle's four history families at adoption time,
    so later correspondence can recompute current durable membership and
    compare before any ``STALE`` classification is legal. V1 commands retain
    the legacy V1 receipt.
    """
    bundle = command.bundle
    if command.schema_version == EXISTING_WORLD_ADOPTION_COMMAND_V2_SCHEMA:
        return ExistingWorldAdoptionReceiptV3(
            adoption_id=bundle.adoption_id,
            world_id=bundle.world_id,
            bundle_sha256=command.bundle_sha256,
            source_provenance=bundle.source_provenance,
            published_revision_id=published_revision_id,
            graph_schema=bundle.graph_schema,
            graph_payload_sha256=command.graph_payload_sha256,
            adopted_at=command.requested_adopted_at,
            source_artifact_count=len(bundle.source_artifacts),
            source_revision_count=len(bundle.source_revisions),
            contribution_count=len(bundle.contributions),
            identity_decision_count=len(bundle.identity_decisions),
            membership_sha256=existing_world_adoption_membership_sha256(
                source_artifacts=bundle.source_artifacts,
                source_revisions=bundle.source_revisions,
                contributions=bundle.contributions,
                identity_decisions=bundle.identity_decisions,
            ),
        )
    return ExistingWorldAdoptionReceiptV1(
        adoption_id=bundle.adoption_id,
        world_id=bundle.world_id,
        bundle_sha256=command.bundle_sha256,
        source_provenance=bundle.source_provenance,
        published_revision_id=published_revision_id,
        graph_schema=bundle.graph_schema,
        graph_payload_sha256=command.graph_payload_sha256,
        adopted_at=command.requested_adopted_at,
        source_artifact_count=len(bundle.source_artifacts),
        source_revision_count=len(bundle.source_revisions),
        contribution_count=len(bundle.contributions),
        identity_decision_count=len(bundle.identity_decisions),
    )


def _build_command(
    bundle: ExistingWorldAdoptionBundle,
    *,
    bundle_sha256: str,
    graph_payload_sha256: str,
    expected_published_revision_id: str,
    adopted_at: datetime,
) -> DurableExistingWorldAdoptionCommand:
    try:
        if isinstance(bundle, ExistingWorldAdoptionBundleV2):
            return ExistingWorldAdoptionCommandV2(
                bundle=bundle,
                bundle_sha256=bundle_sha256,
                expected_published_revision_id=expected_published_revision_id,
                graph_payload_sha256=graph_payload_sha256,
                requested_adopted_at=adopted_at,
            )
        return ExistingWorldAdoptionCommandV1(
            bundle=bundle,
            bundle_sha256=bundle_sha256,
            expected_published_revision_id=expected_published_revision_id,
            graph_payload_sha256=graph_payload_sha256,
            requested_adopted_at=adopted_at,
        )
    except (TypeError, ValidationError, ValueError):
        _integrity("adoption_command_validation")


def adopt_existing_world(
    raw_bundle: bytes,
    *,
    adopted_at: datetime,
    adoption_repository: ExistingWorldAdoptionRepository,
    graph_reader: GraphSnapshotReader,
) -> DurableExistingWorldAdoptionReceipt:
    """Adopt or exactly replay one existing-world migration bundle."""
    if not isinstance(raw_bundle, (bytes, bytearray)):
        _integrity("raw_bundle_not_bytes")
    raw = bytes(raw_bundle)
    bundle_sha256 = sha256_bytes(raw)
    peeked_world_id, peeked_adoption_id, peeked_schema = _peek_world_identity(raw)

    if peeked_world_id is not None:
        existing = adoption_repository.get_for_world(peeked_world_id)
        if existing is not None:
            if existing.bundle_sha256 == bundle_sha256:
                return _reload_receipt(existing, world_id=peeked_world_id)
            raise IdempotencyConflictError(
                "existing-world adoption identity conflicts with the requested bundle",
                details={
                    "world_id": peeked_world_id,
                    "adoption_id": existing.adoption_id,
                    "bundle_sha256": bundle_sha256,
                    "stored_receipt_schema": existing.schema_version,
                    "requested_bundle_schema": peeked_schema,
                },
            )

    bundle = parse_existing_world_adoption_bundle(raw, graph_reader=graph_reader)
    graph_payload_sha256 = canonical_sha256(bundle.graph_payload)
    expected_published_revision_id = compute_revision_id(
        world_id=bundle.world_id,
        parent_revision_id=None,
        operation_ids=[bundle.adoption_id],
        graph_schema=bundle.graph_schema,
        graph_payload_sha256=graph_payload_sha256,
    )
    command = _build_command(
        bundle,
        bundle_sha256=bundle_sha256,
        graph_payload_sha256=graph_payload_sha256,
        expected_published_revision_id=expected_published_revision_id,
        adopted_at=adopted_at,
    )

    try:
        receipt = adoption_repository.adopt(command)
        return _reload_receipt(receipt, world_id=bundle.world_id)
    except Exception as exc:
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
            adoption_id=bundle.adoption_id if peeked_adoption_id is None else peeked_adoption_id,
            bundle_sha256=bundle_sha256,
            expected_published_revision_id=command.expected_published_revision_id,
            reason="adoption_attempt_or_recovery_probe_failed",
        ) from None


def promote_existing_world_adoption_receipt_v3(
    raw_bundle: bytes,
    *,
    world_id: str,
    adoption_repository: ExistingWorldAdoptionRepository,
    source_repository: SourceRepository,
    contribution_repository: ContributionRepository,
    identity_repository: IdentityDecisionRepository,
    graph_reader: GraphSnapshotReader,
    correspondence_service: ExistingWorldCorrespondenceService,
) -> ExistingWorldAdoptionReceiptV3:
    """Steward-supervised v2→v3 receipt promotion for one adopted world.

    The expected membership digest is derived from the exact sealed Buddy
    bundle — never minted from current database state. Promotion is legal
    only when the sealed bundle, the durable receipt, and the current durable
    membership all agree exactly; only the receipt's versioned representation
    changes (no graph/history mutation). Replay with the same facts and digest
    is an exact no-op success; any disagreement fails closed with zero
    mutation. V1 receipts are out of scope and fail closed.
    """
    if not isinstance(raw_bundle, (bytes, bytearray)):
        _integrity("raw_bundle_not_bytes")
    raw = bytes(raw_bundle)
    bundle = parse_existing_world_adoption_bundle(raw, graph_reader=graph_reader)
    if not isinstance(bundle, ExistingWorldAdoptionBundleV2):
        _integrity(
            "adoption_promotion_bundle_schema_unsupported",
            world_id=world_id,
            bundle_schema=bundle.schema_version,
        )
    bundle_sha256 = sha256_bytes(raw)

    stored = adoption_repository.get_for_world(world_id)
    if stored is None:
        _integrity("adoption_receipt_missing", world_id=world_id)
    receipt = _reload_receipt(stored, world_id=world_id)
    if isinstance(receipt, ExistingWorldAdoptionReceiptV1):
        _integrity(
            "adoption_receipt_promotion_unsupported_schema",
            world_id=world_id,
            receipt_schema=receipt.schema_version,
        )

    graph_payload_sha256 = canonical_sha256(bundle.graph_payload)
    expected_published_revision_id = compute_revision_id(
        world_id=bundle.world_id,
        parent_revision_id=None,
        operation_ids=[bundle.adoption_id],
        graph_schema=bundle.graph_schema,
        graph_payload_sha256=graph_payload_sha256,
    )
    identity_agrees = (
        receipt.world_id == world_id == bundle.world_id
        and receipt.adoption_id == bundle.adoption_id
        and receipt.bundle_sha256 == bundle_sha256
        and receipt.source_provenance == bundle.source_provenance
        and receipt.graph_schema == bundle.graph_schema
        and receipt.graph_payload_sha256 == graph_payload_sha256
        and receipt.published_revision_id == expected_published_revision_id
    )
    if not identity_agrees:
        _integrity(
            "adoption_receipt_promotion_identity_mismatch",
            world_id=world_id,
            adoption_id=bundle.adoption_id,
        )

    bundle_membership_sha256 = existing_world_adoption_membership_sha256(
        source_artifacts=bundle.source_artifacts,
        source_revisions=bundle.source_revisions,
        contributions=bundle.contributions,
        identity_decisions=bundle.identity_decisions,
    )
    if isinstance(receipt, ExistingWorldAdoptionReceiptV3):
        if receipt.membership_sha256 != bundle_membership_sha256:
            _integrity(
                "adoption_receipt_promotion_identity_mismatch",
                world_id=world_id,
                adoption_id=bundle.adoption_id,
            )
        return receipt

    artifacts = source_repository.list_artifacts_for_world(world_id)
    revisions = [
        revision
        for artifact in artifacts
        for revision in source_repository.list_revisions(artifact.source_artifact_id)
    ]
    current_membership_sha256 = existing_world_adoption_membership_sha256(
        source_artifacts=artifacts,
        source_revisions=revisions,
        contributions=contribution_repository.list_for_world(world_id),
        identity_decisions=identity_repository.list_for_world(world_id),
    )
    if current_membership_sha256 != bundle_membership_sha256:
        _integrity(
            "adoption_promotion_membership_mismatch",
            world_id=world_id,
            adoption_id=bundle.adoption_id,
            expected_membership_sha256=bundle_membership_sha256,
            current_membership_sha256=current_membership_sha256,
        )

    result = correspondence_service.check(raw, world_id=world_id)
    if result.classification != "CORRESPONDING":
        _integrity(
            "adoption_receipt_promotion_correspondence_failed",
            world_id=world_id,
            adoption_id=bundle.adoption_id,
            classification=result.classification,
        )

    promoted = ExistingWorldAdoptionReceiptV3(
        adoption_id=receipt.adoption_id,
        world_id=receipt.world_id,
        bundle_sha256=receipt.bundle_sha256,
        source_provenance=receipt.source_provenance,
        published_revision_id=receipt.published_revision_id,
        graph_schema=receipt.graph_schema,
        graph_payload_sha256=receipt.graph_payload_sha256,
        adopted_at=receipt.adopted_at,
        source_artifact_count=receipt.source_artifact_count,
        source_revision_count=receipt.source_revision_count,
        contribution_count=receipt.contribution_count,
        identity_decision_count=receipt.identity_decision_count,
        membership_sha256=bundle_membership_sha256,
    )
    return adoption_repository.promote_to_v3_receipt(
        world_id, expected=receipt, promoted=promoted
    )
