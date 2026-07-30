"""Identity resolution contracts (schema ``dm_identity_decision_v1``).

Identity outcomes are explicit and durable. ``ambiguous``/``rejected`` outcomes
stay at contribution level and never create canon; merge/split/unmerge are
durable, replayable decisions. Confidence scores are never authority.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from .base import DungeonMindModel

IDENTITY_DECISION_SCHEMA = "dm_identity_decision_v1"


class IdentityOutcome(StrEnum):
    RESOLVED_EXISTING = "resolved_existing"
    CREATED_NEW = "created_new"
    PROVISIONAL_NEW = "provisional_new"
    AMBIGUOUS = "ambiguous"
    BLOCKED_COLLISION = "blocked_collision"
    REJECTED = "rejected"
    HUMAN_OVERRIDE = "human_override"


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


class IdentityDecisionRecord(DungeonMindModel):
    """A durable, replayable identity decision (merge/split/unmerge/alias/...)."""

    schema_version: Literal["dm_identity_decision_v1"] = IDENTITY_DECISION_SCHEMA
    decision_id: str
    world_id: str
    decision_kind: IdentityDecisionKind
    subject_object_ids: list[str]
    target_object_ids: list[str] = []
    alias: str | None = None
    actor: str = "system"
    reason: str | None = None
    reversible: bool = True
    supersedes_decision_ids: list[str] = []
    status: IdentityDecisionStatus = IdentityDecisionStatus.ACTIVE
    created_at: datetime
