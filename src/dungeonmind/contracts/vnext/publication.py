"""Durable identity for one native vNext publication attempt."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..base import DungeonMindModel


class KnowledgePublicationReceipt(DungeonMindModel):
    schema_version: Literal["dm_knowledge_publication_receipt_v1"] = (
        "dm_knowledge_publication_receipt_v1"
    )
    space_id: str = Field(min_length=1)
    publication_id: str = Field(min_length=1)
    command_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_parent_revision_id: str | None = None
    published_revision_id: str = Field(min_length=1)
    graph_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["published"] = "published"
