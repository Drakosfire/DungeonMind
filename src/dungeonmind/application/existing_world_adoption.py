"""Adopt one already-materialized world through a durable unit of work.

The seam consumes raw bundle bytes, hashes those bytes itself, and performs a
durable-first receipt probe. A completed adoption is historical correspondence:
exact replay returns the original receipt without parsing the graph or invoking
the repository mutation path. Success is never inferred from the current head.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, NoReturn

from pydantic import ValidationError

from ..contracts.contribution import GraphContribution, GraphContributionAssertion
from ..contracts.existing_world_adoption import (
    ExistingWorldAdoptionBundleV1,
    ExistingWorldAdoptionCommandV1,
    ExistingWorldAdoptionReceiptV1,
    existing_world_adoption_bundle_canonical_bytes,
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
from ..domain.revision_ids import compute_revision_id
from .graph_snapshot import GRAPH_SCHEMA_V6, GraphSnapshotReader
from .repositories import ExistingWorldAdoptionRepository

_SUPPORTED_GRAPH_SCHEMA = GRAPH_SCHEMA_V6


def _integrity(reason: str, **details: Any) -> NoReturn:
    raise PersistenceIntegrityError(
        "existing-world adoption failed persistence-integrity validation",
        details={"reason": reason, **details},
    ) from None


def _reload_receipt(
    receipt: ExistingWorldAdoptionReceiptV1, *, world_id: str
) -> ExistingWorldAdoptionReceiptV1:
    try:
        reloaded = ExistingWorldAdoptionReceiptV1.model_validate(receipt.model_dump(mode="json"))
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("adoption_receipt_reload_validation")
    if reloaded.world_id != world_id:
        _integrity("adoption_receipt_identity_mismatch")
    return reloaded


def _peek_world_identity(raw: bytes) -> tuple[str | None, str | None]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    world_id = payload.get("world_id")
    adoption_id = payload.get("adoption_id")
    peeked_world = world_id if isinstance(world_id, str) and world_id.strip() else None
    peeked_adoption = adoption_id if isinstance(adoption_id, str) and adoption_id.strip() else None
    return peeked_world, peeked_adoption


def _unique(ids: list[str], *, field_name: str) -> None:
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            _integrity("duplicate_durable_id", field=field_name)
        seen.add(item)


def _source_maps(
    bundle: ExistingWorldAdoptionBundleV1,
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


def _validate_uniqueness(bundle: ExistingWorldAdoptionBundleV1) -> None:
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


def _validate_world_binding(bundle: ExistingWorldAdoptionBundleV1) -> None:
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


def _validate_source_revision_closure(bundle: ExistingWorldAdoptionBundleV1) -> None:
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
    contribution: GraphContribution,
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
    assertion: GraphContributionAssertion
    for assertion in contribution.assertions:
        _require_source_closure(
            source_artifact_id=assertion.source_artifact_id,
            source_revision_id=assertion.source_revision_id,
            artifacts=artifacts,
            revisions=revisions,
            field_name="assertion",
        )


def _validate_bundle_closures(bundle: ExistingWorldAdoptionBundleV1) -> None:
    _validate_uniqueness(bundle)
    _validate_world_binding(bundle)
    _validate_source_revision_closure(bundle)
    artifacts, revisions = _source_maps(bundle)
    for contribution in bundle.contributions:
        _validate_contribution_source_closure(
            contribution, artifacts=artifacts, revisions=revisions
        )


def _validate_graph(
    bundle: ExistingWorldAdoptionBundleV1,
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
    command: ExistingWorldAdoptionCommandV1,
) -> ExistingWorldAdoptionCommandV1:
    """Reload one command and bind its caller-supplied hashes to the bundle.

    Repository adapters must invoke this before any replay, pristine-target,
    or mutation branch. Caller-minted digests cannot manufacture a receipt.
    """
    try:
        validated = ExistingWorldAdoptionCommandV1.model_validate(command.model_dump(mode="json"))
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("adoption_command_validation")
    bundle = validated.bundle
    expected_bundle_sha256 = sha256_bytes(existing_world_adoption_bundle_canonical_bytes(bundle))
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
) -> ExistingWorldAdoptionBundleV1:
    """Parse, canonicalize, and close one adoption bundle before mutation."""
    if not isinstance(raw_bundle, (bytes, bytearray)):
        _integrity("raw_bundle_not_bytes")
    raw = bytes(raw_bundle)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _integrity("raw_bundle_not_json")
    try:
        bundle = ExistingWorldAdoptionBundleV1.model_validate(payload)
    except (TypeError, ValidationError, ValueError):
        _integrity("bundle_shape_invalid")
    canonical = existing_world_adoption_bundle_canonical_bytes(bundle)
    if canonical != raw:
        _integrity("non_canonical_bundle_bytes")
    _validate_bundle_closures(bundle)
    _validate_graph(bundle, graph_reader)
    return bundle


def adopt_existing_world(
    raw_bundle: bytes,
    *,
    adopted_at: datetime,
    adoption_repository: ExistingWorldAdoptionRepository,
    graph_reader: GraphSnapshotReader,
) -> ExistingWorldAdoptionReceiptV1:
    """Adopt or exactly replay one existing-world migration bundle."""
    if not isinstance(raw_bundle, (bytes, bytearray)):
        _integrity("raw_bundle_not_bytes")
    raw = bytes(raw_bundle)
    bundle_sha256 = sha256_bytes(raw)
    peeked_world_id, peeked_adoption_id = _peek_world_identity(raw)

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
    try:
        command = ExistingWorldAdoptionCommandV1(
            bundle=bundle,
            bundle_sha256=bundle_sha256,
            expected_published_revision_id=expected_published_revision_id,
            graph_payload_sha256=graph_payload_sha256,
            requested_adopted_at=adopted_at,
        )
    except (TypeError, ValidationError, ValueError):
        _integrity("adoption_command_validation")

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
