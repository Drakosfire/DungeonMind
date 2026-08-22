"""Projection contracts v2 (schemas ``dm_projection_request_v2``,
``dm_projection_snapshot_v2``).

v2 adds exactly one thing to the projection vocabulary: the cross-campaign
scope mode. No v1 contract is modified by this module; unchanged pieces
(``Admissibility``, ``FocusKind``, ``ProjectionFocus``) are reused directly
from the v1 module.

``WORLD_CROSS_CAMPAIGN`` is the cross-campaign lens: world-owned knowledge
plus every campaign scope in the world, in one exact revision. It exists so
the v1 ``WORLD`` semantics (world-owned only) are never silently redefined;
consumers needing the Buddy-style "all campaigns in this world" lens must ask
for it explicitly through the v2 contract.

Scope mode and admissibility are independent axes. The scope mode widens or
narrows *which campaign knowledge* is visible; ``admissibility`` then
independently controls GM-only versus player-visible content within that
scope. ``WORLD_CROSS_CAMPAIGN`` does not itself encode any upstream
authorization decision — a PLAYER-admissible cross-campaign read is legal at
this layer and still fails closed on GM-only content.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import DungeonMindModel
from .projection import (
    Admissibility,
    FocusKind,
    ProjectionFocus,
)

PROJECTION_REQUEST_SCHEMA_V2 = "dm_projection_request_v2"
PROJECTION_SNAPSHOT_SCHEMA_V2 = "dm_projection_snapshot_v2"


class ScopeModeV2(StrEnum):
    """Campaign-scope policy for one read (v2 vocabulary).

    * ``CAMPAIGN`` — the requested campaign plus world-owned knowledge;
      requires ``campaign_id``. Same meaning as v1.
    * ``WORLD`` — world-owned knowledge only; campaign-owned sources and
      campaign-scoped assertions are excluded. Requires ``campaign_id=None``.
      Same meaning as v1.
    * ``WORLD_CROSS_CAMPAIGN`` — cross-campaign lens: world-owned knowledge
      plus every campaign scope in the world, in one exact revision.
      Requires ``campaign_id=None``. New in v2; the v1 contract vocabulary
      is frozen without it.

    Scope mode is independent of admissibility: the mode widens campaign
    scope only, and a PLAYER-admissible read under it still fails closed on
    GM-only content. The mode does not encode upstream authorization.
    """

    CAMPAIGN = "campaign"
    WORLD = "world"
    WORLD_CROSS_CAMPAIGN = "world_cross_campaign"


def _validate_campaign_and_focus_scope_v2(
    *,
    scope_mode: ScopeModeV2,
    campaign_id: str | None,
    focus: ProjectionFocus,
) -> None:
    if scope_mode is ScopeModeV2.WORLD and campaign_id is not None:
        raise ValueError("world scope_mode requires campaign_id to be None")
    if scope_mode is ScopeModeV2.WORLD_CROSS_CAMPAIGN and campaign_id is not None:
        raise ValueError("world_cross_campaign scope_mode requires campaign_id to be None")
    if scope_mode is ScopeModeV2.CAMPAIGN and not campaign_id:
        raise ValueError("campaign scope_mode requires campaign_id")
    if focus.kind is FocusKind.SESSION:
        if not campaign_id:
            raise ValueError("session focus requires campaign_id on the world scope")
        if not focus.session_id:
            raise ValueError("session focus requires session_id")


class WorldGraphProjectionRequestV2(DungeonMindModel):
    """v2 projection request: v1 shape plus the wider scope vocabulary."""

    schema_version: Literal["dm_projection_request_v2"] = PROJECTION_REQUEST_SCHEMA_V2
    world_id: str
    campaign_id: str | None = Field(default=None, min_length=1)
    focus: ProjectionFocus = Field(default_factory=ProjectionFocus)
    # Required. No default — absence must never mean GM.
    admissibility: Admissibility
    # None resolves to the head at read time; the snapshot reports which won.
    revision_pin: str | None = None
    query_text: str | None = None
    scope_mode: ScopeModeV2 = ScopeModeV2.WORLD

    @model_validator(mode="after")
    def _scope_and_focus_invariants(self) -> Self:
        _validate_campaign_and_focus_scope_v2(
            scope_mode=self.scope_mode,
            campaign_id=self.campaign_id,
            focus=self.focus,
        )
        return self

    @classmethod
    def for_authorized(
        cls,
        *,
        world_id: str,
        admissibility: Admissibility,
        campaign_id: str | None = None,
        focus: ProjectionFocus | None = None,
        revision_pin: str | None = None,
        query_text: str | None = None,
        scope_mode: ScopeModeV2 = ScopeModeV2.WORLD,
    ) -> Self:
        """Trusted constructor for application code that already authorized the caller."""
        return cls(
            world_id=world_id,
            campaign_id=campaign_id,
            focus=focus or ProjectionFocus(),
            admissibility=admissibility,
            revision_pin=revision_pin,
            query_text=query_text,
            scope_mode=scope_mode,
        )


class ProjectionSnapshotV2(DungeonMindModel):
    """The resolved, reported identity of exactly what was read (v2)."""

    schema_version: Literal["dm_projection_snapshot_v2"] = PROJECTION_SNAPSHOT_SCHEMA_V2
    world_id: str
    campaign_id: str | None = None
    focus: ProjectionFocus = Field(default_factory=ProjectionFocus)
    admissibility: Admissibility
    scope_mode: ScopeModeV2 = ScopeModeV2.WORLD
    revision_id: str
    head_revision_id: str
    is_head: bool
    projected_at: datetime

    @model_validator(mode="after")
    def _resolved_scope_invariants(self) -> Self:
        _validate_campaign_and_focus_scope_v2(
            scope_mode=self.scope_mode,
            campaign_id=self.campaign_id,
            focus=self.focus,
        )
        if self.is_head != (self.revision_id == self.head_revision_id):
            raise ValueError(
                "is_head must equal (revision_id == head_revision_id)"
            )
        return self
