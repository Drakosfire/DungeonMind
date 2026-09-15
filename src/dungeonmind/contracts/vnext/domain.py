"""Data-only domain and semantic-profile descriptors."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from ..base import DungeonMindModel
from .common import (
    DomainMetadataEntry,
    EpistemicBasis,
    JsonValue,
    KnowledgeStanding,
    QualifiedTerm,
    ScopeBinding,
    TemporalScope,
    VisibilityRequirement,
    _json_value,
    _unique,
)


class DomainContractRef(DungeonMindModel):
    schema_version: Literal["dm_domain_contract_ref_v1"] = "dm_domain_contract_ref_v1"
    domain_id: str = Field(min_length=1)
    domain_revision: str = Field(min_length=1)
    descriptor_sha256: str = Field(min_length=64, max_length=64)


class DomainContractDescriptor(DungeonMindModel):
    schema_version: Literal["dm_domain_contract_v1"] = "dm_domain_contract_v1"
    domain_id: str = Field(min_length=1)
    domain_revision: str = Field(min_length=1)
    scope_axes: list[QualifiedTerm] = Field(default_factory=list)
    visibility_labels: list[QualifiedTerm] = Field(default_factory=list)
    claim_modes: list[QualifiedTerm] = Field(default_factory=list)
    temporal_extension_schemas: list[QualifiedTerm] = Field(default_factory=list)
    domain_metadata_schemas: list[QualifiedTerm] = Field(default_factory=list)
    source_annotation_schemas: list[QualifiedTerm] = Field(default_factory=list)
    admission_policy_id: str = Field(min_length=1)

    @field_validator(
        "scope_axes",
        "visibility_labels",
        "claim_modes",
        "temporal_extension_schemas",
        "domain_metadata_schemas",
        "source_annotation_schemas",
    )
    @classmethod
    def _unique_terms(cls, value: list[str]) -> list[str]:
        return _unique(value, "descriptor terms")


class SemanticProfilePredicate(DungeonMindModel):
    term: QualifiedTerm
    allowed_value_kinds: list[Literal["entity_ref", "literal", "term_ref"]] = Field(min_length=1)
    literal_schema: JsonValue | None = None

    _literal = field_validator("literal_schema")(_json_value)

    @field_validator("allowed_value_kinds")
    @classmethod
    def _unique_kinds(cls, value: list[str]) -> list[str]:
        return _unique(value, "allowed_value_kinds")


class SemanticProfileDescriptorV2(DungeonMindModel):
    schema_version: Literal["dm_semantic_profile_v2"] = "dm_semantic_profile_v2"
    profile_id: str = Field(min_length=1)
    profile_revision: str = Field(min_length=1)
    term_namespaces: list[str] = Field(min_length=1)
    predicates: list[SemanticProfilePredicate] = Field(default_factory=list)
    classification_terms: list[QualifiedTerm] = Field(default_factory=list)

    @field_validator("term_namespaces")
    @classmethod
    def _namespaces(cls, value: list[str]) -> list[str]:
        if any(
            not item or ":" in item or any(c.isupper() or c.isspace() for c in item)
            for item in value
        ):
            raise ValueError("term_namespaces must be lowercase namespace names")
        return _unique(value, "term_namespaces")

    @field_validator("classification_terms")
    @classmethod
    def _unique_classification(cls, value: list[str]) -> list[str]:
        return _unique(value, "classification_terms")


class Entity(DungeonMindModel):
    schema_version: Literal["dm_entity_v1"] = "dm_entity_v1"
    entity_id: str = Field(min_length=1)


class EntityRefValue(DungeonMindModel):
    kind: Literal["entity_ref"] = "entity_ref"
    entity_id: str = Field(min_length=1)


class LiteralValue(DungeonMindModel):
    kind: Literal["literal"] = "literal"
    value: JsonValue
    _value = field_validator("value")(_json_value)


class TermRefValue(DungeonMindModel):
    kind: Literal["term_ref"] = "term_ref"
    term: QualifiedTerm


class AssertionMetadata(DungeonMindModel):
    scope: list[ScopeBinding] = Field(default_factory=list)
    visibility: VisibilityRequirement = Field(discriminator="kind")
    epistemic_basis: EpistemicBasis
    claim_mode: QualifiedTerm
    standing: KnowledgeStanding
    evidence_ref_ids: list[str] = Field(default_factory=list)
    temporal_scope: TemporalScope = Field(discriminator="kind")
    domain_metadata: list[DomainMetadataEntry] = Field(default_factory=list)

    @field_validator("evidence_ref_ids")
    @classmethod
    def _evidence(cls, value: list[str]) -> list[str]:
        return _unique(value, "evidence_ref_ids")


class Assertion(DungeonMindModel):
    schema_version: Literal["dm_assertion_v1"] = "dm_assertion_v1"
    assertion_id: str = Field(min_length=1)
    subject_entity_id: str = Field(min_length=1)
    predicate: QualifiedTerm
    value: EntityRefValue | LiteralValue | TermRefValue = Field(discriminator="kind")
    metadata: AssertionMetadata
