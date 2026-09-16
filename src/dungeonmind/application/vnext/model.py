"""The immutable, revision-local ParsedKnowledgeRevision model and structural indexes.

Provides O(1) indexed lookup over already-decoded vNext knowledge primitives without
performing scope/visibility admission or introducing domain/TTRPG concepts.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from .frozen_json import (
    FrozenDict,
    canonical_json_bytes,
    thaw_json_value,
)
from .records import (
    ParsedAssertion,
    ParsedDomainContractRef,
    ParsedDomainTemporalScope,
    ParsedEntity,
    ParsedEvidenceRef,
    ParsedIdentityAlias,
    ParsedKnowledgeRevisionIdentity,
    ParsedLabelsAllVisibility,
    ParsedLabelsAnyVisibility,
    ParsedMigrationOriginRef,
    ParsedPublicVisibility,
    ParsedSemanticProfileRef,
    ParsedUtcIntervalTemporalScope,
)

PARSED_REVISION_FORMAT_VERSION = "vnext_parsed_revision_v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class ParsedKnowledgeRevision:
    """An immutable, deterministic, revision-local representation of decoded vNext knowledge.

    All storage mappings and structural indexes are deeply immutable and fail closed
    against external mutation.
    """

    identity: ParsedKnowledgeRevisionIdentity

    # Primary storage mappings (keyed by stable ID)
    entities_by_id: FrozenDict[str, ParsedEntity]
    assertions_by_id: FrozenDict[str, ParsedAssertion]
    aliases_by_id: FrozenDict[str, ParsedIdentityAlias]
    evidence_by_id: FrozenDict[str, ParsedEvidenceRef]

    # Structural graph indexes
    assertions_by_subject: FrozenDict[str, tuple[str, ...]]
    entity_ref_outgoing: FrozenDict[str, tuple[str, ...]]
    entity_ref_incoming: FrozenDict[str, tuple[str, ...]]
    entity_ref_outgoing_assertions: FrozenDict[str, tuple[str, ...]]
    entity_ref_incoming_assertions: FrozenDict[str, tuple[str, ...]]
    entity_adjacency: FrozenDict[str, tuple[str, ...]]

    # Evidence & supporter indexes
    assertion_evidence: FrozenDict[str, tuple[str, ...]]
    evidence_supporters: FrozenDict[str, tuple[str, ...]]

    # Structural lookup indexes
    alias_exact_index: FrozenDict[str, tuple[str, ...]]
    literal_exact_index: FrozenDict[tuple[str, str], tuple[str, ...]]
    lexical_candidate_index: FrozenDict[str, tuple[str, ...]]

    # Computed digests
    semantic_digest: str
    compatibility_key: str
    format_version: str = PARSED_REVISION_FORMAT_VERSION

    # --- Header property shortcuts ---

    @property
    def space_id(self) -> str:
        return self.identity.space_id

    @property
    def revision_id(self) -> str:
        return self.identity.revision_id

    @property
    def parent_revision_id(self) -> str | None:
        return self.identity.parent_revision_id

    @property
    def created_at(self) -> datetime:
        return self.identity.created_at

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return self.identity.operation_ids

    @property
    def graph_schema(self) -> str:
        return self.identity.graph_schema

    @property
    def graph_payload_sha256(self) -> str:
        return self.identity.graph_payload_sha256

    @property
    def domain_contract_ref(self) -> ParsedDomainContractRef:
        return self.identity.domain_contract_ref

    @property
    def semantic_profile_ref(self) -> ParsedSemanticProfileRef:
        return self.identity.semantic_profile_ref

    @property
    def migration_origin_ref(self) -> ParsedMigrationOriginRef | None:
        return self.identity.migration_origin_ref

    # --- Ergonomic lookup helpers ---

    def get_entity(self, entity_id: str) -> ParsedEntity | None:
        return self.entities_by_id.get(entity_id)

    def get_assertion(self, assertion_id: str) -> ParsedAssertion | None:
        return self.assertions_by_id.get(assertion_id)

    def get_alias(self, alias_id: str) -> ParsedIdentityAlias | None:
        return self.aliases_by_id.get(alias_id)

    def get_evidence(self, evidence_ref_id: str) -> ParsedEvidenceRef | None:
        return self.evidence_by_id.get(evidence_ref_id)

    def get_subject_assertion_ids(self, entity_id: str) -> tuple[str, ...]:
        return self.assertions_by_subject.get(entity_id, ())

    def get_subject_assertions(self, entity_id: str) -> tuple[ParsedAssertion, ...]:
        asrt_ids = self.assertions_by_subject.get(entity_id, ())
        return tuple(self.assertions_by_id[aid] for aid in asrt_ids if aid in self.assertions_by_id)

    def get_outgoing_entity_ref_assertion_ids(self, entity_id: str) -> tuple[str, ...]:
        return self.entity_ref_outgoing_assertions.get(entity_id, ())

    def get_incoming_entity_ref_assertion_ids(self, entity_id: str) -> tuple[str, ...]:
        return self.entity_ref_incoming_assertions.get(entity_id, ())

    def get_adjacent_entities(self, entity_id: str) -> tuple[str, ...]:
        return self.entity_adjacency.get(entity_id, ())

    def get_evidence_supporters(self, evidence_ref_id: str) -> tuple[ParsedAssertion, ...]:
        asrt_ids = self.evidence_supporters.get(evidence_ref_id, ())
        return tuple(self.assertions_by_id[aid] for aid in asrt_ids if aid in self.assertions_by_id)

    def lookup_alias(self, alias_text: str) -> tuple[str, ...]:
        normalized = alias_text.strip().casefold()
        return self.alias_exact_index.get(normalized, ())

    def lookup_literal(self, predicate: str, canonical_json_text: str) -> tuple[str, ...]:
        return self.literal_exact_index.get((predicate, canonical_json_text), ())

    def lookup_lexical_candidates(self, token: str) -> tuple[str, ...]:
        normalized = token.strip().lower()
        return self.lexical_candidate_index.get(normalized, ())


def compute_semantic_digest(
    identity: ParsedKnowledgeRevisionIdentity,
    entities_by_id: dict[str, ParsedEntity],
    assertions_by_id: dict[str, ParsedAssertion],
    aliases_by_id: dict[str, ParsedIdentityAlias],
    evidence_by_id: dict[str, ParsedEvidenceRef],
) -> str:
    """Compute deterministic canonical digest over normalized semantic content."""
    normalized_entities = sorted(entities_by_id.keys())

    normalized_assertions = []
    for aid in sorted(assertions_by_id.keys()):
        a = assertions_by_id[aid]
        m = a.metadata
        vis: dict[str, object]
        if isinstance(m.visibility, ParsedPublicVisibility):
            vis = {"kind": "public"}
        elif isinstance(m.visibility, ParsedLabelsAnyVisibility):
            vis = {"kind": "labels_any", "labels": list(m.visibility.labels)}
        elif isinstance(m.visibility, ParsedLabelsAllVisibility):
            vis = {"kind": "labels_all", "labels": list(m.visibility.labels)}
        else:
            vis = {"kind": "unknown"}

        temporal: dict[str, object]
        if isinstance(m.temporal_scope, ParsedUtcIntervalTemporalScope):
            valid_from_iso = (
                m.temporal_scope.valid_from.isoformat()
                if m.temporal_scope.valid_from
                else None
            )
            valid_until_iso = (
                m.temporal_scope.valid_until.isoformat()
                if m.temporal_scope.valid_until
                else None
            )
            temporal = {
                "kind": "utc_interval",
                "valid_from": valid_from_iso,
                "valid_until": valid_until_iso,
            }
        elif isinstance(m.temporal_scope, ParsedDomainTemporalScope):
            temporal = {
                "kind": "domain_ref",
                "schema": m.temporal_scope.schema_term,
                "payload": thaw_json_value(m.temporal_scope.payload),
            }
        else:
            temporal = {"kind": m.temporal_scope.kind}

        val: dict[str, object]
        if a.value.kind == "entity_ref":
            val = {"kind": "entity_ref", "entity_id": a.value.entity_id}
        elif a.value.kind == "literal":
            val = {"kind": "literal", "value": thaw_json_value(a.value.value)}
        elif a.value.kind == "term_ref":
            val = {"kind": "term_ref", "term": a.value.term}
        else:
            val = {"kind": "unknown"}

        normalized_assertions.append({
            "assertion_id": a.assertion_id,
            "subject_entity_id": a.subject_entity_id,
            "predicate": a.predicate,
            "value": val,
            "metadata": {
                "scope": [{"axis": b.axis, "value": b.value} for b in m.scope],
                "visibility": vis,
                "epistemic_basis": m.epistemic_basis,
                "claim_mode": m.claim_mode,
                "standing": str(m.standing.value if hasattr(m.standing, "value") else m.standing),
                "evidence_ref_ids": list(m.evidence_ref_ids),
                "temporal_scope": temporal,
                "domain_metadata": [
                    {"schema": dm.schema_term, "payload": thaw_json_value(dm.payload)}
                    for dm in m.domain_metadata
                ],
            },
        })

    normalized_aliases = []
    for al_id in sorted(aliases_by_id.keys()):
        al = aliases_by_id[al_id]
        normalized_aliases.append({
            "alias_id": al.alias_id,
            "entity_id": al.entity_id,
            "alias_text": al.alias_text,
            "evidence_ref_ids": list(al.evidence_ref_ids),
            "standing": str(al.standing.value if hasattr(al.standing, "value") else al.standing),
        })

    normalized_evidence = []
    for ev_id in sorted(evidence_by_id.keys()):
        ev = evidence_by_id[ev_id]
        normalized_evidence.append({
            "evidence_ref_id": ev.evidence_ref_id,
            "source_artifact_id": ev.source_artifact_id,
            "source_revision_id": ev.source_revision_id,
            "evidence_role": ev.evidence_role,
            "can_open_source": ev.can_open_source,
            "can_highlight_span": ev.can_highlight_span,
            "locator": ev.locator,
            "uri": ev.uri,
            "source_locator": ev.source_locator,
            "line_ref": ev.line_ref,
            "source_span_ref_id": ev.source_span_ref_id,
            "domain_metadata": [
                {"schema": dm.schema_term, "payload": thaw_json_value(dm.payload)}
                for dm in ev.domain_metadata
            ],
        })

    payload = {
        "space_id": identity.space_id,
        "domain_contract_ref": {
            "domain_id": identity.domain_contract_ref.domain_id,
            "domain_revision": identity.domain_contract_ref.domain_revision,
            "descriptor_sha256": identity.domain_contract_ref.descriptor_sha256,
        },
        "semantic_profile_ref": {
            "profile_id": identity.semantic_profile_ref.profile_id,
            "profile_revision": identity.semantic_profile_ref.profile_revision,
            "descriptor_sha256": identity.semantic_profile_ref.descriptor_sha256,
        },
        "entities": normalized_entities,
        "assertions": normalized_assertions,
        "aliases": normalized_aliases,
        "evidence": normalized_evidence,
    }
    return _sha256(canonical_json_bytes(payload))


def compute_compatibility_key(identity: ParsedKnowledgeRevisionIdentity) -> str:
    """Compute compatibility key covering format version, graph schema, and pinned ref IDs."""
    payload = {
        "format_version": PARSED_REVISION_FORMAT_VERSION,
        "graph_schema": identity.graph_schema,
        "domain_contract_ref": {
            "domain_id": identity.domain_contract_ref.domain_id,
            "domain_revision": identity.domain_contract_ref.domain_revision,
            "descriptor_sha256": identity.domain_contract_ref.descriptor_sha256,
        },
        "semantic_profile_ref": {
            "profile_id": identity.semantic_profile_ref.profile_id,
            "profile_revision": identity.semantic_profile_ref.profile_revision,
            "descriptor_sha256": identity.semantic_profile_ref.descriptor_sha256,
        },
    }
    return _sha256(canonical_json_bytes(payload))
