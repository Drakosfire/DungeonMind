"""Pure materialization of one finalized v2 review into a v6 graph payload.

This module is the ``dm_union_graph_v6`` counterpart of
``review_materialization.materialize_finalized_review``.  It owns payload
transformation only: it does not construct a revision, observe or advance a
graph head, call a repository, append identity decisions, or expose a
transport surface.

The v6 payload is assertion-scoped: every object, alias, summary, property,
aspect, and relationship carries ``dm_knowledge_assertion_metadata_v1``.  The
materializer derives that metadata from the reviewed v2 contribution's
assertions so the resulting payload reparses under the pinned semantic
profile and remains replay-consistent with the Buddy kernel's contribution
merge semantics (identity derivation, alias merge, evidence fallback,
non-mutating identity outcomes).
"""

from __future__ import annotations

import copy
import json
from typing import Any, NoReturn

from ..contracts.contribution import (
    AcceptanceState,
    GraphContributionAssertionV2,
)
from ..contracts.contribution_review import ContributionIdentityVerdictKind
from ..contracts.contribution_review_v2 import (
    NON_MUTATING_IDENTITY_OUTCOMES,
    REVIEWABLE_V2_ASSERTION_KINDS,
    ContributionReviewStateV2,
)
from ..contracts.evidence import EvidenceRefV2, EvidenceRole
from ..contracts.graph import StoredGraphRevision
from ..contracts.knowledge_assertion import (
    EpistemicKindV2,
    KnowledgeAssertionMetadataV1,
    TemporalScopeKind,
    TemporalScopeRefV1,
)
from ..contracts.vocabulary import CanonState
from ..domain.canonical import canonical_sha256
from ..domain.errors import ContributionMaterializationError
from .graph_snapshot import GRAPH_SCHEMA_V6, GraphSnapshotReader, ParsedGraphSnapshot
from .graph_snapshot_v4 import AliasAssertionV4Record
from .graph_snapshot_v6 import (
    GraphObjectV6Record,
    GraphRelationshipV6Record,
    UnionGraphV6Payload,
)
from .review_materialization import FinalizedReviewGraphMaterialization


def _fail(reason: str, **details: Any) -> NoReturn:
    raise ContributionMaterializationError(reason, details=details) from None


def _reload_state(state: ContributionReviewStateV2) -> ContributionReviewStateV2:
    try:
        return ContributionReviewStateV2.model_validate(state.model_dump(mode="json"))
    except Exception:
        _fail("state_reload_validation")


def _reload_parent(parent: StoredGraphRevision) -> StoredGraphRevision:
    try:
        reloaded = StoredGraphRevision.model_validate(parent.model_dump(mode="json"))
        actual_digest = canonical_sha256(reloaded.graph_payload)
    except Exception:
        _fail("parent_reload_validation")
    if actual_digest != reloaded.revision.graph_payload_sha256:
        _fail(
            "parent_binding_mismatch",
            parent_revision_id=reloaded.revision.revision_id,
        )
    return reloaded


