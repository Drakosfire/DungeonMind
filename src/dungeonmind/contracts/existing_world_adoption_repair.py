"""Existing-world adoption source-classification repair intent and command values.

The repair intent is explicit, narrow, and human-reviewable. The caller supplies
the exact sealed bundle bytes plus a strict repair intent naming exact source
artifact IDs and only two possible operations: set_visibility_to_gm and/or
clear_campaign_id.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Self

from pydantic import ConfigDict, field_validator, model_validator

from .base import DungeonMindModel
from .evidence import SourceArtifactV2
from .existing_world_adoption import (
    ExistingWorldAdoptionMembershipManifestV1,
    ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1,
    _require_digest,
    _require_nonblank,
    _require_timezone_aware,
)

EXISTING_WORLD_ADOPTION_SOURCE_CLASSIFICATION_REPAIR_INTENT_SCHEMA = (
    "dm_existing_world_adoption_source_classification_repair_intent_v1"
)
EXISTING_WORLD_ADOPTION_SOURCE_CLASSIFICATION_REPAIR_COMMAND_SCHEMA = (
    "dm_existing_world_adoption_source_classification_repair_command_v1"
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(DungeonMindModel):
    """One exact source-artifact classification repair intent."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    source_artifact_id: str
    set_visibility_to_gm: bool = False
    clear_campaign_id: bool = False

    @field_validator("source_artifact_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="source_artifact_id")

    @model_validator(mode="after")
    def _at_least_one_operation(self) -> Self:
        if not self.set_visibility_to_gm and not self.clear_campaign_id:
            raise ValueError(
                "at least one of set_visibility_to_gm or clear_campaign_id must be true"
            )
        return self


class ExistingWorldAdoptionSourceClassificationRepairIntentV1(DungeonMindModel):
    """Strict repair intent for one existing-world adoption source-classification repair.

    The intent names exact source artifact IDs and only two possible operations:
    set_visibility_to_gm and/or clear_campaign_id. At least one must be true for
    each named artifact.
    """

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal[
        "dm_existing_world_adoption_source_classification_repair_intent_v1"
    ] = EXISTING_WORLD_ADOPTION_SOURCE_CLASSIFICATION_REPAIR_INTENT_SCHEMA
    world_id: str
    adoption_id: str
    repairs: list[ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1]

    @field_validator("world_id", "adoption_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="repair intent identity field")

    @field_validator("repairs")
    @classmethod
    def _unique_repairs(
        cls, value: list[ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1]
    ) -> list[ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1]:
        if not value:
            raise ValueError("repairs must be non-empty")
        seen: set[str] = set()
        for repair in value:
            if repair.source_artifact_id in seen:
                raise ValueError(
                    f"duplicate repair for source_artifact_id {repair.source_artifact_id!r}"
                )
            seen.add(repair.source_artifact_id)
        return value


class ExistingWorldAdoptionSourceClassificationRepairCommandV1(DungeonMindModel):
    """Internal repository command for one source-classification repair.

    Application-owned; not a transport request. Contains the original sealed
    facts, exact target artifacts, manifest, expected identities, and repaired_at.
    The repository observes ``observed_pre_repair_membership_sha256`` inside the
    writer-excluding boundary and must not take that digest from the caller.
    """

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    schema_version: Literal[
        "dm_existing_world_adoption_source_classification_repair_command_v1"
    ] = EXISTING_WORLD_ADOPTION_SOURCE_CLASSIFICATION_REPAIR_COMMAND_SCHEMA
    world_id: str
    adoption_id: str
    bundle_sha256: str
    sealed_bundle_bytes: bytes
    repair_intent: ExistingWorldAdoptionSourceClassificationRepairIntentV1
    membership_manifest: ExistingWorldAdoptionMembershipManifestV1
    target_artifacts: list[SourceArtifactV2]
    corrections: list[ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1]
    original_membership_sha256: str
    effective_membership_sha256: str
    repair_id: str
    repaired_at: datetime

    @field_validator("world_id", "adoption_id", "repair_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="repair command identity field")

    @field_validator(
        "bundle_sha256",
        "original_membership_sha256",
        "effective_membership_sha256",
    )
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_digest(value, field_name="repair command digest")

    @field_validator("repaired_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, field_name="repaired_at")

    @field_validator("target_artifacts")
    @classmethod
    def _unique_targets(cls, value: list[SourceArtifactV2]) -> list[SourceArtifactV2]:
        if not value:
            raise ValueError("target_artifacts must be non-empty")
        seen: set[str] = set()
        for artifact in value:
            if artifact.source_artifact_id in seen:
                raise ValueError(
                    f"duplicate target artifact {artifact.source_artifact_id!r}"
                )
            seen.add(artifact.source_artifact_id)
        return value

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
                    f"duplicate correction for source_artifact_id "
                    f"{correction.source_artifact_id!r}"
                )
            seen.add(correction.source_artifact_id)
        return value

    @model_validator(mode="after")
    def _targets_match_corrections(self) -> Self:
        target_ids = {item.source_artifact_id for item in self.target_artifacts}
        correction_ids = {item.source_artifact_id for item in self.corrections}
        if target_ids != correction_ids:
            raise ValueError("target_artifacts must cover exactly the correction ids")
        intent_ids = {item.source_artifact_id for item in self.repair_intent.repairs}
        if intent_ids != correction_ids:
            raise ValueError("repair intent ids must cover exactly the correction ids")
        return self