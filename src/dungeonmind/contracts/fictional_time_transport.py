"""Public HTTP request envelope for FT1b fictional-time shadow queries."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import ConfigDict, model_validator

from .base import DungeonMindModel
from .fictional_time import FictionalTimeClaimBundle, FictionalTimeQuery

FICTIONAL_TIME_SHADOW_QUERY_REQUEST_SCHEMA = (
    "dm_fictional_time_shadow_query_request_v1"
)


class FictionalTimeShadowQueryRequest(DungeonMindModel):
    """Caller-supplied exact-revision locator plus one shadow bundle and query."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_fictional_time_shadow_query_request_v1"] = (
        FICTIONAL_TIME_SHADOW_QUERY_REQUEST_SCHEMA
    )
    world_id: str
    graph_revision_id: str
    claim_bundle: FictionalTimeClaimBundle
    query: FictionalTimeQuery

    @model_validator(mode="after")
    def _bind_locator_to_bundle(self) -> Self:
        if not self.world_id.strip():
            raise ValueError("world_id must be non-blank")
        if not self.graph_revision_id.strip():
            raise ValueError("graph_revision_id must be non-blank")
        if self.world_id != self.claim_bundle.world_id:
            raise ValueError("world_id must equal claim_bundle.world_id")
        if self.graph_revision_id != self.claim_bundle.graph_revision_id:
            raise ValueError(
                "graph_revision_id must equal claim_bundle.graph_revision_id"
            )
        return self
