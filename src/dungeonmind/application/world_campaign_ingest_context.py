"""Read one authoritative World/campaign membership and its observed head."""

from typing import Protocol

from ..contracts.world_campaign_ingest_context import (
    WorldCampaignIngestContextRequestV1,
    WorldCampaignIngestContextV1,
)
from ..domain.errors import DungeonMindError, PersistenceIntegrityError


class WorldCampaignMembershipNotFoundError(DungeonMindError):
    code = "world_campaign_membership_not_found"

    def __init__(self) -> None:
        super().__init__("World/campaign membership was not found.")


class WorldGraphNotInitializedError(DungeonMindError):
    code = "world_graph_not_initialized"

    def __init__(self) -> None:
        super().__init__("World Graph is not initialized.")


class WorldCampaignIngestContextReader(Protocol):
    def read_ingest_context(
        self, *, world_id: str, campaign_id: str
    ) -> WorldCampaignIngestContextV1:
        """Read membership and current head metadata in one consistent snapshot."""
        ...


def query_world_campaign_ingest_context(
    request: WorldCampaignIngestContextRequestV1,
    *,
    reader: WorldCampaignIngestContextReader,
) -> WorldCampaignIngestContextV1:
    request = WorldCampaignIngestContextRequestV1.model_validate(request.model_dump())
    result = reader.read_ingest_context(world_id=request.world_id, campaign_id=request.campaign_id)
    if (result.world_id, result.campaign_id) != (request.world_id, request.campaign_id):
        raise PersistenceIntegrityError("ingest context returned a different World/campaign")
    return result
