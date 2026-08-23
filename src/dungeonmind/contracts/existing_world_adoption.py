"""Existing-world adoption bundle, command, and terminal receipt contracts.

The bundle is a migration authority artifact supplied to an explicit
application seam. A SHA of the consumed canonical bytes proves identity of
that artifact; it does not prove the producer was authorized. The bundle
must not carry a self-asserted ``bundle_sha256``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base import DungeonMindModel
from .contribution import GraphContribution, GraphContributionV2
from .evidence import SourceArtifactV2, SourceRevision
from .identity import IdentityDecisionRecord, IdentityDecisionRecordV2

EXISTING_WORLD_ADOPTION_BUNDLE_SCHEMA = "dm_existing_world_adoption_bundle_v1"
EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA = "dm_existing_world_adoption_bundle_v2"
EXISTING_WORLD_ADOPTION_COMMAND_SCHEMA = "dm_existing_world_adoption_command_v1"
EXISTING_WORLD_ADOPTION_COMMAND_V2_SCHEMA = "dm_existing_world_adoption_command_v2"
EXISTING_WORLD_ADOPTION_RECEIPT_SCHEMA = "dm_existing_world_adoption_receipt_v1"
EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA = "dm_existing_world_adoption_receipt_v2"
EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA = "dm_existing_world_adoption_receipt_v3"
EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA = "dm_existing_world_adoption_receipt_v4"
EXISTING_WORLD_ADOPTION_MEMBERSHIP_MANIFEST_SCHEMA = "dm_existing_world_adoption_membership_manifest_v1"
EXISTING_WORLD_ADOPTION_SOURCE_CLASSIFICATION_REPAIR_SCHEMA = "dm_existing_world_adoption_source_classification_repair_v1"
EXISTING_WORLD_ADOPTION_SOURCE_ARTIFACT_CLASSIFICATION_CORRECTION_SCHEMA = "dm_existing_world_adoption_source_artifact_classification_correction_v1"
EXISTING_WORLD_ADOPTION_PROVENANCE_SCHEMA = "dm_existing_world_adoption_source_provenance_v1"
EXISTING_WORLD_ADOPTION_AUTHORITY_REF_SCHEMA = "dm_existing_world_adoption_authority_ref_v1"

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be a non-blank string")
    return value


def _require_digest(value: str, *, field_name: str) -> str:
    if not _SHA256_HEX.fullmatch(value):
        raise ValueError(f"{field_name} must be exactly 64 lowercase hex")
    return value


def _require_timezone_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


class ExistingWorldAdoptionAuthorityRefV1(DungeonMindModel):
    """One historical producer authority reference. Not a runtime import."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["dm_existing_world_adoption_authority_ref_v1"] = (
        EXISTING_WORLD_ADOPTION_AUTHORITY_REF_SCHEMA
    )
    schema_: str = Field(alias="schema")
    identifier: str
    sha256: str

    @field_validator("schema_", "identifier")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="authority_ref field")

    @field_validator("sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="authority_ref.sha256")


class ExistingWorldAdoptionSourceProvenanceV1(DungeonMindModel):
    """Producer binding sufficient for a successor export without importing Buddy."""

    schema_version: Literal["dm_existing_world_adoption_source_provenance_v1"] = (
        EXISTING_WORLD_ADOPTION_PROVENANCE_SCHEMA
    )
    producer_id: str
    producer_revision: str
    source_world_revision_id: str
    source_graph_payload_sha256: str
    authority_refs: list[ExistingWorldAdoptionAuthorityRefV1] = Field(default_factory=list)

    @field_validator("producer_id", "producer_revision", "source_world_revision_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="source_provenance field")

    @field_validator("source_graph_payload_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="source_graph_payload_sha256")


class ExistingWorldAdoptionBundleV1(DungeonMindModel):
    """Strict ``dm_existing_world_adoption_bundle_v1`` migration artifact."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_existing_world_adoption_bundle_v1"] = (
        EXISTING_WORLD_ADOPTION_BUNDLE_SCHEMA
    )
    adoption_id: str
    world_id: str
    source_provenance: ExistingWorldAdoptionSourceProvenanceV1
    graph_schema: str
    graph_payload: dict[str, Any]
    source_artifacts: list[SourceArtifactV2]
    source_revisions: list[SourceRevision]
    contributions: list[GraphContribution]
    identity_decisions: list[IdentityDecisionRecord]

    @field_validator("adoption_id", "world_id", "graph_schema")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="bundle identity field")

    @model_validator(mode="after")
    def _require_graph_payload(self) -> Self:
        if not self.graph_payload:
            raise ValueError("graph_payload must be a non-empty object")
        return self


class ExistingWorldAdoptionCommandV1(DungeonMindModel):
    """Internal repository command. Application-owned; not a transport request."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_existing_world_adoption_command_v1"] = (
        EXISTING_WORLD_ADOPTION_COMMAND_SCHEMA
    )
    bundle: ExistingWorldAdoptionBundleV1
    bundle_sha256: str
    expected_published_revision_id: str
    graph_payload_sha256: str
    requested_adopted_at: datetime

    @field_validator("bundle_sha256", "graph_payload_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="command digest")

    @field_validator("expected_published_revision_id")
    @classmethod
    def _revision_id(cls, value: str) -> str:
        return _require_nonblank(value, field_name="expected_published_revision_id")

    @field_validator("requested_adopted_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="requested_adopted_at")


class ExistingWorldAdoptionReceiptV1(DungeonMindModel):
    """Terminal historical correspondence for one existing-world adoption."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_existing_world_adoption_receipt_v1"] = (
        EXISTING_WORLD_ADOPTION_RECEIPT_SCHEMA
    )
    adoption_id: str
    world_id: str
    bundle_sha256: str
    source_provenance: ExistingWorldAdoptionSourceProvenanceV1
    published_revision_id: str
    graph_schema: str
    graph_payload_sha256: str
    adopted_at: datetime
    source_artifact_count: int
    source_revision_count: int
    contribution_count: int
    identity_decision_count: int

    @field_validator("adoption_id", "world_id", "published_revision_id", "graph_schema")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="receipt identity field")

    @field_validator("bundle_sha256", "graph_payload_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="receipt digest")

    @field_validator("adopted_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="adopted_at")

    @field_validator(
        "source_artifact_count",
        "source_revision_count",
        "contribution_count",
        "identity_decision_count",
    )
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("receipt counts must be non-negative")
        return value


class ExistingWorldAdoptionBundleV2(DungeonMindModel):
    """Strict ``dm_existing_world_adoption_bundle_v2`` migration artifact."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_existing_world_adoption_bundle_v2"] = (
        EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA
    )
    adoption_id: str
    world_id: str
    source_provenance: ExistingWorldAdoptionSourceProvenanceV1
    graph_schema: str
    graph_payload: dict[str, Any]
    source_artifacts: list[SourceArtifactV2]
    source_revisions: list[SourceRevision]
    contributions: list[GraphContributionV2]
    identity_decisions: list[IdentityDecisionRecordV2]

    @field_validator("adoption_id", "world_id", "graph_schema")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="bundle identity field")

    @model_validator(mode="after")
    def _require_graph_payload(self) -> Self:
        if not self.graph_payload:
            raise ValueError("graph_payload must be a non-empty object")
        return self


class ExistingWorldAdoptionCommandV2(DungeonMindModel):
    """Internal v2 repository command. Application-owned; not a transport request."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_existing_world_adoption_command_v2"] = (
        EXISTING_WORLD_ADOPTION_COMMAND_V2_SCHEMA
    )
    bundle: ExistingWorldAdoptionBundleV2
    bundle_sha256: str
    expected_published_revision_id: str
    graph_payload_sha256: str
    requested_adopted_at: datetime

    @field_validator("bundle_sha256", "graph_payload_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="command digest")

    @field_validator("expected_published_revision_id")
    @classmethod
    def _revision_id(cls, value: str) -> str:
        return _require_nonblank(value, field_name="expected_published_revision_id")

    @field_validator("requested_adopted_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="requested_adopted_at")


class ExistingWorldAdoptionReceiptV2(DungeonMindModel):
    """Terminal historical correspondence for one v2 existing-world adoption."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_existing_world_adoption_receipt_v2"] = (
        EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA
    )
    adoption_id: str
    world_id: str
    bundle_sha256: str
    source_provenance: ExistingWorldAdoptionSourceProvenanceV1
    published_revision_id: str
    graph_schema: str
    graph_payload_sha256: str
    adopted_at: datetime
    source_artifact_count: int
    source_revision_count: int
    contribution_count: int
    identity_decision_count: int

    @field_validator("adoption_id", "world_id", "published_revision_id", "graph_schema")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="receipt identity field")

    @field_validator("bundle_sha256", "graph_payload_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="receipt digest")

    @field_validator("adopted_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="adopted_at")

    @field_validator(
        "source_artifact_count",
        "source_revision_count",
        "contribution_count",
        "identity_decision_count",
    )
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("receipt counts must be non-negative")
        return value


class ExistingWorldAdoptionReceiptV3(ExistingWorldAdoptionReceiptV2):
    """Terminal historical correspondence strengthened by one exact
    adopted-membership checkpoint.

    Every v2 field retains its semantics; the four counts remain diagnostics
    but are no longer sufficient proof of exact membership.
    ``membership_sha256`` is computed at adoption (or at steward-supervised
    v2→v3 promotion) from the exact sealed bundle's four durable history
    families — source artifacts, source revisions, contributions, and
    identity decisions — as sorted ``(record_id, record_fingerprint)`` pairs
    under the domain-separated ``dm_existing_world_adoption_membership_v1``
    canonical payload. Correspondence recomputes the current durable
    membership digest before any ``STALE`` classification is legal.
    """

    schema_version: Literal["dm_existing_world_adoption_receipt_v3"] = (
        EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA
    )
    membership_sha256: str

    @field_validator("membership_sha256")
    @classmethod
    def _membership_digest(cls, value: str) -> str:
        return _require_digest(value, field_name="membership_sha256")


class ExistingWorldAdoptionMembershipManifestV1(DungeonMindModel):
    """Exact adopted-member manifest for one existing-world adoption.

    Contains sorted, unique exact IDs for the four adoption-time families:
    source artifacts, source revisions, contributions, and identity decisions.
    The manifest is derived only from the exact sealed bundle; it is not graph
    authority and does not make later records part of the adoption.
    """

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal["dm_existing_world_adoption_membership_manifest_v1"] = (
        EXISTING_WORLD_ADOPTION_MEMBERSHIP_MANIFEST_SCHEMA
    )
    source_artifact_ids: list[str]
    source_revision_ids: list[str]
    contribution_ids: list[str]
    identity_decision_ids: list[str]

    @field_validator(
        "source_artifact_ids",
        "source_revision_ids",
        "contribution_ids",
        "identity_decision_ids",
    )
    @classmethod
    def _sorted_unique_nonblank(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("manifest ID list must be non-empty")
        for item in value:
            _require_nonblank(item, field_name="manifest ID")
        if len(value) != len(set(value)):
            raise ValueError("manifest ID list must be unique")
        if value != sorted(value):
            raise ValueError("manifest ID list must be sorted")
        return value


class ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1(DungeonMindModel):
    """One exact source-artifact classification correction."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal[
        "dm_existing_world_adoption_source_artifact_classification_correction_v1"
    ] = EXISTING_WORLD_ADOPTION_SOURCE_ARTIFACT_CLASSIFICATION_CORRECTION_SCHEMA
    source_artifact_id: str
    original_record_fingerprint: str
    effective_record_fingerprint: str
    changed_fields: list[Literal["visibility", "campaign_id"]]
    original_visibility: str | None
    effective_visibility: str | None
    original_campaign_id: str | None
    effective_campaign_id: str | None

    @field_validator("source_artifact_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="source_artifact_id")

    @field_validator("original_record_fingerprint", "effective_record_fingerprint")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="record_fingerprint")

    @field_validator("changed_fields")
    @classmethod
    def _closed_changed_fields(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("changed_fields must be non-empty")
        allowed = {"visibility", "campaign_id"}
        for field in value:
            if field not in allowed:
                raise ValueError(f"changed_fields contains unsupported field {field!r}")
        if len(value) != len(set(value)):
            raise ValueError("changed_fields must be unique")
        return value


class ExistingWorldAdoptionSourceClassificationRepairV1(DungeonMindModel):
    """One explicit source-classification repair record."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal[
        "dm_existing_world_adoption_source_classification_repair_v1"
    ] = EXISTING_WORLD_ADOPTION_SOURCE_CLASSIFICATION_REPAIR_SCHEMA
    repair_id: str
    reason_code: Literal["fix_forward_preexisting_source_classification_mutation"] = (
        "fix_forward_preexisting_source_classification_mutation"
    )
    repaired_at: datetime
    observed_pre_repair_membership_sha256: str
    effective_membership_sha256: str
    corrections: list[ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1]

    @field_validator("repair_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="repair_id")

    @field_validator("repaired_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="repaired_at")

    @field_validator("observed_pre_repair_membership_sha256", "effective_membership_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="membership digest")

    @field_validator("corrections")
    @classmethod
    def _unique_corrections(
        cls, value: list[ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1]
    ) -> list[ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1]:
        if not value:
            raise ValueError("corrections must be non-empty")
        seen: set[str] = set()
        for correction in value:
            if correction.source_artifact_id in seen:
                raise ValueError(
                    f"duplicate correction for source_artifact_id {correction.source_artifact_id!r}"
                )
            seen.add(correction.source_artifact_id)
        return value


class ExistingWorldAdoptionReceiptV4(ExistingWorldAdoptionReceiptV3):
    """Terminal historical correspondence for one repaired existing-world adoption.

    V4 retains every prior adoption fact and adds explicit repair authority:

    - ``membership_sha256`` = original adoption-time checkpoint M0 (historical
      truth; never rewritten from current rows)
    - ``effective_membership_sha256`` = current sanctioned checkpoint M1
      (recomputed from the exact adopted member set after the authorized repair)
    - ``membership_manifest`` = exact adopted-member IDs from the sealed bundle
    - ``source_classification_repair`` = one explicit repair record

    The distinction between M0 and M1 is the center of the V4 contract: a digest
    can prove payload equality but cannot select which current rows belong to
    the original adoption once the world has descendants. The manifest makes
    the repair checkpoint independently verifiable without asking frozen Buddy
    what was adopted.
    """

    schema_version: Literal["dm_existing_world_adoption_receipt_v4"] = (
        EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA
    )
    effective_membership_sha256: str
    membership_manifest: ExistingWorldAdoptionMembershipManifestV1
    source_classification_repair: ExistingWorldAdoptionSourceClassificationRepairV1

    @field_validator("effective_membership_sha256")
    @classmethod
    def _effective_membership_digest(cls, value: str) -> str:
        return _require_digest(value, field_name="effective_membership_sha256")

    @model_validator(mode="after")
    def _repair_digest_consistency(self) -> Self:
        if (
            self.source_classification_repair.effective_membership_sha256
            != self.effective_membership_sha256
        ):
            raise ValueError(
                "repair record effective_membership_sha256 must equal receipt effective_membership_sha256"
            )
        if (
            self.source_classification_repair.observed_pre_repair_membership_sha256
            != self.membership_sha256
        ):
            raise ValueError(
                "repair record observed_pre_repair_membership_sha256 must equal receipt membership_sha256"
            )
        return self


def _canonicalize_adoption_bundle_payload(payload: dict[str, Any]) -> bytes:
    payload["source_artifacts"] = sorted(
        payload["source_artifacts"],
        key=lambda item: item["source_artifact_id"],
    )
    payload["source_revisions"] = sorted(
        payload["source_revisions"],
        key=lambda item: item["source_revision_id"],
    )
    payload["contributions"] = sorted(
        payload["contributions"],
        key=lambda item: item["contribution_id"],
    )
    payload["identity_decisions"] = sorted(
        payload["identity_decisions"],
        key=lambda item: item["decision_id"],
    )
    provenance = payload["source_provenance"]
    provenance["authority_refs"] = sorted(
        provenance["authority_refs"],
        key=lambda item: (item["schema"], item["identifier"], item["sha256"]),
    )
    return (_canonical_json(payload) + "\n").encode("utf-8")


def existing_world_adoption_bundle_canonical_bytes(
    bundle: ExistingWorldAdoptionBundleV1,
) -> bytes:
    """Serialize one v1 bundle as UTF-8 canonical JSON with a trailing newline.

    Lists with durable identities are sorted so two semantically identical
    bundles cannot differ only by caller array order.
    """
    payload = bundle.model_dump(mode="json", by_alias=True)
    return _canonicalize_adoption_bundle_payload(payload)


def existing_world_adoption_bundle_v2_canonical_bytes(
    bundle: ExistingWorldAdoptionBundleV2,
) -> bytes:
    """Serialize one v2 bundle as UTF-8 canonical JSON with a trailing newline."""
    payload = bundle.model_dump(mode="json", by_alias=True)
    return _canonicalize_adoption_bundle_payload(payload)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
