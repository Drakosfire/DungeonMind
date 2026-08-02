"""D&D Threat extraction candidate contracts.

Candidate packets are provenance-bearing, non-canonical, and non-publishable
proposals: temporary candidate identity only, a closed evidence ledger, and
explicit (unverified) existing-object references. They contain no stable
object IDs, no merge decisions, no confidence scores, no provider metadata,
and no arbitrary property bags. Catalog-dependent checks (exact term
membership, predicate direction, profile/vocabulary pin agreement) live in
``dungeonmind_dnd.application.threat_candidates``; these models enforce every
packet-internal invariant.
"""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from dungeonmind.contracts.base import DungeonMindModel
from dungeonmind.contracts.evidence import EvidenceRef
from dungeonmind.contracts.semantic_profile import SemanticProfileRef

from .vocabulary import DndVocabularyRef

NODE_CANDIDATE_SCHEMA = "dmdnd_node_candidate_v1"
RELATIONSHIP_CANDIDATE_SCHEMA = "dmdnd_relationship_candidate_v1"
THREAT_CANDIDATE_PACKET_SCHEMA = "dmdnd_threat_candidate_packet_v1"

# Threat is contextual: it is only ever the ``dnd5e:threatens`` relationship,
# never an object kind. These constants are D&D-package-owned vocabulary.
FORBIDDEN_THREAT_KIND = "dnd5e:threat"
REQUIRED_THREAT_PREDICATE = "dnd5e:threatens"

_QUALIFIED_TERM = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*:[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_GRAPH_ID_PREFIXES = ("obj:", "rel:")


def _normalize_surface_form(value: str) -> str:
    return " ".join(value.split()).casefold()


def _validate_candidate_id(value: str, *, field_name: str = "candidate_id") -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    if value.startswith(_GRAPH_ID_PREFIXES):
        raise ValueError(
            f"{field_name} is temporary candidate identity; it must not begin "
            "with 'obj:' or 'rel:'"
        )
    return value


def _validate_term_shape(value: str, *, field_name: str) -> str:
    if not _QUALIFIED_TERM.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a qualified namespace:local term "
            "(lowercase letters, digits, '.', '_', '-')"
        )
    return value


def _validate_evidence_ref_ids(value: list[str]) -> list[str]:
    if len(set(value)) != len(value):
        raise ValueError("evidence_ref_ids must be unique")
    for evidence_ref_id in value:
        if not evidence_ref_id.strip():
            raise ValueError("evidence_ref_ids entries must be non-empty")
    return value


