"""Metadata required to bind a recap run to an existing World and campaign."""

from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from .base import DungeonMindModel


class WorldCampaignIngestContextRequestV1(DungeonMindModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)
    world_id: str = Field(min_length=1, max_length=512)
    campaign_id: str = Field(min_length=1, max_length=512)

    @field_validator("world_id", "campaign_id")
    @classmethod
    def _exact_id(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("IDs must be nonblank and unpadded")
        return value


class WorldCampaignIngestContextV1(WorldCampaignIngestContextRequestV1):
    """An observed membership and head; subsequent publication still requires CAS."""

    schema_version: Literal["dm_world_campaign_ingest_context_v1"] = (
        "dm_world_campaign_ingest_context_v1"
    )
    membership: Literal["member"] = "member"
    head_revision_id: str = Field(min_length=1)
    graph_schema: str = Field(min_length=1)
    graph_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("head_revision_id", "graph_schema")
    @classmethod
    def _exact_metadata(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("head metadata must be nonblank and unpadded")
        return value
