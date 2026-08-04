"""Public HTTP contract for finalized-review publication."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, field_validator

from .base import DungeonMindModel

FINALIZED_REVIEW_PUBLICATION_REQUEST_SCHEMA = (
    "dm_finalized_review_publication_request_v1"
)


class FinalizedReviewPublicationRequest(DungeonMindModel):
    """The only caller-controlled publication inputs."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal[
        "dm_finalized_review_publication_request_v1"
    ] = FINALIZED_REVIEW_PUBLICATION_REQUEST_SCHEMA
    world_id: str
    review_id: str

    @field_validator("world_id", "review_id")
    @classmethod
    def _require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("publication identity must be non-blank")
        return value