class DndCandidateEndpointRef(DungeonMindModel):
    """One relationship endpoint: a packet candidate or an explicit,
    typed — but graph-unverified — existing object reference.

    Nested record; carries no schema_version of its own. Endpoint refs never
    contain labels, aliases, summaries, or copied graph objects.
    """

    candidate_id: str | None = None
    existing_object_id: str | None = None
    expected_kind: str | None = None

    @field_validator("candidate_id")
    @classmethod
    def _validate_candidate_id_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_candidate_id(value)

    @field_validator("existing_object_id")
    @classmethod
    def _validate_existing_object_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("existing_object_id must be non-empty")
        return value

    @field_validator("expected_kind")
    @classmethod
    def _validate_expected_kind(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_term_shape(value, field_name="expected_kind")

    @model_validator(mode="after")
    def _exactly_one_target_form(self) -> Self:
        is_candidate = self.candidate_id is not None
        is_existing = self.existing_object_id is not None
        if is_candidate == is_existing:
            raise ValueError(
                "exactly one of candidate_id / existing_object_id is required"
            )
        if is_candidate and self.expected_kind is not None:
            raise ValueError("candidate endpoints do not carry expected_kind")
        if is_existing and self.expected_kind is None:
            raise ValueError("existing object endpoints require expected_kind")
        return self

    def same_target(self, other: DndCandidateEndpointRef) -> bool:
        """True when both refs name the same candidate or existing object."""
        if self.candidate_id is not None and other.candidate_id is not None:
            return self.candidate_id == other.candidate_id
        if self.existing_object_id is not None and other.existing_object_id is not None:
            return self.existing_object_id == other.existing_object_id
        return False


class DndNodeCandidate(DungeonMindModel):
    """One proposed object. Temporary identity only — never graph identity."""

    schema_version: Literal["dmdnd_node_candidate_v1"] = NODE_CANDIDATE_SCHEMA
    candidate_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    label: str = Field(min_length=1)
    surface_forms: list[str] = Field(min_length=1)
    summary: str | None = None
    evidence_ref_ids: list[str] = Field(min_length=1)

    @field_validator("candidate_id")
    @classmethod
    def _validate_candidate_id_shape(cls, value: str) -> str:
        return _validate_candidate_id(value)

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        _validate_term_shape(value, field_name="kind")
        if value == FORBIDDEN_THREAT_KIND:
            raise ValueError(
                "Threat is a contextual dnd5e:threatens relationship, "
                "never an object kind"
            )
        return value

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("label must be non-empty")
        return value

    @field_validator("surface_forms")
    @classmethod
    def _validate_surface_forms(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        for form in value:
            normalized = _normalize_surface_form(form)
            if not normalized:
                raise ValueError("surface_forms entries must be non-empty")
            if normalized == FORBIDDEN_THREAT_KIND:
                raise ValueError(
                    "surface forms must not alias the forbidden dnd5e:threat kind"
                )
            if normalized in seen:
                raise ValueError("surface_forms must be unique after normalization")
            seen.add(normalized)
        return value

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("summary must be non-empty when present")
        return value

    @field_validator("evidence_ref_ids")
    @classmethod
    def _validate_evidence(cls, value: list[str]) -> list[str]:
        return _validate_evidence_ref_ids(value)


class DndRelationshipCandidate(DungeonMindModel):
    """One proposed directed relationship. Temporary identity only."""

    schema_version: Literal["dmdnd_relationship_candidate_v1"] = (
        RELATIONSHIP_CANDIDATE_SCHEMA
    )
    candidate_id: str = Field(min_length=1)
    subject: DndCandidateEndpointRef
    predicate: str = Field(min_length=1)
    object: DndCandidateEndpointRef
    evidence_ref_ids: list[str] = Field(min_length=1)

    @field_validator("candidate_id")
    @classmethod
    def _validate_candidate_id_shape(cls, value: str) -> str:
        return _validate_candidate_id(value)

    @field_validator("predicate")
    @classmethod
    def _validate_predicate(cls, value: str) -> str:
        return _validate_term_shape(value, field_name="predicate")

    @field_validator("evidence_ref_ids")
    @classmethod
    def _validate_evidence(cls, value: list[str]) -> list[str]:
        return _validate_evidence_ref_ids(value)

    @model_validator(mode="after")
    def _not_self_pointing(self) -> Self:
        if self.subject.same_target(self.object):
            raise ValueError("a relationship cannot point to itself")
        return self


class DndThreatCandidatePacket(DungeonMindModel):
    """One Threat-oriented extraction proposal over one source anchor.

    Non-canonical and non-publishable by construction: no stable IDs, no
    merge outcomes, no graph revision or contribution fields.
    """

    schema_version: Literal["dmdnd_threat_candidate_packet_v1"] = (
        THREAT_CANDIDATE_PACKET_SCHEMA
    )
    packet_id: str = Field(min_length=1)
    world_id: str = Field(min_length=1)
    campaign_id: str | None = None
    semantic_profile: SemanticProfileRef
    vocabulary: DndVocabularyRef
    source_artifact_id: str | None = None
    source_revision_id: str | None = None
    focus_evidence_ref_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(min_length=1)
    nodes: list[DndNodeCandidate] = Field(min_length=1)
    relationships: list[DndRelationshipCandidate] = Field(min_length=1)

    @field_validator("packet_id")
    @classmethod
    def _validate_packet_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("packet_id must be non-empty")
        return value

    @field_validator("world_id")
    @classmethod
    def _validate_world_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("world_id must be non-empty")
        return value

    @model_validator(mode="after")
    def _closed_candidate_and_evidence_ledger(self) -> Self:
        if self.source_revision_id is not None and self.source_artifact_id is None:
            raise ValueError("source_revision_id requires source_artifact_id")

        node_ids = [node.candidate_id for node in self.nodes]
        relationship_ids = [rel.candidate_id for rel in self.relationships]
        all_candidate_ids = node_ids + relationship_ids
        if len(set(all_candidate_ids)) != len(all_candidate_ids):
            raise ValueError("candidate IDs must be unique across nodes and relationships")
        node_by_id = {node.candidate_id: node for node in self.nodes}

        for rel in self.relationships:
            for endpoint in (rel.subject, rel.object):
                if endpoint.candidate_id is not None and (
                    endpoint.candidate_id not in node_by_id
                ):
                    raise ValueError(
                        f"candidate endpoint {endpoint.candidate_id} does not "
                        "resolve to a packet node"
                    )

        ledger_ids = [ref.evidence_ref_id for ref in self.evidence_refs]
        if len(set(ledger_ids)) != len(ledger_ids):
            raise ValueError("evidence_ref_id values must be unique within the ledger")
        ledger = set(ledger_ids)

        referenced: set[str] = set(self.focus_evidence_ref_ids)
        for node in self.nodes:
            referenced.update(node.evidence_ref_ids)
        for rel in self.relationships:
            referenced.update(rel.evidence_ref_ids)
        dangling = sorted(referenced - ledger)
        if dangling:
            raise ValueError(f"referenced evidence IDs missing from ledger: {dangling}")
        unused = sorted(ledger - referenced)
        if unused:
            raise ValueError(f"ledger evidence refs never referenced: {unused}")

        if self.source_artifact_id is not None:
            for ref in self.evidence_refs:
                if ref.source_artifact_id != self.source_artifact_id:
                    raise ValueError(
                        "evidence refs must agree with the packet source anchor"
                    )
        if self.source_revision_id is not None:
            for ref in self.evidence_refs:
                if ref.source_revision_id != self.source_revision_id:
                    raise ValueError(
                        "evidence refs must agree with the packet source anchor"
                    )

        focus = set(self.focus_evidence_ref_ids)
        connected: set[str] = set()
        for rel in self.relationships:
            for endpoint in (rel.subject, rel.object):
                if endpoint.candidate_id is not None:
                    connected.add(endpoint.candidate_id)
        for node in self.nodes:
            grounded = node.candidate_id in connected or bool(
                focus & set(node.evidence_ref_ids)
            )
            if not grounded:
                raise ValueError(
                    f"candidate node {node.candidate_id} is ungrounded: it "
                    "joins no relationship and holds no focus evidence"
                )

        if not any(rel.predicate == REQUIRED_THREAT_PREDICATE for rel in self.relationships):
            raise ValueError(
                "a Threat candidate packet requires at least one "
                f"{REQUIRED_THREAT_PREDICATE} relationship"
            )
        return self
