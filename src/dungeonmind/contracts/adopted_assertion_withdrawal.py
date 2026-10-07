"""Versioned, neutral withdrawal of one unsupported adopted assertion.

Withdrawal records that the bound source does not support an adopted assertion.
It is not a negation, contradiction, or replacement claim. The graph remains
append-only: the operation publishes a child snapshot with exactly one reviewed
relationship omitted and records its durable receipt.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, ValidationInfo, field_validator

from .base import DungeonMindModel

ADOPTED_ASSERTION_WITHDRAWAL_COMMAND_V1 = (
    "dm_adopted_assertion_withdrawal_command_v1"
)
ADOPTED_ASSERTION_WITHDRAWAL_RECEIPT_V1 = (
    "dm_adopted_assertion_withdrawal_receipt_v1"
)
ADOPTED_ASSERTION_WITHDRAWAL_TOOL = "dungeonmind.withdraw_adopted_assertion"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _id(value: str, field: str) -> str:
    if not value or not value.strip() or len(value) > 256:
        raise ValueError(f"{field} must be a non-blank ID of at most 256 characters")
    return value


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


class AdoptedAssertionWithdrawalCommandV1(DungeonMindModel):
    """Internal command; provenance is cross-verified by the repository."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_adopted_assertion_withdrawal_command_v1"] = (
        ADOPTED_ASSERTION_WITHDRAWAL_COMMAND_V1
    )
    operation_id: str
    world_id: str
    adoption_id: str
    expected_parent_revision_id: str
    relationship_id: str
    assertion_id: str
    subject_object_id: str
    predicate: str
    object_object_id: str
    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str
    source_span_ref_id: str
    source_locator: str
    parent_payload_sha256: str
    disposition: Literal["unsupported_by_bound_source"] = "unsupported_by_bound_source"
    actor: str
    requested_at: datetime

    @field_validator(
        "operation_id", "world_id", "adoption_id", "expected_parent_revision_id",
        "relationship_id", "assertion_id", "subject_object_id", "predicate",
        "object_object_id", "evidence_ref_id", "source_artifact_id",
        "source_revision_id", "source_span_ref_id", "source_locator", "actor",
    )
    @classmethod
    def _bounded_ids(cls, value: str, info: ValidationInfo) -> str:
        return _id(value, info.field_name or "field")

    @field_validator("requested_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("parent_payload_sha256")
    @classmethod
    def _parent_digest(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("parent_payload_sha256 must be a lowercase SHA-256 digest")
        return value


class AdoptedAssertionWithdrawalReceiptV1(DungeonMindModel):
    """Immutable terminal proof of one withdrawal and its graph publication."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_adopted_assertion_withdrawal_receipt_v1"] = (
        ADOPTED_ASSERTION_WITHDRAWAL_RECEIPT_V1
    )
    operation_id: str
    world_id: str
    adoption_id: str
    request_sha256: str
    adoption_receipt_fingerprint: str
    parent_revision_id: str
    parent_payload_sha256: str
    published_revision_id: str
    relationship_id: str
    assertion_id: str
    subject_object_id: str
    predicate: str
    object_object_id: str
    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str
    source_span_ref_id: str
    source_locator: str
    disposition: Literal["unsupported_by_bound_source"] = "unsupported_by_bound_source"
    actor: str
    completed_at: datetime

    @field_validator(
        "operation_id", "world_id", "adoption_id", "parent_revision_id",
        "published_revision_id", "relationship_id", "assertion_id", "evidence_ref_id",
        "subject_object_id", "predicate", "object_object_id",
        "source_artifact_id", "source_revision_id", "source_span_ref_id",
        "source_locator", "actor",
    )
    @classmethod
    def _bounded_ids(cls, value: str, info: ValidationInfo) -> str:
        return _id(value, info.field_name or "field")

    @field_validator("request_sha256", "adoption_receipt_fingerprint", "parent_payload_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("request_sha256 must be a lowercase SHA-256 digest")
        return value

    @field_validator("completed_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)
