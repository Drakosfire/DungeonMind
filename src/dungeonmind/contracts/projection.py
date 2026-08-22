"""Projection contracts (schemas ``dm_projection_request_v1``,
``dm_projection_snapshot_v1``).

A projection is a lens over one exact graph revision: world + campaign scope +
focus + admissibility. Every read operates against one coherent revision —
an explicit pin, or the head resolved at read time and reported in the
snapshot. Projections never mutate identity and never become a store.

Admissibility is required on every externally constructed request. Absence
never means GM — that would broaden access when a caller forgets a field.

Campaign ownership lives only on the request/snapshot/scope (``campaign_id`` +
``scope_mode``). ``ProjectionFocus`` narrows chronology or salience; it is not
a second campaign authority.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

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
    """A focus overlay narrows chronology/salience; it is not an ownership boundary.

    Campaign scope is never carried here — use the enclosing request's
    ``campaign_id`` so there is exactly one campaign authority.
    """

    kind: FocusKind = FocusKind.NONE
    session_id: str | None = None

    @model_validator(mode="after")
    def _focus_kind_invariants(self) -> Self:
        if self.kind is FocusKind.SESSION and not self.session_id:
            raise ValueError("session focus requires session_id")
        if self.kind is FocusKind.NONE and self.session_id is not None:
            raise ValueError("session_id is only valid when focus kind is session")
        return self


class ScopeMode(StrEnum):
    CAMPAIGN = "campaign"
    WORLD = "world"


def _validate_campaign_and_focus_scope(
    *,
    scope_mode: ScopeMode,
    campaign_id: str | None,
    focus: ProjectionFocus,
) -> None:
    if scope_mode is ScopeMode.WORLD and campaign_id is not None:
        raise ValueError("world scope_mode requires campaign_id to be None")
    if scope_mode is ScopeMode.CAMPAIGN and not campaign_id:
        raise ValueError("campaign scope_mode requires campaign_id")
    if focus.kind is FocusKind.SESSION:
        if not campaign_id:
            raise ValueError("session focus requires campaign_id on the enclosing scope")
        if not focus.session_id:
            raise ValueError("session focus requires session_id")


class WorldGraphProjectionRequest(DungeonMindModel):
    schema_version: Literal["dm_projection_request_v1"] = PROJECTION_REQUEST_SCHEMA
    world_id: str
    campaign_id: str | None = Field(default=None, min_length=1)
    focus: ProjectionFocus = Field(default_factory=ProjectionFocus)
    # Required. No default — absence must never mean GM.
    admissibility: Admissibility
    # None resolves to the head at read time; the snapshot reports which won.
    revision_pin: str | None = None
    query_text: str | None = None
    scope_mode: ScopeMode = ScopeMode.WORLD

    @model_validator(mode="after")
    def _scope_and_focus_invariants(self) -> Self:
        _validate_campaign_and_focus_scope(
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
        scope_mode: ScopeMode = ScopeMode.WORLD,
    ) -> Self:
        """Trusted constructor for orchestration code that already authorized the caller."""
        return cls(
            world_id=world_id,
            campaign_id=campaign_id,
            focus=focus or ProjectionFocus(),
            admissibility=admissibility,
            revision_pin=revision_pin,
            query_text=query_text,
            scope_mode=scope_mode,
        )


class ProjectionSnapshot(DungeonMindModel):
    """The resolved, reported identity of exactly what was read."""

    schema_version: Literal["dm_projection_snapshot_v1"] = PROJECTION_SNAPSHOT_SCHEMA
    world_id: str
    campaign_id: str | None = None
    focus: ProjectionFocus = Field(default_factory=ProjectionFocus)
    admissibility: Admissibility
    scope_mode: ScopeMode = ScopeMode.WORLD
    revision_id: str
    head_revision_id: str
    is_head: bool
    projected_at: datetime

    @model_validator(mode="after")
    def _resolved_scope_invariants(self) -> Self:
        _validate_campaign_and_focus_scope(
            scope_mode=self.scope_mode,
            campaign_id=self.campaign_id,
            focus=self.focus,
        )
        if self.is_head != (self.revision_id == self.head_revision_id):
            raise ValueError(
                "is_head must equal (revision_id == head_revision_id)"
            )
        return self
