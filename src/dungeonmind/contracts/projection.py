"""Projection contracts (schemas ``dm_projection_request_v1``,
``dm_projection_snapshot_v1``).

A projection is a lens over one exact graph revision: world + campaign scope +
focus + admissibility. Every read operates against one coherent revision —
an explicit pin, or the head resolved at read time and reported in the
snapshot. Projections never mutate identity and never become a store.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from .base import DungeonMindModel

PROJECTION_REQUEST_SCHEMA = "dm_projection_request_v1"
PROJECTION_SNAPSHOT_SCHEMA = "dm_projection_snapshot_v1"


class Admissibility(StrEnum):
    """Which knowledge classes are admissible to this reader."""

    GM = "gm"
    PLAYER = "player"


class FocusKind(StrEnum):
    NONE = "none"
    SESSION = "session"


class ProjectionFocus(DungeonMindModel):
    """A focus overlay narrows chronology/salience; it is not an ownership boundary."""

    kind: FocusKind = FocusKind.NONE
    session_id: str | None = None
    campaign_id: str | None = None


class ScopeMode(StrEnum):
    CAMPAIGN = "campaign"
    WORLD = "world"


class WorldGraphProjectionRequest(DungeonMindModel):
    schema_version: Literal["dm_projection_request_v1"] = PROJECTION_REQUEST_SCHEMA
    world_id: str
    campaign_id: str | None = Field(default=None, min_length=1)
    focus: ProjectionFocus = ProjectionFocus()
    admissibility: Admissibility = Admissibility.GM
    # None resolves to the head at read time; the snapshot reports which won.
    revision_pin: str | None = None
    query_text: str | None = None
    scope_mode: ScopeMode = ScopeMode.CAMPAIGN


class ProjectionSnapshot(DungeonMindModel):
    """The resolved, reported identity of exactly what was read."""

    schema_version: Literal["dm_projection_snapshot_v1"] = PROJECTION_SNAPSHOT_SCHEMA
    world_id: str
    campaign_id: str | None = None
    focus: ProjectionFocus = ProjectionFocus()
    admissibility: Admissibility = Admissibility.GM
    scope_mode: ScopeMode = ScopeMode.CAMPAIGN
    revision_id: str
    head_revision_id: str
    is_head: bool
    projected_at: datetime