def _parse_parent(
    parent: StoredGraphRevision,
    *,
    state: ContributionReviewStateV2,
    graph_reader: GraphSnapshotReader,
) -> tuple[UnionGraphV6Payload, ParsedGraphSnapshot]:
    record = state.record
    plan_ref = record.plan_ref
    revision = parent.revision
    if revision.graph_schema != GRAPH_SCHEMA_V6:
        _fail("unsupported_graph_schema", graph_schema=revision.graph_schema)
    if (
        revision.world_id != record.world_id
        or revision.revision_id != plan_ref.expected_parent_revision_id
        or revision.graph_schema != plan_ref.base_graph_schema
        or revision.graph_payload_sha256 != plan_ref.base_graph_payload_sha256
    ):
        _fail(
            "parent_binding_mismatch",
            parent_revision_id=revision.revision_id,
            expected_parent_revision_id=plan_ref.expected_parent_revision_id,
            graph_schema=revision.graph_schema,
        )
    try:
        typed_parent = UnionGraphV6Payload.model_validate(copy.deepcopy(parent.graph_payload))
    except Exception:
        _fail("parent_reload_validation", graph_schema=revision.graph_schema)
    # The materializer only rewrites payloads it can reproduce exactly; a
    # round-trip drift would make the child payload differ from the parent by
    # more than the intended mutations.
    if typed_parent.model_dump(mode="json") != parent.graph_payload:
        _fail(
            "parent_reload_validation",
            parent_revision_id=revision.revision_id,
            reason_detail="typed_round_trip_drift",
        )
    try:
        snapshot = graph_reader.parse(
            graph_schema=revision.graph_schema,
            graph_payload=copy.deepcopy(parent.graph_payload),
        )
    except Exception:
        _fail("parent_reload_validation", graph_schema=revision.graph_schema)
    if (
        snapshot.world_id != record.world_id
        or snapshot.graph_schema != plan_ref.base_graph_schema
        or snapshot.semantic_profile_ref != plan_ref.semantic_profile
    ):
        _fail(
            "parent_binding_mismatch",
            parent_revision_id=revision.revision_id,
            graph_schema=revision.graph_schema,
        )
    return typed_parent, snapshot


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


def _temporal_scope(assertion: GraphContributionAssertionV2) -> TemporalScopeRefV1:
    raw = assertion.temporal_scope
    if raw is None:
        return TemporalScopeRefV1(kind=TemporalScopeKind.UNKNOWN)
    try:
        return TemporalScopeRefV1.model_validate(raw)
    except Exception:
        _fail(
            "unsupported_temporal_scope",
            assertion_id=assertion.assertion_id,
        )


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


def _lift_evidence(
    assertion: GraphContributionAssertionV2,
) -> dict[str, EvidenceRefV2]:
    """Lift the assertion's v1 evidence refs to lossless v2 payload records."""
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
            _fail(
                "accepted_evidence_conflict",
                evidence_ref_id=ref.evidence_ref_id,
            )
        lifted[ref.evidence_ref_id] = record
    return lifted


def _fallback_evidence(
    assertion: GraphContributionAssertionV2,
    *,
    reviewed_contribution_id: str,
    reviewed_source_artifact_id: str | None,
    reviewed_source_revision_id: str | None,
    graph_object_id: str,
) -> EvidenceRefV2:
    """Synthesize contribution-scoped evidence, mirroring Buddy's merge fallback."""
    return EvidenceRefV2(
        evidence_ref_id=f"evidence:{reviewed_contribution_id}:{graph_object_id}",
        source_artifact_id=(
            assertion.source_artifact_id
            or reviewed_source_artifact_id
            or f"artifact:{reviewed_contribution_id}"
        ),
        source_revision_id=assertion.source_revision_id or reviewed_source_revision_id,
        source_domain_key="manual_seed",
        source_domain=None,
        evidence_role=EvidenceRole.SUPPORT,
        can_open_source=False,
        can_highlight_span=False,
        session_id=None,
        source_span_ref_id=None,
        locator=f"contribution/{reviewed_contribution_id}/{graph_object_id}",
        uri=None,
        source_locator=None,
        line_ref=None,
    )


def _assertion_evidence(
    assertion: GraphContributionAssertionV2,
    *,
    kind: str,
    reviewed_contribution_id: str,
    reviewed_source_artifact_id: str | None,
    reviewed_source_revision_id: str | None,
    graph_object_id: str,
) -> tuple[list[str], dict[str, EvidenceRefV2]]:
    """Evidence ids for one applied assertion plus any new payload records.

    Node/edge assertions without explicit evidence synthesize the same
    contribution-scoped fallback Buddy's merge creates.  Alias, attribute, and
    evidence_ref assertions must carry explicit evidence (Buddy's merge never
    synthesizes for them).
    """
    lifted = _lift_evidence(assertion)
    if lifted:
        return sorted(lifted), lifted
    if kind not in {"node", "edge"}:
        _fail(
            "accepted_assertion_missing_graph_evidence",
            assertion_id=assertion.assertion_id,
        )
    fallback = _fallback_evidence(
        assertion,
        reviewed_contribution_id=reviewed_contribution_id,
        reviewed_source_artifact_id=reviewed_source_artifact_id,
        reviewed_source_revision_id=reviewed_source_revision_id,
        graph_object_id=graph_object_id,
    )
    return [fallback.evidence_ref_id], {fallback.evidence_ref_id: fallback}


