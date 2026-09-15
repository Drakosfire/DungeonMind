from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from ..base import DungeonMindModel
from ..semantic_profile import SemanticProfileRef
from .common import QualifiedTerm, ScopeSelector, _unique
from .domain import DomainContractRef


class FocusRef(DungeonMindModel):
    kind: QualifiedTerm
    id: str = Field(min_length=1)


class ProjectionRequest(DungeonMindModel):
    schema_version: Literal["dm_knowledge_projection_request_v1"] = (
        "dm_knowledge_projection_request_v1"
    )
    space_id: str = Field(min_length=1)
    revision_id: str | None = None
    scope_selector: ScopeSelector
    audience_labels: list[QualifiedTerm] = Field(default_factory=list)
    standing_selector: list[str] = Field(default_factory=list)
    focus: list[FocusRef] = Field(default_factory=list)
    domain_context: list[QualifiedTerm] = Field(default_factory=list)
    _audience = field_validator("audience_labels", "standing_selector", "domain_context")(_unique)


class ProjectionSnapshot(DungeonMindModel):
    schema_version: Literal["dm_knowledge_projection_snapshot_v1"] = (
        "dm_knowledge_projection_snapshot_v1"
    )
    space_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    head_revision_id: str = Field(min_length=1)
    is_head: bool
    domain_contract_ref: DomainContractRef
    semantic_profile_ref: SemanticProfileRef
    scope_selector: ScopeSelector
    audience_labels: list[QualifiedTerm] = Field(default_factory=list)
    standing_selector: list[str] = Field(default_factory=list)
    focus: list[FocusRef] = Field(default_factory=list)
    projected_at: datetime
    _audience = field_validator("audience_labels", "standing_selector")(_unique)
