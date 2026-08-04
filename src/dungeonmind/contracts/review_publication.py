"""Durable finalized-review publication contracts.

These contracts bind one finalized review operation to one immutable graph
revision.  The command is an internal unit-of-work value; the publication is
the terminal durable record returned by exact replay and recovery.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import ConfigDict, field_validator, model_validator

from .base import DungeonMindModel

FINALIZED_REVIEW_PUBLICATION_COMMAND_SCHEMA = (
    "dm_finalized_review_publication_command_v1"
)
FINALIZED_REVIEW_PUBLICATION_SCHEMA = "dm_finalized_review_publication_v1"

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compute_revision_id(
    *,
    world_id: str,
    parent_revision_id: str,
    operation_id: str,
    graph_schema: str,
    graph_payload_sha256: str,
) -> str:
    material = {
        "world_id": world_id,
        "parent_revision_id": parent_revision_id,
        "operation_ids": [operation_id],
        "graph_schema": graph_schema,
        "graph_payload_sha256": graph_payload_sha256,
    }
    return f"rev:{_canonical_sha256(material)[:32]}"


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-blank")
    return value


def _require_digest(value: str, *, field_name: str) -> str:
    if not _SHA256_HEX.fullmatch(value):
        raise ValueError(f"{field_name} must be exactly 64 lowercase hex")
    return value


def _require_timezone_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class _PublicationContract(DungeonMindModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    _identity_fields = (
        "world_id",
        "review_id",
        "reviewed_contribution_id",
        "confirmation_id",
        "operation_id",
        "expected_parent_revision_id",
        "published_revision_id",
    )

    @field_validator(*_identity_fields, "graph_schema", check_fields=False)
    @classmethod
    def _validate_nonblank(cls, value: str, info: object) -> str:
        return _require_nonblank(
            value,
            field_name=getattr(info, "field_name", "identity"),
        )

    @field_validator(
        "reviewed_contribution_sha256",
        "review_intent_sha256",
        "parent_graph_payload_sha256",
        "graph_payload_sha256",
        check_fields=False,
    )
    @classmethod
    def _validate_digests(cls, value: str, info: object) -> str:
        return _require_digest(
            value,
            field_name=getattr(info, "field_name", "digest"),
        )

    @field_validator("published_at", check_fields=False)
    @classmethod
    def _validate_published_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="published_at")


class FinalizedReviewPublication(_PublicationContract):
    """One immutable terminal correspondence between review and revision."""

    schema_version: Literal[
        "dm_finalized_review_publication_v1"
    ] = FINALIZED_REVIEW_PUBLICATION_SCHEMA
    world_id: str
    review_id: str
    reviewed_contribution_id: str
    reviewed_contribution_sha256: str
    review_intent_sha256: str
    confirmation_id: str
    operation_id: str
    expected_parent_revision_id: str
    parent_graph_payload_sha256: str
    published_revision_id: str
    graph_schema: str
    graph_payload_sha256: str
    published_at: datetime
    status: Literal["published"] = "published"

    @model_validator(mode="after")
    def _revision_identity(self) -> Self:
        expected = _compute_revision_id(
            world_id=self.world_id,
            parent_revision_id=self.expected_parent_revision_id,
            operation_id=self.operation_id,
            graph_schema=self.graph_schema,
            graph_payload_sha256=self.graph_payload_sha256,
        )
        if self.published_revision_id != expected:
            raise ValueError("published_revision_id does not match publication content")
        return self


class FinalizedReviewPublicationCommand(_PublicationContract):
    """Internal atomic publication unit-of-work command.

    It carries graph bytes only long enough for the repository transaction.  It
    is not a transport request and has no pending-attempt or retry lifecycle.
    """

    schema_version: Literal[
        "dm_finalized_review_publication_command_v1"
    ] = FINALIZED_REVIEW_PUBLICATION_COMMAND_SCHEMA
    world_id: str
    review_id: str
    reviewed_contribution_id: str
    reviewed_contribution_sha256: str
    review_intent_sha256: str
    confirmation_id: str
    operation_id: str
    expected_parent_revision_id: str
    parent_graph_payload_sha256: str
    expected_published_revision_id: str
    graph_schema: str
    graph_payload: dict[str, Any]
    graph_payload_sha256: str
    requested_published_at: datetime

    @field_validator("requested_published_at")
    @classmethod
    def _validate_requested_published_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="requested_published_at")

    @model_validator(mode="after")
    def _command_integrity(self) -> Self:
        if _canonical_sha256(self.graph_payload) != self.graph_payload_sha256:
            raise ValueError("graph_payload_sha256 does not match graph_payload")
        expected = _compute_revision_id(
            world_id=self.world_id,
            parent_revision_id=self.expected_parent_revision_id,
            operation_id=self.operation_id,
            graph_schema=self.graph_schema,
            graph_payload_sha256=self.graph_payload_sha256,
        )
        if self.expected_published_revision_id != expected:
            raise ValueError(
                "expected_published_revision_id does not match publication content"
            )
        return self
