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
from typing import Any, Literal, Self, cast

from pydantic import ConfigDict, field_validator, model_validator

from .base import DungeonMindModel
from .contribution_review_v2 import ReviewedIdentityPublicationPreconditions

FINALIZED_REVIEW_PUBLICATION_COMMAND_SCHEMA = "dm_finalized_review_publication_command_v1"
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

    schema_version: Literal["dm_finalized_review_publication_v1"] = (
        FINALIZED_REVIEW_PUBLICATION_SCHEMA
    )
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

    schema_version: Literal["dm_finalized_review_publication_command_v1"] = (
        FINALIZED_REVIEW_PUBLICATION_COMMAND_SCHEMA
    )
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
            raise ValueError("expected_published_revision_id does not match publication content")
        return self


class GuardedFinalizedReviewPublicationCommand(FinalizedReviewPublicationCommand):
    reviewed_identity_preconditions: ReviewedIdentityPublicationPreconditions

    @model_validator(mode="after")
    def _guard_basis(self) -> Self:
        guard = self.reviewed_identity_preconditions
        if (
            guard.world_id != self.world_id
            or guard.expected_parent_revision_id != self.expected_parent_revision_id
        ):
            raise ValueError("publication guard differs from command basis")
        return self


def decode_finalized_review_publication_command(
    value: dict[str, Any],
) -> FinalizedReviewPublicationCommand:
    family = value.get("schema_version")
    guarded = "reviewed_identity_preconditions" in value
    if family == FINALIZED_REVIEW_PUBLICATION_COMMAND_SCHEMA:
        model = (
            GuardedFinalizedReviewPublicationCommand
            if guarded
            else FinalizedReviewPublicationCommand
        )
    elif family == "dm_finalized_review_publication_command_v2":
        model = (
            GuardedFinalizedReviewPublicationCommandV2
            if guarded
            else FinalizedReviewPublicationCommandV2
        )
    else:
        raise ValueError("unknown finalized publication command family")
    return model.model_validate(value)


# V1 definitions above stay byte-exact; the independent admission claim belongs
# only to these explicitly versioned families.
from .publication_admission import (  # noqa: E402
    CONTEXT_BYTES,
    GRAPH_BYTES,
    AdmissionPolicyRefV1,
    AdmissionValidatorRefV1,
    PublicationAdmissionContextV1,
    bounded_canonical,
    bounded_sha256,
    strict_json_loads,
)


class FinalizedReviewPublicationCommandV2(FinalizedReviewPublicationCommand):
    schema_version: Literal["dm_finalized_review_publication_command_v2"] = (
        "dm_finalized_review_publication_command_v2"
    )
    admission_policy_ref: AdmissionPolicyRefV1
    validator_ref: AdmissionValidatorRefV1

    @classmethod
    def model_validate_json(cls, json_data: str | bytes | bytearray, **kwargs: Any) -> Self:
        if type(json_data) not in (str, bytes, bytearray):
            raise ValueError("admission JSON input must be text or bytes")
        raw = (
            cast(str, json_data).encode("utf-8")
            if type(json_data) is str
            else bytes(cast(bytes | bytearray, json_data))
        )
        return cls.model_validate(
            strict_json_loads(raw, max_bytes=GRAPH_BYTES + CONTEXT_BYTES), **kwargs
        )

    @model_validator(mode="before")
    @classmethod
    def bounded_raw_graph(cls, value: Any) -> Any:
        if type(value) is dict and "graph_payload" in value:
            bounded_canonical(value["graph_payload"], max_bytes=GRAPH_BYTES)
        return value


class GuardedFinalizedReviewPublicationCommandV2(
    FinalizedReviewPublicationCommandV2, GuardedFinalizedReviewPublicationCommand
):
    pass


class FinalizedReviewPublicationV2(FinalizedReviewPublication):
    schema_version: Literal["dm_finalized_review_publication_v2"] = (
        "dm_finalized_review_publication_v2"
    )
    admission_policy_ref: AdmissionPolicyRefV1
    validator_ref: AdmissionValidatorRefV1
    admission_context: PublicationAdmissionContextV1
    admission_context_sha256: str

    @model_validator(mode="before")
    @classmethod
    def retained_families(cls, value: Any) -> Any:
        if type(value) is dict:
            PublicationAdmissionContextV1.model_validate(value.get("admission_context"))
            AdmissionPolicyRefV1.model_validate(value.get("admission_policy_ref"))
            AdmissionValidatorRefV1.model_validate(value.get("validator_ref"))
        return value

    @classmethod
    def model_validate_json(cls, json_data: str | bytes | bytearray, **kwargs: Any) -> Self:
        if type(json_data) not in (str, bytes, bytearray):
            raise ValueError("admission JSON input must be text or bytes")
        raw = (
            cast(str, json_data).encode("utf-8")
            if type(json_data) is str
            else bytes(cast(bytes | bytearray, json_data))
        )
        return cls.model_validate(
            strict_json_loads(raw, max_bytes=GRAPH_BYTES + CONTEXT_BYTES), **kwargs
        )

    @model_validator(mode="after")
    def context_binding(self) -> Self:
        context = self.admission_context
        if (
            bounded_sha256(context.model_dump(mode="json"), max_bytes=CONTEXT_BYTES)
            != self.admission_context_sha256
            or context.admission_policy_ref != self.admission_policy_ref
            or context.validator_ref != self.validator_ref
            or context.review_id != self.review_id
            or context.reviewed_contribution_sha256 != self.reviewed_contribution_sha256
            or context.review_intent_sha256 != self.review_intent_sha256
            or context.parent_revision_id != self.expected_parent_revision_id
            or context.child_revision_id != self.published_revision_id
            or context.parent_graph_payload_sha256 != self.parent_graph_payload_sha256
            or context.child_graph_payload_sha256 != self.graph_payload_sha256
        ):
            raise ValueError("admission receipt/context binding mismatch")
        return self


def decode_finalized_review_publication(value: dict[str, Any]) -> FinalizedReviewPublication:
    family = value.get("schema_version")
    if family == FINALIZED_REVIEW_PUBLICATION_SCHEMA:
        return FinalizedReviewPublication.model_validate(value)
    if family == "dm_finalized_review_publication_v2":
        return FinalizedReviewPublicationV2.model_validate(value)
    raise ValueError("unknown finalized publication family")


def publication_record_payload(value: FinalizedReviewPublication) -> dict[str, Any]:
    if isinstance(value, FinalizedReviewPublicationV2):
        PublicationAdmissionContextV1.model_validate(value.admission_context)
        AdmissionPolicyRefV1.model_validate(value.admission_policy_ref)
        AdmissionValidatorRefV1.model_validate(value.validator_ref)
    return value.model_dump(mode="json")
