"""Reviewed first-world initialization: validation, v6 materialization, and UoW.

The command is reviewed-fact authority. This module materializes a strict empty
``dm_union_graph_v6`` value from accepted node/edge assertions, then the
application service probes the durable receipt before any mutation. Adapters
own the atomic store transaction.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, NoReturn

from pydantic import ValidationError

from ..contracts.contribution import (
    AcceptanceState,
    ContributionStatus,
    GraphContributionAssertionV2,
    GraphContributionV2,
)
from ..contracts.contribution_review_v2 import (
    contribution_v2_payload_sha256,
)
from ..contracts.evidence import EvidenceRefV2, EvidenceRole, SourceArtifactV2, SourceRevision
from ..contracts.identity import IdentityOutcome
from ..contracts.knowledge_assertion import (
    EpistemicKindV2,
    KnowledgeAssertionMetadataV1,
    TemporalScopeKind,
    TemporalScopeRefV1,
)
from ..contracts.reviewed_world_initialization import (
    REVIEWED_WORLD_INITIALIZATION_COMMAND_SCHEMA,
    REVIEWED_WORLD_INITIALIZATION_RECEIPT_SCHEMA,
    ReviewedWorldInitializationCommandV1,
    ReviewedWorldInitializationReceiptV1,
)
from ..contracts.vocabulary import CanonState
from ..domain.canonical import canonical_json, canonical_sha256
from ..domain.errors import (
    ContributionMaterializationError,
    DungeonMindError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    ReviewedWorldInitializationOutcomeUnknownError,
)
from ..domain.revision_ids import compute_revision_id
from .graph_snapshot import GRAPH_SCHEMA_V6, GraphSnapshotReader
from .graph_snapshot_v4 import AliasAssertionV4Record
from .graph_snapshot_v6 import (
    GraphObjectV6Record,
    GraphRelationshipV6Record,
    UnionGraphV6Payload,
)
from .repositories import ReviewedWorldInitializationRepository

_MECHANICS_BINDING_PREDICATE = "uses_statblock"
_MECHANICS_BINDING_VALUE_KEYS = frozenset({"threat_statblock_binding", "statblock_binding"})
_MATERIALIZABLE_KINDS = frozenset({"node", "edge"})
_REJECTED_EXISTING_IDENTITY = frozenset(
    {
        IdentityOutcome.RESOLVED_EXISTING,
        "confirm_existing",
    }
)


def _integrity(reason: str, **details: Any) -> NoReturn:
    raise PersistenceIntegrityError(
        "reviewed-world initialization failed persistence-integrity validation",
        details={"reason": reason, **details},
    ) from None


def _fail(reason: str, **details: Any) -> NoReturn:
    raise ContributionMaterializationError(reason, details=details) from None


@dataclass(frozen=True, init=False)
class FirstWorldMaterialization:
    """Ephemeral first-world payload with copy-on-read graph bytes."""

    world_id: str
    initialization_id: str
    reviewed_contribution_id: str
    reviewed_contribution_sha256: str
    graph_schema: str
    graph_payload_sha256: str
    accepted_assertion_ids: tuple[str, ...]
    _graph_payload_json: str = field(repr=False)

    def __init__(
        self,
        world_id: str,
        initialization_id: str,
        reviewed_contribution_id: str,
        reviewed_contribution_sha256: str,
        graph_schema: str,
        graph_payload: dict[str, Any],
        graph_payload_sha256: str,
        accepted_assertion_ids: tuple[str, ...],
    ) -> None:
        payload = copy.deepcopy(graph_payload)
        if graph_schema != GRAPH_SCHEMA_V6:
            raise ValueError("first-world materialization requires dm_union_graph_v6")
        if canonical_sha256(payload) != graph_payload_sha256:
            raise ValueError("first-world materialization payload digest does not match")
        object.__setattr__(self, "world_id", world_id)
        object.__setattr__(self, "initialization_id", initialization_id)
        object.__setattr__(self, "reviewed_contribution_id", reviewed_contribution_id)
        object.__setattr__(
            self, "reviewed_contribution_sha256", reviewed_contribution_sha256
        )
        object.__setattr__(self, "graph_schema", graph_schema)
        object.__setattr__(self, "graph_payload_sha256", graph_payload_sha256)
        object.__setattr__(self, "accepted_assertion_ids", accepted_assertion_ids)
        object.__setattr__(self, "_graph_payload_json", canonical_json(payload))

    @property
    def graph_payload(self) -> dict[str, Any]:
        """Return a fresh JSON-compatible copy that cannot mutate this result."""
        return json.loads(self._graph_payload_json)


def reviewed_world_initialization_command_sha256(
    command: ReviewedWorldInitializationCommandV1,
) -> str:
    """Digest every semantic command field. The command model has no digest field."""
    return canonical_sha256(command.model_dump(mode="json"))


def bind_reviewed_world_initialization_command(
    command: ReviewedWorldInitializationCommandV1,
) -> ReviewedWorldInitializationCommandV1:
    """Reload one command before replay, pristine-target, or mutation."""
    schema = getattr(command, "schema_version", None)
    if schema != REVIEWED_WORLD_INITIALIZATION_COMMAND_SCHEMA:
        _integrity("unsupported_initialization_command_schema")
    try:
        return ReviewedWorldInitializationCommandV1.model_validate(
            command.model_dump(mode="json")
        )
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("initialization_command_validation")


def _reload_receipt(
    receipt: ReviewedWorldInitializationReceiptV1, *, world_id: str
) -> ReviewedWorldInitializationReceiptV1:
    schema = getattr(receipt, "schema_version", None)
    if schema != REVIEWED_WORLD_INITIALIZATION_RECEIPT_SCHEMA:
        _integrity("unsupported_initialization_receipt_schema")
    try:
        reloaded = ReviewedWorldInitializationReceiptV1.model_validate(
            receipt.model_dump(mode="json")
        )
    except (AttributeError, TypeError, ValidationError, ValueError):
        _integrity("initialization_receipt_reload_validation")
    if reloaded.world_id != world_id:
        _integrity("initialization_receipt_identity_mismatch")
    return reloaded


def _unique(ids: list[str], *, field_name: str) -> None:
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            _integrity("duplicate_durable_id", field=field_name)
        seen.add(item)


def _source_maps(
    artifacts: list[SourceArtifactV2],
    revisions: list[SourceRevision],
) -> tuple[dict[str, SourceArtifactV2], dict[str, SourceRevision]]:
    artifact_map = {artifact.source_artifact_id: artifact for artifact in artifacts}
    revision_map = {revision.source_revision_id: revision for revision in revisions}
    return artifact_map, revision_map


def _resolve_command_source(
    *,
    source_artifact_id: str | None,
    source_revision_id: str | None,
    artifacts: dict[str, SourceArtifactV2],
    revisions: dict[str, SourceRevision],
    field_name: str,
) -> tuple[str | None, str | None]:
    """Return the command-owned (artifact, revision) pair, deriving artifact from revision."""
    if source_artifact_id is None and source_revision_id is None:
        return None, None
    if source_revision_id is not None:
        revision = revisions.get(source_revision_id)
        if revision is None:
            _integrity("source_revision_not_in_command", field=field_name)
        assert revision is not None
        proven_artifact = revision.source_artifact_id
        if proven_artifact not in artifacts:
            _integrity("source_revision_artifact_not_in_command", field=field_name)
        if source_artifact_id is not None and source_artifact_id != proven_artifact:
            _integrity("source_revision_artifact_mismatch", field=field_name)
        return proven_artifact, source_revision_id
    if source_artifact_id not in artifacts:
        _integrity("source_artifact_not_in_command", field=field_name)
    return source_artifact_id, None


def _is_existing_identity(outcome: IdentityOutcome | str | None) -> bool:
    if outcome in _REJECTED_EXISTING_IDENTITY:
        return True
    return outcome is not None and getattr(outcome, "value", outcome) == "confirm_existing"


def _is_materializable(assertion: GraphContributionAssertionV2) -> bool:
    return (
        assertion.acceptance_state is AcceptanceState.ACCEPTED
        and assertion.assertion_kind in _MATERIALIZABLE_KINDS
        and assertion.identity_resolution_outcome is IdentityOutcome.CREATED_NEW
    )


def validate_reviewed_world_initialization_command(
    command: ReviewedWorldInitializationCommandV1,
) -> None:
    """Fail closed on first-world identity, source closure, and contribution rules."""
    contribution = command.reviewed_contribution
    if contribution.world_id != command.world_id:
        _integrity("world_id_drift", field="reviewed_contribution")
    if contribution.status is not ContributionStatus.ACTIVE:
        _integrity("contribution_not_active")
    if contribution.identity_decision_ids:
        _integrity("identity_decision_ids_not_empty")
    if contribution.assertion_corrections:
        _integrity("assertion_corrections_not_empty")
    if contribution.supersedes_contribution_id is not None:
        _integrity("supersedes_prior_contribution")

    artifacts = command.source_artifacts
    revisions = command.source_revisions
    _unique([item.source_artifact_id for item in artifacts], field_name="source_artifact_id")
    _unique([item.source_revision_id for item in revisions], field_name="source_revision_id")
    _unique(
        [item.assertion_id for item in contribution.assertions],
        field_name="assertion_id",
    )
    artifact_map, revision_map = _source_maps(artifacts, revisions)
    for artifact in artifacts:
        if artifact.world_id != command.world_id:
            _integrity("world_id_drift", field="source_artifact")
        current = artifact.current_revision_id
        if current is None:
            continue
        revision = revision_map.get(current)
        if revision is None:
            _integrity("artifact_current_revision_missing")
        if revision.source_artifact_id != artifact.source_artifact_id:
            _integrity("artifact_current_revision_owner_mismatch")
    for revision in revisions:
        if revision.source_artifact_id not in artifact_map:
            _integrity("revision_artifact_missing")

    referenced_artifacts: set[str] = set()
    referenced_revisions: set[str] = set()

    def _note_source(artifact_id: str | None, revision_id: str | None) -> None:
        if artifact_id is not None:
            referenced_artifacts.add(artifact_id)
        if revision_id is not None:
            referenced_revisions.add(revision_id)

    _note_source(
        *_resolve_command_source(
            source_artifact_id=contribution.source_artifact_id,
            source_revision_id=contribution.source_revision_id,
            artifacts=artifact_map,
            revisions=revision_map,
            field_name="contribution",
        )
    )
    created_object_ids: set[str] = set()
    materializable: list[GraphContributionAssertionV2] = []
    for assertion in contribution.assertions:
        _note_source(
            *_resolve_command_source(
                source_artifact_id=assertion.source_artifact_id,
                source_revision_id=assertion.source_revision_id,
                artifacts=artifact_map,
                revisions=revision_map,
                field_name="assertion",
            )
        )
        for ref in assertion.evidence_refs:
            _note_source(
                *_resolve_command_source(
                    source_artifact_id=ref.source_artifact_id,
                    source_revision_id=ref.source_revision_id,
                    artifacts=artifact_map,
                    revisions=revision_map,
                    field_name="evidence_ref",
                )
            )
        if assertion.acceptance_state is not AcceptanceState.ACCEPTED:
            continue
        outcome = assertion.identity_resolution_outcome
        if assertion.assertion_kind in _MATERIALIZABLE_KINDS:
            if _is_existing_identity(outcome):
                _integrity(
                    "accepted_resolved_existing",
                    assertion_id=assertion.assertion_id,
                )
            if outcome is not IdentityOutcome.CREATED_NEW:
                _integrity(
                    "accepted_identity_not_create_new",
                    assertion_id=assertion.assertion_id,
                    identity_resolution_outcome=(
                        outcome.value if outcome is not None else None
                    ),
                )
        if assertion.assertion_kind not in _MATERIALIZABLE_KINDS:
            _integrity(
                "unsupported_accepted_assertion_kind",
                assertion_id=assertion.assertion_id,
                assertion_kind=assertion.assertion_kind,
            )
        materializable.append(assertion)
        if assertion.assertion_kind == "node":
            object_id = assertion.subject_object_id
            if object_id is None or not object_id.strip():
                _integrity("orphan_accepted_assertion", assertion_id=assertion.assertion_id)
            if object_id in created_object_ids:
                _integrity("duplicate_subject_object_id", object_id=object_id)
            created_object_ids.add(object_id)
    if not materializable:
        _integrity("no_accepted_materializable_assertion")
    for assertion in materializable:
        if assertion.assertion_kind != "edge":
            continue
        subject = assertion.subject_object_id
        target = assertion.object_object_id
        if subject not in created_object_ids or target not in created_object_ids:
            _integrity(
                "accepted_edge_missing_endpoint",
                assertion_id=assertion.assertion_id,
            )
    for artifact in artifacts:
        if artifact.source_artifact_id not in referenced_artifacts:
            _integrity(
                "unreferenced_source_artifact",
                source_artifact_id=artifact.source_artifact_id,
            )
    for revision in revisions:
        if revision.source_revision_id not in referenced_revisions:
            _integrity(
                "unreferenced_source_revision",
                source_revision_id=revision.source_revision_id,
            )


def _parse_value(assertion: GraphContributionAssertionV2) -> dict[str, Any]:
    if assertion.value is None:
        return {}
    try:
        parsed = json.loads(assertion.value)
    except (TypeError, ValueError):
        _fail(
            "unsupported_field_shape",
            assertion_id=assertion.assertion_id,
            field="value",
        )
    if not isinstance(parsed, dict):
        _fail(
            "unsupported_field_shape",
            assertion_id=assertion.assertion_id,
            field="value",
        )
    return parsed


def _session_refs(assertion: GraphContributionAssertionV2, value: dict[str, Any]) -> list[str]:
    raw = value.get("session_ids")
    if raw is None:
        return []
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        _fail(
            "unsupported_field_shape",
            assertion_id=assertion.assertion_id,
            field="session_ids",
        )
    return list(raw)


def _reject_mechanics_binding(assertion: GraphContributionAssertionV2) -> None:
    value = _parse_value(assertion)
    predicates = [assertion.predicate]
    qualified = value.get("dm_predicate")
    if isinstance(qualified, str):
        predicates.append(qualified)
    for predicate in predicates:
        if predicate and predicate.rsplit(":", 1)[-1] == _MECHANICS_BINDING_PREDICATE:
            _fail(
                "unsupported_assertion_kind",
                assertion_id=assertion.assertion_id,
                assertion_kind=assertion.assertion_kind,
                binding=_MECHANICS_BINDING_PREDICATE,
            )
    for key in sorted(_MECHANICS_BINDING_VALUE_KEYS):
        if key in value:
            _fail(
                "unsupported_assertion_kind",
                assertion_id=assertion.assertion_id,
                assertion_kind=assertion.assertion_kind,
                binding=key,
            )


def _temporal_scope(assertion: GraphContributionAssertionV2) -> TemporalScopeRefV1:
    raw = assertion.temporal_scope
    if raw is None:
        return TemporalScopeRefV1(kind=TemporalScopeKind.UNKNOWN)
    try:
        return TemporalScopeRefV1.model_validate(raw)
    except Exception:
        _fail("unsupported_temporal_scope", assertion_id=assertion.assertion_id)


def _metadata(
    assertion: GraphContributionAssertionV2,
    *,
    assertion_id: str,
    evidence_ref_ids: list[str],
    session_refs: list[str],
) -> KnowledgeAssertionMetadataV1:
    try:
        return KnowledgeAssertionMetadataV1(
            assertion_id=assertion_id,
            campaign_scope=assertion.campaign_scope,
            visibility=assertion.visibility,
            epistemic_kind=EpistemicKindV2(assertion.epistemic_kind.value),
            canon_state=CanonState.CANONICAL,
            evidence_ref_ids=evidence_ref_ids,
            session_refs=session_refs,
            temporal_scope=_temporal_scope(assertion),
        )
    except Exception:
        _fail(
            "unsupported_field_shape",
            assertion_id=assertion.assertion_id,
            field="assertion_metadata",
        )


def _lift_evidence(assertion: GraphContributionAssertionV2) -> dict[str, EvidenceRefV2]:
    lifted: dict[str, EvidenceRefV2] = {}
    for ref in assertion.evidence_refs:
        record = EvidenceRefV2(
            evidence_ref_id=ref.evidence_ref_id,
            source_artifact_id=ref.source_artifact_id,
            source_revision_id=ref.source_revision_id,
            source_domain_key=ref.source_domain.value,
            source_domain=ref.source_domain,
            evidence_role=ref.evidence_role,
            can_open_source=ref.can_open_source,
            can_highlight_span=ref.can_highlight_span,
            session_id=None,
            source_span_ref_id=None,
            locator=ref.locator,
            uri=ref.uri,
            source_locator=None,
            line_ref=None,
        )
        prior = lifted.get(ref.evidence_ref_id)
        if prior is not None and prior != record:
            _fail("accepted_evidence_conflict", evidence_ref_id=ref.evidence_ref_id)
        lifted[ref.evidence_ref_id] = record
    return lifted


def _fallback_source_identity(
    assertion: GraphContributionAssertionV2,
    *,
    contribution: GraphContributionV2,
    artifacts: dict[str, SourceArtifactV2],
    revisions: dict[str, SourceRevision],
) -> tuple[str, str]:
    """Derive fallback evidence source from the proven revision owner, or fail closed."""
    revision_id = assertion.source_revision_id or contribution.source_revision_id
    named_artifact_id = assertion.source_artifact_id or contribution.source_artifact_id
    if revision_id is not None:
        revision = revisions.get(revision_id)
        if revision is None:
            _fail(
                "source_revision_not_in_command",
                assertion_id=assertion.assertion_id,
            )
        proven_artifact_id = revision.source_artifact_id
        if named_artifact_id is not None and named_artifact_id != proven_artifact_id:
            _fail(
                "source_revision_artifact_mismatch",
                assertion_id=assertion.assertion_id,
            )
        if proven_artifact_id not in artifacts:
            _fail(
                "source_revision_artifact_not_in_command",
                assertion_id=assertion.assertion_id,
            )
        return proven_artifact_id, revision_id
    if named_artifact_id is None:
        _fail(
            "accepted_assertion_missing_source_identity",
            assertion_id=assertion.assertion_id,
        )
    artifact = artifacts.get(named_artifact_id)
    if artifact is None:
        _fail(
            "source_artifact_not_in_command",
            assertion_id=assertion.assertion_id,
        )
    current = artifact.current_revision_id
    if current is None or current not in revisions:
        _fail(
            "accepted_assertion_missing_source_revision",
            assertion_id=assertion.assertion_id,
        )
    if revisions[current].source_artifact_id != named_artifact_id:
        _fail(
            "source_revision_artifact_mismatch",
            assertion_id=assertion.assertion_id,
        )
    return named_artifact_id, current


def _fallback_evidence(
    assertion: GraphContributionAssertionV2,
    *,
    contribution: GraphContributionV2,
    artifacts: dict[str, SourceArtifactV2],
    revisions: dict[str, SourceRevision],
    graph_object_id: str,
) -> EvidenceRefV2:
    artifact_id, revision_id = _fallback_source_identity(
        assertion,
        contribution=contribution,
        artifacts=artifacts,
        revisions=revisions,
    )
    artifact = artifacts[artifact_id]
    domain = artifact.source_domain
    return EvidenceRefV2(
        evidence_ref_id=f"evidence:{contribution.contribution_id}:{graph_object_id}",
        source_artifact_id=artifact_id,
        source_revision_id=revision_id,
        source_domain_key=artifact.source_domain_key,
        source_domain=domain,
        evidence_role=EvidenceRole.SUPPORT,
        can_open_source=False,
        can_highlight_span=False,
        session_id=None,
        source_span_ref_id=None,
        locator=f"contribution/{contribution.contribution_id}/{graph_object_id}",
        uri=None,
        source_locator=None,
        line_ref=None,
    )


def _require_emitted_evidence_in_command(
    record: EvidenceRefV2,
    *,
    artifacts: dict[str, SourceArtifactV2],
    revisions: dict[str, SourceRevision],
) -> None:
    if record.source_revision_id is None:
        _fail(
            "emitted_evidence_missing_source_revision",
            evidence_ref_id=record.evidence_ref_id,
        )
    revision = revisions.get(record.source_revision_id)
    if revision is None:
        _fail(
            "emitted_evidence_source_revision_not_in_command",
            evidence_ref_id=record.evidence_ref_id,
        )
    if revision.source_artifact_id != record.source_artifact_id:
        _fail(
            "emitted_evidence_source_revision_artifact_mismatch",
            evidence_ref_id=record.evidence_ref_id,
        )
    if record.source_artifact_id not in artifacts:
        _fail(
            "emitted_evidence_source_artifact_not_in_command",
            evidence_ref_id=record.evidence_ref_id,
        )


def _assertion_evidence(
    assertion: GraphContributionAssertionV2,
    *,
    kind: str,
    contribution: GraphContributionV2,
    artifacts: dict[str, SourceArtifactV2],
    revisions: dict[str, SourceRevision],
    graph_object_id: str,
) -> tuple[list[str], dict[str, EvidenceRefV2]]:
    lifted = _lift_evidence(assertion)
    if lifted:
        for record in lifted.values():
            _require_emitted_evidence_in_command(
                record, artifacts=artifacts, revisions=revisions
            )
        return sorted(lifted), lifted
    if kind not in _MATERIALIZABLE_KINDS:
        _fail(
            "accepted_assertion_missing_graph_evidence",
            assertion_id=assertion.assertion_id,
        )
    fallback = _fallback_evidence(
        assertion,
        contribution=contribution,
        artifacts=artifacts,
        revisions=revisions,
        graph_object_id=graph_object_id,
    )
    _require_emitted_evidence_in_command(
        fallback, artifacts=artifacts, revisions=revisions
    )
    return [fallback.evidence_ref_id], {fallback.evidence_ref_id: fallback}


def _alias_record(
    assertion: GraphContributionAssertionV2,
    *,
    alias: str,
    assertion_id: str,
    evidence_ref_ids: list[str],
    session_refs: list[str],
) -> AliasAssertionV4Record:
    return AliasAssertionV4Record(
        value=alias,
        assertion_metadata=_metadata(
            assertion,
            assertion_id=assertion_id,
            evidence_ref_ids=evidence_ref_ids,
            session_refs=session_refs,
        ),
    )


class _FirstWorldWorkspace:
    """Mutable typed-payload workspace over an empty v6 value."""

    def __init__(
        self,
        *,
        contribution: GraphContributionV2,
        artifacts: dict[str, SourceArtifactV2],
        revisions: dict[str, SourceRevision],
    ) -> None:
        self.reviewed = contribution
        self.artifacts = artifacts
        self.revisions = revisions
        self.objects: dict[str, GraphObjectV6Record] = {}
        self.object_order: list[str] = []
        self.relationships: dict[str, GraphRelationshipV6Record] = {}
        self.relationship_order: list[str] = []
        self.evidence: dict[str, EvidenceRefV2] = {}
        self.evidence_order: list[str] = []
        self.expected_relationship_ids: set[str] = set()
        self.expected_evidence_ids: set[str] = set()

    def _register_evidence(self, records: dict[str, EvidenceRefV2]) -> None:
        for evidence_ref_id in sorted(records):
            record = records[evidence_ref_id]
            existing = self.evidence.get(evidence_ref_id)
            if existing is not None:
                if existing != record:
                    _fail("accepted_evidence_conflict", evidence_ref_id=evidence_ref_id)
                continue
            self.evidence[evidence_ref_id] = record
            self.evidence_order.append(evidence_ref_id)
        self.expected_evidence_ids.update(records)

    def apply_node(self, assertion: GraphContributionAssertionV2) -> None:
        object_id = assertion.subject_object_id
        if object_id is None:
            _fail("orphan_accepted_assertion", assertion_id=assertion.assertion_id)
        if object_id in self.objects:
            _fail("duplicate_subject_object_id", object_id=object_id)
        value = _parse_value(assertion)
        evidence_ids, evidence_records = _assertion_evidence(
            assertion,
            kind="node",
            contribution=self.reviewed,
            artifacts=self.artifacts,
            revisions=self.revisions,
            graph_object_id=object_id,
        )
        session_refs = _session_refs(assertion, value)
        self._register_evidence(evidence_records)
        kind = value.get("dm_kind")
        if not isinstance(kind, str) or not kind.strip():
            _fail(
                "missing_qualified_kind",
                assertion_id=assertion.assertion_id,
                object_id=object_id,
            )
        label = assertion.label or str(value.get("label") or object_id)
        alias_values = value.get("aliases")
        if not isinstance(alias_values, list) or not alias_values:
            alias_values = [label]
        alias_records: list[AliasAssertionV4Record] = []
        seen_aliases: set[str] = set()
        for alias in alias_values:
            alias_text = str(alias)
            if not alias_text.strip() or alias_text.casefold() in seen_aliases:
                continue
            seen_aliases.add(alias_text.casefold())
            alias_records.append(
                _alias_record(
                    assertion,
                    alias=alias_text,
                    assertion_id=f"{assertion.assertion_id}:alias:{alias_text}",
                    evidence_ref_ids=evidence_ids,
                    session_refs=session_refs,
                )
            )
        node = GraphObjectV6Record(
            object_id=object_id,
            kind=kind,
            label=label,
            assertion_metadata=_metadata(
                assertion,
                assertion_id=assertion.assertion_id,
                evidence_ref_ids=evidence_ids,
                session_refs=session_refs,
            ),
            aliases=alias_records,
            summary=None,
            properties=[],
            aspects=[],
        )
        self.objects[object_id] = node
        self.object_order.append(object_id)

    def apply_edge(self, assertion: GraphContributionAssertionV2) -> None:
        subject = assertion.subject_object_id
        target = assertion.object_object_id
        predicate = assertion.predicate
        if subject is None or target is None or predicate is None:
            _fail("orphan_accepted_assertion", assertion_id=assertion.assertion_id)
        value = _parse_value(assertion)
        relationship_id = value.get("edge_id") or f"edge:{subject}:{predicate}:{target}"
        if not isinstance(relationship_id, str) or not relationship_id.strip():
            _fail("unsupported_field_shape", assertion_id=assertion.assertion_id)
        qualified_predicate = value.get("dm_predicate")
        if not isinstance(qualified_predicate, str) or not qualified_predicate.strip():
            _fail(
                "missing_qualified_predicate",
                assertion_id=assertion.assertion_id,
                relationship_id=relationship_id,
            )
        if value.get("source_aspect_assertion_id") or value.get("target_aspect_assertion_id"):
            _fail(
                "unsupported_field_shape",
                assertion_id=assertion.assertion_id,
                field="endpoint_aspect",
            )
        if subject not in self.objects or target not in self.objects:
            _fail(
                "orphan_accepted_assertion",
                assertion_id=assertion.assertion_id,
                relationship_id=relationship_id,
            )
        if relationship_id in self.relationships:
            _fail("relationship_id_collision", relationship_id=relationship_id)
        evidence_ids, evidence_records = _assertion_evidence(
            assertion,
            kind="edge",
            contribution=self.reviewed,
            artifacts=self.artifacts,
            revisions=self.revisions,
            graph_object_id=relationship_id,
        )
        session_refs = _session_refs(assertion, value)
        self._register_evidence(evidence_records)
        record = GraphRelationshipV6Record(
            relationship_id=relationship_id,
            source_object_id=subject,
            target_object_id=target,
            predicate=qualified_predicate,
            assertion_metadata=_metadata(
                assertion,
                assertion_id=assertion.assertion_id,
                evidence_ref_ids=evidence_ids,
                session_refs=session_refs,
            ),
            source_aspect_assertion_id=None,
            target_aspect_assertion_id=None,
        )
        self.relationships[relationship_id] = record
        self.relationship_order.append(relationship_id)
        self.expected_relationship_ids.add(relationship_id)

    def result_payload(self, empty: UnionGraphV6Payload) -> dict[str, Any]:
        payload = empty.model_copy(
            update={
                "objects": [self.objects[object_id] for object_id in self.object_order],
                "relationships": [
                    self.relationships[relationship_id]
                    for relationship_id in self.relationship_order
                ],
                "evidence_refs": [
                    self.evidence[evidence_ref_id] for evidence_ref_id in self.evidence_order
                ],
            }
        )
        return payload.model_dump(mode="json")


def materialize_reviewed_world_initialization_v6(
    command: ReviewedWorldInitializationCommandV1,
    *,
    graph_reader: GraphSnapshotReader,
) -> FirstWorldMaterialization:
    """Materialize one reviewed first-world command into a validated v6 payload."""
    validated = bind_reviewed_world_initialization_command(command)
    validate_reviewed_world_initialization_command(validated)
    contribution = validated.reviewed_contribution
    try:
        empty = UnionGraphV6Payload(
            world_id=validated.world_id,
            semantic_profile=validated.semantic_profile,
        )
    except Exception:
        _fail("empty_graph_validation")
    workspace = _FirstWorldWorkspace(
        contribution=contribution,
        artifacts={item.source_artifact_id: item for item in validated.source_artifacts},
        revisions={item.source_revision_id: item for item in validated.source_revisions},
    )
    accepted_nodes = sorted(
        (
            assertion
            for assertion in contribution.assertions
            if _is_materializable(assertion) and assertion.assertion_kind == "node"
        ),
        key=lambda item: item.assertion_id,
    )
    accepted_edges = sorted(
        (
            assertion
            for assertion in contribution.assertions
            if _is_materializable(assertion) and assertion.assertion_kind == "edge"
        ),
        key=lambda item: item.assertion_id,
    )
    accepted_ids = tuple(item.assertion_id for item in (*accepted_nodes, *accepted_edges))
    for assertion in (*accepted_nodes, *accepted_edges):
        _reject_mechanics_binding(assertion)
        if assertion.assertion_kind == "node":
            workspace.apply_node(assertion)
        else:
            workspace.apply_edge(assertion)
    payload = workspace.result_payload(empty)
    try:
        output_snapshot = graph_reader.parse(
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=copy.deepcopy(payload),
        )
    except ContributionMaterializationError:
        raise
    except Exception:
        _fail("output_graph_validation")
    if (
        output_snapshot.world_id != validated.world_id
        or output_snapshot.graph_schema != GRAPH_SCHEMA_V6
        or output_snapshot.semantic_profile_ref != validated.semantic_profile
    ):
        _fail("output_graph_validation")
    for object_id in workspace.object_order:
        if object_id not in output_snapshot.objects:
            _fail("output_graph_validation", object_id=object_id)
    for relationship_id in workspace.expected_relationship_ids:
        if relationship_id not in output_snapshot.relationships:
            _fail("output_graph_validation", relationship_id=relationship_id)
    for evidence_ref_id in workspace.expected_evidence_ids:
        if evidence_ref_id not in output_snapshot.evidence:
            _fail("output_graph_validation", evidence_ref_id=evidence_ref_id)
    result_digest = canonical_sha256(payload)
    try:
        return FirstWorldMaterialization(
            world_id=validated.world_id,
            initialization_id=validated.initialization_id,
            reviewed_contribution_id=contribution.contribution_id,
            reviewed_contribution_sha256=contribution_v2_payload_sha256(contribution),
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload,
            graph_payload_sha256=result_digest,
            accepted_assertion_ids=accepted_ids,
        )
    except Exception:
        _fail("output_graph_validation")


def terminal_reviewed_world_initialization_receipt(
    command: ReviewedWorldInitializationCommandV1,
    *,
    command_sha256: str,
    materialization: FirstWorldMaterialization,
    published_revision_id: str,
) -> ReviewedWorldInitializationReceiptV1:
    """Build the terminal receipt for one bound initialization command."""
    try:
        return ReviewedWorldInitializationReceiptV1(
            initialization_id=command.initialization_id,
            world_id=command.world_id,
            campaign_id=command.campaign_id,
            source_plan_schema=command.source_plan_schema,
            source_plan_id=command.source_plan_id,
            source_plan_sha256=command.source_plan_sha256,
            command_sha256=command_sha256,
            reviewed_contribution_id=materialization.reviewed_contribution_id,
            reviewed_contribution_sha256=materialization.reviewed_contribution_sha256,
            published_revision_id=published_revision_id,
            published_graph_schema=GRAPH_SCHEMA_V6,
            published_graph_payload_sha256=materialization.graph_payload_sha256,
            accepted_assertion_ids=list(materialization.accepted_assertion_ids),
            actor=command.actor,
            initialized_at=command.requested_initialized_at,
        )
    except (TypeError, ValidationError, ValueError):
        _integrity("initialization_receipt_validation")


def _receipt_matches_command(
    receipt: ReviewedWorldInitializationReceiptV1,
    *,
    initialization_id: str,
    command_sha256: str,
) -> bool:
    return (
        receipt.initialization_id == initialization_id
        and receipt.command_sha256 == command_sha256
    )


def initialize_reviewed_world(
    command: ReviewedWorldInitializationCommandV1,
    *,
    initialization_repository: ReviewedWorldInitializationRepository,
    graph_reader: GraphSnapshotReader,
) -> ReviewedWorldInitializationReceiptV1:
    """Initialize or exactly replay one reviewed first-world command."""
    validated = bind_reviewed_world_initialization_command(command)
    command_sha256 = reviewed_world_initialization_command_sha256(validated)
    world_id = validated.world_id
    existing = initialization_repository.get_for_world(world_id)
    if existing is not None:
        if _receipt_matches_command(
            existing,
            initialization_id=validated.initialization_id,
            command_sha256=command_sha256,
        ):
            return _reload_receipt(existing, world_id=world_id)
        raise IdempotencyConflictError(
            "reviewed-world initialization identity conflicts with the requested command",
            details={
                "world_id": world_id,
                "initialization_id": existing.initialization_id,
                "command_sha256": command_sha256,
                "stored_command_sha256": existing.command_sha256,
            },
        )

    validate_reviewed_world_initialization_command(validated)
    materialization = materialize_reviewed_world_initialization_v6(
        validated, graph_reader=graph_reader
    )
    expected_published_revision_id = compute_revision_id(
        world_id=world_id,
        parent_revision_id=None,
        operation_ids=[validated.initialization_id],
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload_sha256=materialization.graph_payload_sha256,
    )
    try:
        receipt = initialization_repository.initialize(
            validated,
            graph_payload=materialization.graph_payload,
            graph_payload_sha256=materialization.graph_payload_sha256,
            accepted_assertion_ids=materialization.accepted_assertion_ids,
        )
        return _reload_receipt(receipt, world_id=world_id)
    except Exception as exc:
        try:
            recovered = initialization_repository.get_for_world(world_id)
            if recovered is not None and _receipt_matches_command(
                recovered,
                initialization_id=validated.initialization_id,
                command_sha256=command_sha256,
            ):
                return _reload_receipt(recovered, world_id=world_id)
        except Exception:
            pass
        if isinstance(exc, DungeonMindError) and not isinstance(
            exc, PersistenceUnavailableError
        ):
            raise
        raise ReviewedWorldInitializationOutcomeUnknownError(
            world_id=world_id,
            initialization_id=validated.initialization_id,
            command_sha256=command_sha256,
            expected_published_revision_id=expected_published_revision_id,
            reason="initialization_attempt_or_recovery_probe_failed",
        ) from None


def replay_conflict_if_present(
    receipt: ReviewedWorldInitializationReceiptV1 | None,
    *,
    initialization_id: str,
    command_sha256: str,
    world_id: str,
    other_world_receipt: Callable[[], ReviewedWorldInitializationReceiptV1 | None] | None = None,
) -> ReviewedWorldInitializationReceiptV1 | None:
    """Shared receipt-first probe used by adapters after ``lock_world``."""
    if receipt is not None:
        if _receipt_matches_command(
            receipt, initialization_id=initialization_id, command_sha256=command_sha256
        ):
            return receipt
        raise IdempotencyConflictError(
            "reviewed-world initialization identity conflicts with the requested command",
            details={
                "world_id": world_id,
                "initialization_id": receipt.initialization_id,
                "command_sha256": command_sha256,
                "stored_command_sha256": receipt.command_sha256,
            },
        )
    if other_world_receipt is not None:
        other = other_world_receipt()
        if other is not None:
            raise IdempotencyConflictError(
                f"initialization {initialization_id!r} already exists for another world"
            )
    return None
