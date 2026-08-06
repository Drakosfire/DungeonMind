"""Strict public request contract for exact Threat mechanics hydration."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, field_validator

from dungeonmind.contracts.base import DungeonMindModel

from .mechanics_resources import DndMechanicsResourceRef

THREAT_MECHANICS_HYDRATION_REQUEST_SCHEMA = (
    "dmdnd_threat_mechanics_hydration_request_v1"
)

_OPAQUE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_GRAPH_REVISION_ID = re.compile(r"^rev:[0-9a-f]{32}$")
_OBJECT_ID = re.compile(r"^obj:[A-Za-z0-9._:-]+$")


def _validate_opaque_world_id(value: str) -> str:
    lowered = value.casefold()
    if not value.strip() or value != value.strip():
        raise ValueError("world_id must be a non-blank opaque token")
    if lowered == "latest":
        raise ValueError("world_id must not be 'latest'")
    if "://" in value or lowered.startswith(("http:", "https:", "file:", "ftp:")):
        raise ValueError("world_id must not be a URI")
    if "/" in value or "\\" in value:
        raise ValueError("world_id must not be a path")
    if not _OPAQUE_TOKEN.fullmatch(value):
        raise ValueError("world_id must be an opaque identity token")
    return value


class DndThreatMechanicsHydrationRequest(DungeonMindModel):
    """Caller-minimal locator for one exact-revision mechanics hydration."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal[
        "dmdnd_threat_mechanics_hydration_request_v1"
    ] = THREAT_MECHANICS_HYDRATION_REQUEST_SCHEMA
    world_id: str
    graph_revision_id: str
    object_id: str
    resource_ref: DndMechanicsResourceRef

    @field_validator("world_id")
    @classmethod
    def _validate_world(cls, value: str) -> str:
        return _validate_opaque_world_id(value)

    @field_validator("graph_revision_id")
    @classmethod
    def _validate_graph_revision(cls, value: str) -> str:
        if not _GRAPH_REVISION_ID.fullmatch(value):
            raise ValueError("graph_revision_id must be rev:<32 lowercase hex>")
        return value

    @field_validator("object_id")
    @classmethod
    def _validate_object(cls, value: str) -> str:
        if not _OBJECT_ID.fullmatch(value):
            raise ValueError("object_id must be obj:<opaque identity>")
        return value


__all__ = [
    "THREAT_MECHANICS_HYDRATION_REQUEST_SCHEMA",
    "DndThreatMechanicsHydrationRequest",
]
