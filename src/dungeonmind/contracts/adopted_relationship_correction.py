"""Closed wire records and server-only rule data for adopted relationship repair."""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from .adopted_assertion_withdrawal import AdoptedObjectWithdrawalEvidenceV1
from .base import DungeonMindModel
from .semantic_profile import SemanticProfileRef

CORRECT_ADOPTED_RELATIONSHIP_TOOL = "dungeonmind.correct_adopted_relationship"
Digest = str


class PredicateEndpointRuleV1(DungeonMindModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    predicate: str = Field(min_length=1)
    subject_kinds: tuple[str, ...] = Field(min_length=1)
    object_kinds: tuple[str, ...] = Field(min_length=1)


class RelationshipCorrectionRulesV1(DungeonMindModel):
    """Trusted constructor dependency; never a field in a correction request."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    profile_ref: SemanticProfileRef
    catalog_id: str = Field(min_length=1)
    catalog_version: str = Field(min_length=1)
    catalog_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    predicates: tuple[PredicateEndpointRuleV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        terms = [p.predicate for p in self.predicates]
        if len(terms) != len(set(terms)):
            raise ValueError("duplicate predicate policy")
        return self


class AdoptedRelationshipCorrectionCommandV1(DungeonMindModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal["dm_adopted_relationship_correction_command_v1"] = (
        "dm_adopted_relationship_correction_command_v1"
    )
    operation_id: str
    world_id: str
    adoption_id: str
    expected_parent_revision_id: str
    parent_payload_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    relationship_id: str
    relationship_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    old_evidence_bindings: tuple[AdoptedObjectWithdrawalEvidenceV1, ...] = Field(min_length=1)
    replacement_source_object_id: str
    replacement_source_object_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    replacement_target_object_id: str
    replacement_target_object_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    replacement_predicate: str
    replacement_evidence_bindings: tuple[AdoptedObjectWithdrawalEvidenceV1, ...] = Field(
        min_length=1
    )
    actor: str
    rationale: str
    requested_at: datetime

    @field_validator(
        "operation_id",
        "world_id",
        "adoption_id",
        "expected_parent_revision_id",
        "relationship_id",
        "replacement_source_object_id",
        "replacement_target_object_id",
        "replacement_predicate",
        "actor",
        "rationale",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("correction identity/rationale must be nonblank")
        return value

    @field_validator("requested_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("correction timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _distinct(self) -> Self:
        for bindings in (self.old_evidence_bindings, self.replacement_evidence_bindings):
            identifiers = [b.evidence_ref_id for b in bindings]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError("duplicate correction evidence binding")
        return self


class AdoptedRelationshipCorrectionReceiptV1(DungeonMindModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal["dm_adopted_relationship_correction_receipt_v1"] = (
        "dm_adopted_relationship_correction_receipt_v1"
    )
    command: AdoptedRelationshipCorrectionCommandV1
    request_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    adoption_receipt_fingerprint: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    rules_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    identity_history: tuple[dict[str, Any], ...]
    identity_history_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    published_revision_id: str
    published_payload_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    replacement_relationship_id: str
    replacement_relationship_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
