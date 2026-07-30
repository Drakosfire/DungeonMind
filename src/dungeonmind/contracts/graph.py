"""World Graph revision and head contracts (schemas ``dm_graph_revision_v1``,
``dm_graph_head_v1``).

There is exactly one World Supergraph per world. Published revisions are
immutable and content-addressed; one head per world advances atomically with
stale-parent rejection. A failed publish leaves the previous head readable.
The graph payload in v1 is a complete canonical JSON snapshot (see
Docs/Decisions/ADR-0001); normalized head/query tables are a later,
benchmark-gated optimization.
"""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from .base import DungeonMindModel

GRAPH_REVISION_SCHEMA = "dm_graph_revision_v1"
GRAPH_HEAD_SCHEMA = "dm_graph_head_v1"


class WorldGraphRevision(DungeonMindModel):
    """The immutable revision envelope. Payload bytes live with the store."""

    schema_version: Literal["dm_graph_revision_v1"] = GRAPH_REVISION_SCHEMA
    world_id: str
    # Content-addressed: "rev:<sha256-hex-prefix>"; see domain.revision_ids.
    revision_id: str
    # Declared lineage. None only for the world's first revision.
    parent_revision_id: str | None
    created_at: datetime
    operation_ids: list[str] = Field(min_length=1)
    graph_schema: str
    graph_payload_sha256: str
    status: Literal["published"] = "published"


class WorldGraphHead(DungeonMindModel):
    """The single mutable pointer per world. Never 'latest by timestamp'."""

    schema_version: Literal["dm_graph_head_v1"] = GRAPH_HEAD_SCHEMA
    world_id: str
    head_revision_id: str
    updated_at: datetime


class PublishRevisionCommand(DungeonMindModel):
    """Atomic publish request for linear head advancement.

    Normal publication requires
    ``parent_revision_id == expected_parent_revision_id == current_head``.
    The contract enforces ``parent_revision_id == expected_parent_revision_id``;
    the repository enforces equality with the current head (CAS). Rollback is
    the explicit mechanism for repointing a head; there is no branch-publication
    operation in v1.
    """

    world_id: str
    parent_revision_id: str | None
    expected_parent_revision_id: str | None
    operation_ids: list[str] = Field(min_length=1)
    graph_schema: str
    graph_payload: dict[str, Any]
    created_at: datetime

    @model_validator(mode="after")
    def _lineage_matches_cas_token(self) -> Self:
        if self.parent_revision_id != self.expected_parent_revision_id:
            raise ValueError(
                "parent_revision_id must equal expected_parent_revision_id for "
                "normal publication; use rollback_head to repoint without lineage"
            )
        return self


class StoredGraphRevision(DungeonMindModel):
    """Envelope + payload as returned by exact revision reads."""

    revision: WorldGraphRevision
    graph_payload: dict[str, Any]