def _alias_record(
    assertion: GraphContributionAssertionV2,
    *,
    alias: str,
    assertion_id: str,
    evidence_ref_ids: list[str],
) -> AliasAssertionV4Record:
    return AliasAssertionV4Record(
        value=alias,
        assertion_metadata=_metadata(
            assertion,
            assertion_id=assertion_id,
            evidence_ref_ids=evidence_ref_ids,
            session_refs=[],
        ),
    )


class _V6Materialization:
    """Mutable typed-payload workspace for one v6 review materialization."""

    def __init__(
        self,
        *,
        state: ContributionReviewStateV2,
        parent_payload: UnionGraphV6Payload,
        parent_snapshot: ParsedGraphSnapshot,
    ) -> None:
        self.state = state
        self.record = state.record
        self.reviewed = state.reviewed_contribution
        self.parent_snapshot = parent_snapshot
        self.objects: dict[str, GraphObjectV6Record] = {
            record.object_id: record for record in parent_payload.objects
        }
        self.object_order: list[str] = [record.object_id for record in parent_payload.objects]
        self.relationships: dict[str, GraphRelationshipV6Record] = {
            record.relationship_id: record for record in parent_payload.relationships
        }
        self.relationship_order: list[str] = [
            record.relationship_id for record in parent_payload.relationships
        ]
        self.evidence: dict[str, EvidenceRefV2] = {
            record.evidence_ref_id: record for record in parent_payload.evidence_refs
        }
        self.evidence_order: list[str] = [
            record.evidence_ref_id for record in parent_payload.evidence_refs
        ]
        self.new_object_ids: list[str] = []
        self.new_relationship_ids: list[str] = []
        self.new_evidence_ids: list[str] = []
        self.created_object_ids: set[str] = set()
        self.updated_object_ids: set[str] = set()
        self.expected_relationship_ids: set[str] = set()
        self.expected_evidence_ids: set[str] = set()
        self.corrected_assertion_ids: set[str] = set()

    def _register_evidence(self, records: dict[str, EvidenceRefV2]) -> None:
        for evidence_ref_id in sorted(records):
            record = records[evidence_ref_id]
            existing = self.evidence.get(evidence_ref_id)
            if existing is not None:
                if existing != record:
                    _fail(
                        "accepted_evidence_conflict",
                        evidence_ref_id=evidence_ref_id,
                    )
                continue
            self.evidence[evidence_ref_id] = record
            self.new_evidence_ids.append(evidence_ref_id)
        self.expected_evidence_ids.update(records)

    def _verdict_for_target(self, target: str) -> ContributionIdentityVerdictKind | None:
        for proposal in self.record.identity_proposals:
            if proposal.target_object_id == target:
                for verdict in self.record.identity_verdicts:
                    if verdict.candidate_id == proposal.candidate_id:
                        return verdict.verdict
        return None

    def apply_node(self, assertion: GraphContributionAssertionV2) -> None:
        object_id = assertion.subject_object_id
        if object_id is None:
            _fail("orphan_accepted_assertion", assertion_id=assertion.assertion_id)
        value = _parse_value(assertion)
        verdict = self._verdict_for_target(object_id)
        existing = self.objects.get(object_id)
        if verdict is ContributionIdentityVerdictKind.CREATE_NEW and existing is not None:
            _fail("parent_binding_mismatch", object_id=object_id)
        if verdict is ContributionIdentityVerdictKind.CONFIRM_EXISTING and existing is None:
            _fail("parent_binding_mismatch", object_id=object_id)
        evidence_ids, evidence_records = _assertion_evidence(
            assertion,
            kind="node",
            reviewed_contribution_id=self.reviewed.contribution_id,
            reviewed_source_artifact_id=self.reviewed.source_artifact_id,
            reviewed_source_revision_id=self.reviewed.source_revision_id,
            graph_object_id=object_id,
        )
        self._register_evidence(evidence_records)
        if existing is None:
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
                if not alias_text.strip() or alias_text in seen_aliases:
                    continue
                seen_aliases.add(alias_text)
                alias_records.append(
                    _alias_record(
                        assertion,
                        alias=alias_text,
                        assertion_id=f"{assertion.assertion_id}:alias:{alias_text}",
                        evidence_ref_ids=evidence_ids,
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
                    session_refs=[],
                ),
                aliases=alias_records,
                summary=None,
                properties=[],
                aspects=[],
            )
            self.objects[object_id] = node
            self.new_object_ids.append(object_id)
            self.created_object_ids.add(object_id)
            return
        # Merge onto the existing object: additive aliases and evidence only;
        # kind/label are never rewritten (Buddy kernel merge semantics).
        merged_aliases = list(existing.aliases)
        known_aliases = {record.value for record in merged_aliases}
        for alias in value.get("aliases") or []:
            alias_text = str(alias)
            if not alias_text.strip() or alias_text in known_aliases:
                continue
            known_aliases.add(alias_text)
            merged_aliases.append(
                _alias_record(
                    assertion,
                    alias=alias_text,
                    assertion_id=f"{assertion.assertion_id}:alias:{alias_text}",
                    evidence_ref_ids=evidence_ids,
                )
            )
        merged_evidence = list(existing.assertion_metadata.evidence_ref_ids)
        for evidence_ref_id in evidence_ids:
            if evidence_ref_id not in merged_evidence:
                merged_evidence.append(evidence_ref_id)
        self.objects[object_id] = existing.model_copy(
            update={
                "aliases": merged_aliases,
                "assertion_metadata": existing.assertion_metadata.model_copy(
                    update={"evidence_ref_ids": merged_evidence}
                ),
            }
        )
        self.updated_object_ids.add(object_id)

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
        evidence_ids, evidence_records = _assertion_evidence(
            assertion,
            kind="edge",
            reviewed_contribution_id=self.reviewed.contribution_id,
            reviewed_source_artifact_id=self.reviewed.source_artifact_id,
            reviewed_source_revision_id=self.reviewed.source_revision_id,
            graph_object_id=relationship_id,
        )
        existing = self.relationships.get(relationship_id)
        if existing is not None:
            if (
                existing.source_object_id == subject
                and existing.target_object_id == target
                and existing.predicate == qualified_predicate
            ):
                # Exact duplicate: replay-safe no-op (Buddy merge semantics).
                return
            _fail(
                "relationship_id_collision",
                relationship_id=relationship_id,
            )
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
                session_refs=[],
            ),
            source_aspect_assertion_id=None,
            target_aspect_assertion_id=None,
        )
        self.relationships[relationship_id] = record
        self.new_relationship_ids.append(relationship_id)
        self.expected_relationship_ids.add(relationship_id)

    def apply_alias(self, assertion: GraphContributionAssertionV2) -> None:
        object_id = assertion.subject_object_id
        if object_id is None:
            _fail("orphan_accepted_assertion", assertion_id=assertion.assertion_id)
        value = _parse_value(assertion)
        alias = assertion.label or value.get("alias")
        if not isinstance(alias, str) or not alias.strip():
            _fail("unsupported_field_shape", assertion_id=assertion.assertion_id)
        existing = self.objects.get(object_id)
        if existing is None:
            _fail("orphan_accepted_assertion", assertion_id=assertion.assertion_id)
        if alias in {record.value for record in existing.aliases}:
            return  # exact duplicate: replay-safe no-op
        evidence_ids, evidence_records = _assertion_evidence(
            assertion,
            kind="alias",
            reviewed_contribution_id=self.reviewed.contribution_id,
            reviewed_source_artifact_id=self.reviewed.source_artifact_id,
            reviewed_source_revision_id=self.reviewed.source_revision_id,
            graph_object_id=object_id,
        )
        self._register_evidence(evidence_records)
        merged_aliases = [
            *existing.aliases,
            _alias_record(
                assertion,
                alias=alias,
                assertion_id=assertion.assertion_id,
                evidence_ref_ids=evidence_ids,
            ),
        ]
        # Buddy's alias merge also extends the object's retained evidence.
        merged_evidence = list(existing.assertion_metadata.evidence_ref_ids)
        for evidence_ref_id in evidence_ids:
            if evidence_ref_id not in merged_evidence:
                merged_evidence.append(evidence_ref_id)
        self.objects[object_id] = existing.model_copy(
            update={
                "aliases": merged_aliases,
                "assertion_metadata": existing.assertion_metadata.model_copy(
                    update={"evidence_ref_ids": merged_evidence}
                ),
            }
        )
        self.updated_object_ids.add(object_id)

    def apply_evidence_only(self, assertion: GraphContributionAssertionV2) -> None:
        """Attribute/evidence_ref assertions materialize provenance only."""
        graph_object_id = assertion.subject_object_id or assertion.assertion_id
        _evidence_ids, evidence_records = _assertion_evidence(
            assertion,
            kind=assertion.assertion_kind,
            reviewed_contribution_id=self.reviewed.contribution_id,
            reviewed_source_artifact_id=self.reviewed.source_artifact_id,
            reviewed_source_revision_id=self.reviewed.source_revision_id,
            graph_object_id=graph_object_id,
        )
        self._register_evidence(evidence_records)

    def apply_corrections(self) -> None:
        for correction in self.reviewed.assertion_corrections:
            target_id = correction.target_assertion_id
            found = False
            for object_id in list(self.objects):
                record = self.objects[object_id]
                if record.assertion_metadata.assertion_id == target_id:
                    _fail(
                        "correction_target_existence",
                        assertion_id=target_id,
                        object_id=object_id,
                    )
                aliases = [
                    item
                    for item in record.aliases
                    if item.assertion_metadata.assertion_id != target_id
                ]
                summary = record.summary
                if summary is not None and summary.assertion_metadata.assertion_id == target_id:
                    summary = None
                properties = [
                    item
                    for item in record.properties
                    if item.assertion_metadata.assertion_id != target_id
                ]
                aspects = [
                    item
                    for item in record.aspects
                    if item.assertion_metadata.assertion_id != target_id
                ]
                changed = (
                    len(aliases) != len(record.aliases)
                    or summary is not record.summary
                    or len(properties) != len(record.properties)
                    or len(aspects) != len(record.aspects)
                )
                if changed:
                    found = True
                    self.objects[object_id] = record.model_copy(
                        update={
                            "aliases": aliases,
                            "summary": summary,
                            "properties": properties,
                            "aspects": aspects,
                        }
                    )
                    self.updated_object_ids.add(object_id)
            for relationship_id in list(self.relationships):
                record = self.relationships[relationship_id]
                if record.assertion_metadata.assertion_id == target_id:
                    del self.relationships[relationship_id]
                    self.relationship_order.remove(relationship_id)
                    found = True
            if not found:
                _fail(
                    "correction_target_unresolvable",
                    assertion_id=target_id,
                    contribution_id=correction.target_contribution_id,
                )
            self.corrected_assertion_ids.add(target_id)

    def result_payload(self, parent_payload: UnionGraphV6Payload) -> dict[str, Any]:
        payload = parent_payload.model_copy(
            update={
                "objects": [
                    self.objects[object_id]
                    for object_id in self.object_order
                    if object_id in self.objects
                ]
                + [self.objects[object_id] for object_id in sorted(self.new_object_ids)],
                "relationships": [
                    self.relationships[relationship_id]
                    for relationship_id in self.relationship_order
                ]
                + [
                    self.relationships[relationship_id]
                    for relationship_id in sorted(self.new_relationship_ids)
                ],
                "evidence_refs": [
                    self.evidence[evidence_ref_id] for evidence_ref_id in self.evidence_order
                ]
                + [
                    self.evidence[evidence_ref_id]
                    for evidence_ref_id in sorted(self.new_evidence_ids)
                ],
            }
        )
        return payload.model_dump(mode="json")


