"""Additive governed aliases for newly created prospective entities.

Parent evidence membership is not current source authorization. Reads retain the
ordinary source, visibility, scope and standing gates.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from ..base import DungeonMindModel
from .common import KnowledgeStanding, NonBlankId, _unique
from .prospective import ProspectiveEntityRef, ProspectiveKnowledgeContribution


class ProspectiveCreateAliasV1(DungeonMindModel):
    kind: Literal["create_alias"] = "create_alias"
    item_id: NonBlankId
    alias_id: NonBlankId
    entity: ProspectiveEntityRef
    alias_text: NonBlankId
    evidence_ref_ids: list[NonBlankId] = Field(min_length=1)
    standing: KnowledgeStanding

    _evidence_unique = field_validator("evidence_ref_ids")(_unique)


class ProspectiveAliasContributionV1(DungeonMindModel):
    schema_version: Literal["dm_prospective_alias_contribution_v1"] = (
        "dm_prospective_alias_contribution_v1"
    )
    contribution: ProspectiveKnowledgeContribution
    aliases: list[ProspectiveCreateAliasV1] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_items_and_aliases(self) -> ProspectiveAliasContributionV1:
        items = [item.item_id for item in self.contribution.items] + [
            alias.item_id for alias in self.aliases
        ]
        if len(items) != len(set(items)):
            raise ValueError("item_id must be unique across contribution and aliases")
        ids = [alias.alias_id for alias in self.aliases]
        if len(ids) != len(set(ids)):
            raise ValueError("alias_id must be unique")
        return self
