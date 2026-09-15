from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

from ..base import DungeonMindModel
from .common import DomainMetadataEntry, NonBlankId, _unique
from .domain import Assertion, Entity
from .knowledge import IdentityDecisionV3


class ProposeEntity(DungeonMindModel):
    kind: Literal["propose_entity"] = "propose_entity"
    item_id: NonBlankId
    entity: Entity


class ProposeAssertion(DungeonMindModel):
    kind: Literal["propose_assertion"] = "propose_assertion"
    item_id: NonBlankId
    assertion: Assertion


class RetractAssertion(DungeonMindModel):
    kind: Literal["retract_assertion"] = "retract_assertion"
    item_id: NonBlankId
    target_assertion_id: NonBlankId


class SupersedeAssertion(DungeonMindModel):
    kind: Literal["supersede_assertion"] = "supersede_assertion"
    item_id: NonBlankId
    target_assertion_id: NonBlankId
    replacement_assertion: Assertion


class ProposeIdentityDecision(DungeonMindModel):
    kind: Literal["propose_identity_decision"] = "propose_identity_decision"
    item_id: NonBlankId
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
    contribution_id: NonBlankId
    space_id: NonBlankId
    producer: NonBlankId
    produced_at: datetime
    source_refs: list[NonBlankId] = Field(default_factory=list)
    status: NonBlankId
    supersedes_contribution_id: NonBlankId | None = None
    items: list[ContributionItem] = Field(min_length=1)
    diagnostics: list[DomainMetadataEntry] = Field(default_factory=list)
    _refs = field_validator("source_refs")(_unique)


class ContributionDisposition(DungeonMindModel):
    schema_version: Literal["dm_contribution_disposition_v1"] = "dm_contribution_disposition_v1"
    item_id: NonBlankId
    disposition: Literal["accepted", "rejected", "unresolved"]
    identity_decision_ids: list[NonBlankId] = Field(default_factory=list)
    reason_code: str | None = None
    domain_metadata: list[DomainMetadataEntry] = Field(default_factory=list)
    _ids = field_validator("identity_decision_ids")(_unique)