def materialize_finalized_review_v6(
    state: ContributionReviewStateV2,
    *,
    parent: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
) -> FinalizedReviewGraphMaterialization:
    """Materialize one finalized v2 review into one validated v6 graph payload."""
    verified_state = _reload_state(state)
    verified_parent = _reload_parent(parent)
    parent_payload, parent_snapshot = _parse_parent(
        verified_parent,
        state=verified_state,
        graph_reader=graph_reader,
    )
    record = verified_state.record
    plan_ref = record.plan_ref

    workspace = _V6Materialization(
        state=verified_state,
        parent_payload=parent_payload,
        parent_snapshot=parent_snapshot,
    )

    for assertion in verified_state.reviewed_contribution.assertions:
        if assertion.acceptance_state is not AcceptanceState.ACCEPTED:
            continue
        if assertion.identity_resolution_outcome in NON_MUTATING_IDENTITY_OUTCOMES:
            continue
        if assertion.assertion_kind not in REVIEWABLE_V2_ASSERTION_KINDS:
            _fail(
                "unsupported_assertion_kind",
                assertion_id=assertion.assertion_id,
                assertion_kind=assertion.assertion_kind,
            )
        if assertion.assertion_kind == "node":
            workspace.apply_node(assertion)
        elif assertion.assertion_kind == "edge":
            workspace.apply_edge(assertion)
        elif assertion.assertion_kind == "alias":
            workspace.apply_alias(assertion)
        else:
            workspace.apply_evidence_only(assertion)

    workspace.apply_corrections()

    payload = workspace.result_payload(parent_payload)
    try:
        output_snapshot = graph_reader.parse(
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=copy.deepcopy(payload),
        )
    except Exception:
        _fail("output_graph_validation")
    if (
        output_snapshot.world_id != record.world_id
        or output_snapshot.graph_schema != GRAPH_SCHEMA_V6
        or output_snapshot.semantic_profile_ref != plan_ref.semantic_profile
    ):
        _fail("output_graph_validation")
    for object_id in workspace.created_object_ids | workspace.updated_object_ids:
        if object_id not in output_snapshot.objects:
            _fail("output_graph_validation", object_id=object_id)
    for relationship_id in workspace.expected_relationship_ids:
        if relationship_id not in output_snapshot.relationships:
            _fail("output_graph_validation", relationship_id=relationship_id)
    for evidence_ref_id in workspace.expected_evidence_ids:
        if evidence_ref_id not in output_snapshot.evidence:
            _fail("output_graph_validation", evidence_ref_id=evidence_ref_id)
    for assertion_id in workspace.corrected_assertion_ids:
        for obj in output_snapshot.objects.values():
            if (
                obj.existence_assertion_metadata is not None
                and obj.existence_assertion_metadata.assertion_id == assertion_id
            ) or any(
                item.assertion_id == assertion_id
                for item in (
                    *obj.admitted_alias_assertions,
                    *obj.admitted_property_assertions,
                    *obj.admitted_aspect_assertions,
                    *(
                        [obj.admitted_summary_assertion]
                        if obj.admitted_summary_assertion is not None
                        else []
                    ),
                )
            ):
                _fail("output_graph_validation", corrected_assertion_id=assertion_id)
        if any(
            view.assertion_metadata is not None
            and view.assertion_metadata.assertion_id == assertion_id
            for view in output_snapshot.relationships.values()
        ):
            _fail("output_graph_validation", corrected_assertion_id=assertion_id)

    result_digest = canonical_sha256(payload)
    try:
        return FinalizedReviewGraphMaterialization(
            world_id=record.world_id,
            review_id=record.review_id,
            reviewed_contribution_id=record.reviewed_contribution_id,
            reviewed_contribution_sha256=record.reviewed_contribution_sha256,
            review_intent_sha256=record.review_intent_sha256,
            confirmation_id=record.confirmation_id,
            operation_id=record.operation_id,
            expected_parent_revision_id=plan_ref.expected_parent_revision_id,
            parent_graph_payload_sha256=plan_ref.base_graph_payload_sha256,
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload,
            graph_payload_sha256=result_digest,
        )
    except Exception:
        _fail("output_graph_validation")
