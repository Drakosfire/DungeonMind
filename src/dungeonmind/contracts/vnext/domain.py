"""Data-only domain and semantic-profile descriptors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ..base import DungeonMindModel
from .common import (
    DomainMetadataEntry,
    EpistemicBasis,
    JsonValue,
    KnowledgeStanding,
    NonBlankId,
    QualifiedTerm,
    ScopeBinding,
    Sha256Hex,
    TemporalScope,
    VisibilityRequirement,
    _json_value,
    _unique,
)


class DomainContractRef(DungeonMindModel):
    schema_version: Literal["dm_domain_contract_ref_v1"] = "dm_domain_contract_ref_v1"
    domain_id: NonBlankId
    domain_revision: NonBlankId
    descriptor_sha256: Sha256Hex


class DomainContractDescriptor(DungeonMindModel):
    schema_version: Literal["dm_domain_contract_v1"] = "dm_domain_contract_v1"
    domain_id: NonBlankId
    domain_revision: NonBlankId
    scope_axes: list[QualifiedTerm] = Field(default_factory=list)
    visibility_labels: list[QualifiedTerm] = Field(default_factory=list)
    claim_modes: list[QualifiedTerm] = Field(default_factory=list)
    temporal_extension_schemas: list[QualifiedTerm] = Field(default_factory=list)
    domain_metadata_schemas: list[QualifiedTerm] = Field(default_factory=list)
    source_annotation_schemas: list[QualifiedTerm] = Field(default_factory=list)
    admission_policy_id: NonBlankId

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
    profile_id: NonBlankId
    profile_revision: NonBlankId
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


class OpenPredicateNamespace(DungeonMindModel):
    """A profile-owned, type-constrained namespace for authored predicates."""

    namespace: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
    )
    allowed_value_kinds: list[Literal["entity_ref", "literal", "term_ref"]] = Field(
        min_length=1
    )

    @field_validator("allowed_value_kinds")
    @classmethod
    def _unique_kinds(cls, value: list[str]) -> list[str]:
        return _unique(value, "allowed_value_kinds")


class SemanticProfileDescriptorV3(SemanticProfileDescriptorV2):
    """Versioned predicate namespace admission without changing V2 meaning."""

    schema_version: Literal["dm_semantic_profile_v3"] = "dm_semantic_profile_v3"
    open_predicate_namespaces: list[OpenPredicateNamespace] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_open_namespaces(self) -> SemanticProfileDescriptorV3:
        namespaces = [item.namespace for item in self.open_predicate_namespaces]
        _unique(namespaces, "open_predicate_namespaces")
        if not set(namespaces).issubset(self.term_namespaces):
            raise ValueError("open predicate namespaces must be declared term namespaces")
        if any(item.term.split(":", 1)[0] in namespaces for item in self.predicates):
            raise ValueError("fixed predicates cannot share an open predicate namespace")
        return self


def parse_semantic_profile_descriptor(
    value: Mapping[str, Any],
) -> SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3:
    """Rehydrate the exact descriptor revision sealed by a KnowledgeRevision."""

    if value.get("schema_version") == "dm_semantic_profile_v3":
        return SemanticProfileDescriptorV3.model_validate(value)
    return SemanticProfileDescriptorV2.model_validate(value)


class Entity(DungeonMindModel):
    schema_version: Literal["dm_entity_v1"] = "dm_entity_v1"
    entity_id: NonBlankId


class EntityRefValue(DungeonMindModel):
    kind: Literal["entity_ref"] = "entity_ref"
    entity_id: NonBlankId


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
    evidence_ref_ids: list[NonBlankId] = Field(default_factory=list)
    temporal_scope: TemporalScope = Field(discriminator="kind")
    domain_metadata: list[DomainMetadataEntry] = Field(default_factory=list)

    @field_validator("evidence_ref_ids")
    @classmethod
    def _evidence(cls, value: list[str]) -> list[str]:
        return _unique(value, "evidence_ref_ids")


class Assertion(DungeonMindModel):
    schema_version: Literal["dm_assertion_v1"] = "dm_assertion_v1"
    assertion_id: NonBlankId
    subject_entity_id: NonBlankId
    predicate: QualifiedTerm
    value: EntityRefValue | LiteralValue | TermRefValue = Field(discriminator="kind")
    metadata: AssertionMetadata
