"""Closed authority for one additive semantic-profile transition."""

from datetime import datetime
from typing import Literal

from pydantic import field_validator

from dungeonmind.contracts.base import DungeonMindModel
from dungeonmind.contracts.semantic_profile import SemanticProfileRef

from .common import NonBlankId
from .domain import DomainContractRef


class KnowledgeProfileTransitionV1(DungeonMindModel):
    schema_version: Literal["dm_knowledge_profile_transition_v1"] = (
        "dm_knowledge_profile_transition_v1"
    )
    space_id: NonBlankId
    expected_parent_revision_id: NonBlankId
    domain_contract_ref: DomainContractRef
    from_profile_ref: SemanticProfileRef
    to_profile_ref: SemanticProfileRef
    publication_id: NonBlankId
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Profile transition timestamp must be timezone aware")
        return value
