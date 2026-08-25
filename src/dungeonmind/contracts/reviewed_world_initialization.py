"""Reviewed first-world initialization command and terminal receipt contracts.

The command is reviewed-fact authority for a pristine world. It must not carry
a graph payload or an expected parent. ``command_sha256`` is computed by the
application bind over every semantic command field; it is stored on the
receipt, not on this command model.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, field_validator

from .base import DungeonMindModel
from .contribution import GraphContributionV2
from .evidence import SourceArtifactV2, SourceRevision
from .semantic_profile import SemanticProfileRef

REVIEWED_WORLD_INITIALIZATION_COMMAND_SCHEMA = (
    "dm_reviewed_world_initialization_command_v1"
)
REVIEWED_WORLD_INITIALIZATION_RECEIPT_SCHEMA = (
    "dm_reviewed_world_initialization_receipt_v1"
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_MAX_ID_LEN = 256


def _require_bounded_id(value: str, *, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be a non-blank string")
    if len(value) > _MAX_ID_LEN:
        raise ValueError(f"{field_name} exceeds maximum length {_MAX_ID_LEN}")
    return value


def _require_digest(value: str, *, field_name: str) -> str:
    if not _SHA256_HEX.fullmatch(value):
        raise ValueError(f"{field_name} must be exactly 64 lowercase hex")
    return value


def _require_timezone_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class ReviewedWorldInitializationCommandV1(DungeonMindModel):
    """Internal repository command. Application-owned; not a transport request."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_reviewed_world_initialization_command_v1"] = (
        REVIEWED_WORLD_INITIALIZATION_COMMAND_SCHEMA
    )
    initialization_id: str
    world_id: str
    campaign_id: str | None
    source_plan_schema: str
    source_plan_id: str
    source_plan_sha256: str
    semantic_profile: SemanticProfileRef
    source_artifacts: list[SourceArtifactV2]
    source_revisions: list[SourceRevision]
    reviewed_contribution: GraphContributionV2
    actor: str
    requested_initialized_at: datetime

    @field_validator(
        "initialization_id",
        "world_id",
        "source_plan_schema",
        "source_plan_id",
        "actor",
    )
    @classmethod
    def _bounded_ids(cls, value: str) -> str:
        return _require_bounded_id(value, field_name="command identity field")

    @field_validator("campaign_id")
    @classmethod
    def _optional_campaign(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_bounded_id(value, field_name="campaign_id")

    @field_validator("source_plan_sha256")
    @classmethod
    def _plan_digest(cls, value: str) -> str:
        return _require_digest(value, field_name="source_plan_sha256")

    @field_validator("requested_initialized_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="requested_initialized_at")


class ReviewedWorldInitializationReceiptV1(DungeonMindModel):
    """Terminal historical correspondence for one reviewed first-world initialization."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_reviewed_world_initialization_receipt_v1"] = (
        REVIEWED_WORLD_INITIALIZATION_RECEIPT_SCHEMA
    )
    initialization_id: str
    world_id: str
    campaign_id: str | None
    source_plan_schema: str
    source_plan_id: str
    source_plan_sha256: str
    command_sha256: str
    reviewed_contribution_id: str
    reviewed_contribution_sha256: str
    published_revision_id: str
    published_graph_schema: Literal["dm_union_graph_v6"] = "dm_union_graph_v6"
    published_graph_payload_sha256: str
    accepted_assertion_ids: list[str]
    actor: str
    initialized_at: datetime

    @field_validator(
        "initialization_id",
        "world_id",
        "source_plan_schema",
        "source_plan_id",
        "reviewed_contribution_id",
        "published_revision_id",
        "actor",
    )
    @classmethod
    def _bounded_ids(cls, value: str) -> str:
        return _require_bounded_id(value, field_name="receipt identity field")

    @field_validator("campaign_id")
    @classmethod
    def _optional_campaign(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_bounded_id(value, field_name="campaign_id")

    @field_validator(
        "source_plan_sha256",
        "command_sha256",
        "reviewed_contribution_sha256",
        "published_graph_payload_sha256",
    )
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="receipt digest")

    @field_validator("accepted_assertion_ids")
    @classmethod
    def _accepted_ids(cls, value: list[str]) -> list[str]:
        for item in value:
            _require_bounded_id(item, field_name="accepted_assertion_id")
        if len(value) != len(set(value)):
            raise ValueError("accepted_assertion_ids must be unique")
        return value

    @field_validator("initialized_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="initialized_at")
