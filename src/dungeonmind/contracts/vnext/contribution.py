from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

from ..base import DungeonMindModel
from .common import DomainMetadataEntry, _unique
from .domain import Assertion, Entity
from .knowledge import IdentityDecisionV3


class ProposeEntity(DungeonMindModel):
    kind: Literal["propose_entity"] = "propose_entity"
    item_id: str = Field(min_length=1)
    entity: Entity


class ProposeAssertion(DungeonMindModel):
    kind: Literal["propose_assertion"] = "propose_assertion"
    item_id: str = Field(min_length=1)
    assertion: Assertion


class RetractAssertion(DungeonMindModel):
    kind: Literal["retract_assertion"] = "retract_assertion"
    item_id: str = Field(min_length=1)
    target_assertion_id: str = Field(min_length=1)


class SupersedeAssertion(DungeonMindModel):
    kind: Literal["supersede_assertion"] = "supersede_assertion"
    item_id: str = Field(min_length=1)
    target_assertion_id: str = Field(min_length=1)
    replacement_assertion: Assertion


class ProposeIdentityDecision(DungeonMindModel):
    kind: Literal["propose_identity_decision"] = "propose_identity_decision"
    item_id: str = Field(min_length=1)
    decision: IdentityDecisionV3


ContributionItem = Annotated[
    ProposeEntity
    | ProposeAssertion
    | RetractAssertion
    | SupersedeAssertion
    | ProposeIdentityDecision,
    Field(discriminator="kind"),
]


class KnowledgeContribution(DungeonMindModel):
    schema_version: Literal["dm_knowledge_contribution_v1"] = "dm_knowledge_contribution_v1"
    contribution_id: str = Field(min_length=1)
    space_id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    produced_at: datetime
    source_refs: list[str] = Field(default_factory=list)
    status: str = Field(min_length=1)
    supersedes_contribution_id: str | None = None
    items: list[ContributionItem] = Field(min_length=1)
    diagnostics: list[DomainMetadataEntry] = Field(default_factory=list)
    _refs = field_validator("source_refs")(_unique)


class ContributionDisposition(DungeonMindModel):
    schema_version: Literal["dm_contribution_disposition_v1"] = "dm_contribution_disposition_v1"
    item_id: str = Field(min_length=1)
    disposition: Literal["accepted", "rejected", "unresolved"]
    identity_decision_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = None
    domain_metadata: list[DomainMetadataEntry] = Field(default_factory=list)
    _ids = field_validator("identity_decision_ids")(_unique)
