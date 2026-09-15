from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ..base import DungeonMindModel
from ..semantic_profile import SemanticProfileRef
from .common import KnowledgeStanding, _unique
from .domain import DomainContractRef


class IdentityDecisionKind(StrEnum):
    ALIAS_ADD = "alias_add"
    ALIAS_REMOVE = "alias_remove"
    MERGE = "merge"
    SPLIT = "split"
    UNMERGE = "unmerge"
    REJECT_CANDIDATE = "reject_candidate"
    MARK_AMBIGUOUS = "mark_ambiguous"
    HUMAN_OVERRIDE = "human_override"


class IdentityDecisionStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class MigrationOriginRef(DungeonMindModel):
    source_system: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    source_revision_id: str = Field(min_length=1)
    source_payload_sha256: str = Field(min_length=64, max_length=64)
    migration_manifest_sha256: str = Field(min_length=64, max_length=64)


class IdentityAlias(DungeonMindModel):
    schema_version: Literal["dm_identity_alias_v1"] = "dm_identity_alias_v1"
    alias_id: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    alias_text: str = Field(min_length=1)
    evidence_ref_ids: list[str] = Field(default_factory=list)
    standing: KnowledgeStanding
    _ids = field_validator("evidence_ref_ids")(_unique)


class IdentityDecisionV3(DungeonMindModel):
    schema_version: Literal["dm_identity_decision_v3"] = "dm_identity_decision_v3"
    decision_id: str = Field(min_length=1)
    space_id: str = Field(min_length=1)
    decision_kind: IdentityDecisionKind
    subject_entity_ids: list[str] = Field(min_length=1)
    target_entity_ids: list[str] = Field(default_factory=list)
    alias: str | None = None
    actor: str = "system"
    reason: str | None = None
    reversible: bool = True
    supersedes_decision_ids: list[str] = Field(default_factory=list)
    status: IdentityDecisionStatus = IdentityDecisionStatus.ACTIVE
    created_at: datetime

    @model_validator(mode="after")
    def _cardinality(self) -> IdentityDecisionV3:
        k, s, t = self.decision_kind, self.subject_entity_ids, self.target_entity_ids
        if (
            k in (IdentityDecisionKind.ALIAS_ADD, IdentityDecisionKind.ALIAS_REMOVE)
            and not self.alias
        ):
            raise ValueError(f"{k.value} requires alias")
        if k is IdentityDecisionKind.MERGE and (len(s) < 2 or len(t) != 1):
            raise ValueError("merge requires at least two subjects and one target")
        if k is IdentityDecisionKind.SPLIT and (len(s) != 1 or len(t) < 2):
            raise ValueError("split requires one subject and at least two targets")
        if k is IdentityDecisionKind.UNMERGE and not t:
            raise ValueError("unmerge requires targets")
        return self


class KnowledgeRevision(DungeonMindModel):
    schema_version: Literal["dm_knowledge_revision_v1"] = "dm_knowledge_revision_v1"
    space_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    parent_revision_id: str | None = None
    created_at: datetime
    operation_ids: list[str] = Field(min_length=1)
    graph_schema: str = Field(min_length=1)
    graph_payload_sha256: str = Field(min_length=64, max_length=64)
    domain_contract_ref: DomainContractRef
    semantic_profile_ref: SemanticProfileRef
    migration_origin_ref: MigrationOriginRef | None = None
    status: Literal["published"] = "published"
    _ops = field_validator("operation_ids")(_unique)


class KnowledgeHead(DungeonMindModel):
    schema_version: Literal["dm_knowledge_head_v1"] = "dm_knowledge_head_v1"
    space_id: str = Field(min_length=1)
    head_revision_id: str = Field(min_length=1)
    updated_at: datetime


class PublishKnowledgeRevisionCommand(DungeonMindModel):
    schema_version: Literal["dm_publish_knowledge_revision_command_v1"] = (
        "dm_publish_knowledge_revision_command_v1"
    )
    space_id: str = Field(min_length=1)
    parent_revision_id: str | None = None
    expected_parent_revision_id: str | None = None
    operation_ids: list[str] = Field(default_factory=list)
    graph_schema: str = Field(min_length=1)
    graph_payload: dict[str, object]
    domain_contract_ref: DomainContractRef
    semantic_profile_ref: SemanticProfileRef
    migration_origin_ref: MigrationOriginRef | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _parent(self) -> PublishKnowledgeRevisionCommand:
        if self.parent_revision_id != self.expected_parent_revision_id:
            raise ValueError("parent_revision_id must equal expected_parent_revision_id")
        return self
