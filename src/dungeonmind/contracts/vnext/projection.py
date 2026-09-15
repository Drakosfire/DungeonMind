from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from ..base import DungeonMindModel
from ..semantic_profile import SemanticProfileRef
from .common import KnowledgeStanding, NonBlankId, QualifiedTerm, ScopeSelector, _unique
from .domain import DomainContractRef


class FocusRef(DungeonMindModel):
    kind: QualifiedTerm
    id: NonBlankId


class ProjectionRequest(DungeonMindModel):
    schema_version: Literal["dm_knowledge_projection_request_v1"] = (
        "dm_knowledge_projection_request_v1"
    )
    space_id: NonBlankId
    revision_id: NonBlankId | None = None
    scope_selector: ScopeSelector
    audience_labels: list[QualifiedTerm] = Field(default_factory=list)
    standing_selector: list[KnowledgeStanding] = Field(default_factory=list)
    focus: list[FocusRef] = Field(default_factory=list)
    domain_context: list[QualifiedTerm] = Field(default_factory=list)
    _audience = field_validator("audience_labels", "domain_context")(_unique)

    @field_validator("standing_selector")
    @classmethod
    def _unique_standing(cls, value: list[KnowledgeStanding]) -> list[KnowledgeStanding]:
        if len(value) != len(set(value)):
            raise ValueError("standing_selector must contain unique values")
        return value


class ProjectionSnapshot(DungeonMindModel):
    schema_version: Literal["dm_knowledge_projection_snapshot_v1"] = (
        "dm_knowledge_projection_snapshot_v1"
    )
    space_id: NonBlankId
    revision_id: NonBlankId
    head_revision_id: NonBlankId
    is_head: bool
    domain_contract_ref: DomainContractRef
    semantic_profile_ref: SemanticProfileRef
    scope_selector: ScopeSelector
    audience_labels: list[QualifiedTerm] = Field(default_factory=list)
    standing_selector: list[KnowledgeStanding] = Field(default_factory=list)
    focus: list[FocusRef] = Field(default_factory=list)
    projected_at: datetime
    _audience = field_validator("audience_labels")(_unique)

    @field_validator("standing_selector")
    @classmethod
    def _unique_standing(cls, value: list[KnowledgeStanding]) -> list[KnowledgeStanding]:
        if len(value) != len(set(value)):
            raise ValueError("standing_selector must contain unique values")
        return value
