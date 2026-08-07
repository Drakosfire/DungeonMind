"""World-object mechanics binding and statblock attachment contracts.

Hostility-independent exact mechanics attachment for cutover work pinned to
``dnd5e-profile-v3`` / ``world-object-v1``. Historical B.3a Threat bindings
remain in ``mechanics_resources`` and are unchanged.
"""

from __future__ import annotations

import re
from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from dungeonmind.contracts.base import DungeonMindModel
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256

from .mechanics_resources import (
    DndMechanicsResourceRef,
    _validate_opaque_token,
)
from .vocabulary import DndVocabularyRef

WORLD_OBJECT_MECHANICS_BINDING_SCHEMA = "dmdnd_world_object_mechanics_binding_v1"
WORLD_OBJECT_MECHANICS_HYDRATION_SCHEMA = "dmdnd_world_object_mechanics_hydration_v1"
STATBLOCK_MECHANICS_ATTACHMENT_SCHEMA = "dmdnd_statblock_mechanics_attachment_v1"

WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS = frozenset({"dnd5e:threat", "dnd5e:npc"})
StatblockMechanicsRole = Literal[
    "primary",
    "alternate",
    "phase",
    "encounter_variant",
    "template",
]

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_BINDING_ID = re.compile(r"^mechbind:[0-9a-f]{32}$")
_REVISION_ID = re.compile(r"^rev:[0-9a-f]{32}$")
_OBJECT_ID = re.compile(r"^obj:[A-Za-z0-9._:-]+$")


def _world_object_binding_id_material(
    *,
    world_id: str,
    graph_revision_id: str,
    graph_payload_sha256: str,
    semantic_profile: SemanticProfileRef,
    world_object_vocabulary: DndVocabularyRef,
    object_id: str,
    object_kind: str,
    visibility: str,
    resource_ref: DndMechanicsResourceRef,
) -> dict[str, Any]:
    return {
        "schema": WORLD_OBJECT_MECHANICS_BINDING_SCHEMA,
        "world_id": world_id,
        "graph_revision_id": graph_revision_id,
        "graph_payload_sha256": graph_payload_sha256,
        "semantic_profile": semantic_profile.model_dump(mode="json"),
        "world_object_vocabulary": world_object_vocabulary.model_dump(mode="json"),
        "object_id": object_id,
        "object_kind": object_kind,
        "visibility": visibility,
        "resource_ref": resource_ref.model_dump(mode="json"),
    }


def derive_world_object_mechanics_binding_id(
    *,
    world_id: str,
    graph_revision_id: str,
    graph_payload_sha256: str,
    semantic_profile: SemanticProfileRef,
    world_object_vocabulary: DndVocabularyRef,
    object_id: str,
    object_kind: str,
    visibility: str,
    resource_ref: DndMechanicsResourceRef,
) -> str:
    """Derive the content-addressed binding ID for one exact attachment."""
    material = _world_object_binding_id_material(
        world_id=world_id,
        graph_revision_id=graph_revision_id,
        graph_payload_sha256=graph_payload_sha256,
        semantic_profile=semantic_profile,
        world_object_vocabulary=world_object_vocabulary,
        object_id=object_id,
        object_kind=object_kind,
        visibility=visibility,
        resource_ref=resource_ref,
    )
    return f"mechbind:{canonical_sha256(material)[:32]}"


class DndWorldObjectMechanicsBinding(DungeonMindModel):
    """Exact world-object ↔ mechanics binding without hostility eligibility."""

    model_config = ConfigDict(hide_input_in_errors=True)

    schema_version: Literal["dmdnd_world_object_mechanics_binding_v1"] = (
        WORLD_OBJECT_MECHANICS_BINDING_SCHEMA
    )
    binding_id: str
    world_id: str = Field(min_length=1)
    graph_revision_id: str
    graph_payload_sha256: str = Field(min_length=64, max_length=64)
    semantic_profile: SemanticProfileRef
    world_object_vocabulary: DndVocabularyRef
    object_id: str
    object_kind: Literal["dnd5e:threat", "dnd5e:npc"]
    visibility: Literal["gm"] = "gm"
    resource_ref: DndMechanicsResourceRef

    @field_validator("binding_id")
    @classmethod
    def _validate_binding_id(cls, value: str) -> str:
        if not _BINDING_ID.fullmatch(value):
            raise ValueError("binding_id must be mechbind:<32 lowercase hex>")
        return value

    @field_validator("world_id")
    @classmethod
    def _validate_world_id(cls, value: str) -> str:
        return _validate_opaque_token(value, field_name="world_id")

    @field_validator("graph_revision_id")
    @classmethod
    def _validate_graph_revision_id(cls, value: str) -> str:
        if not _REVISION_ID.fullmatch(value):
            raise ValueError("graph_revision_id must be rev:<32 lowercase hex>")
        return value

    @field_validator("graph_payload_sha256")
    @classmethod
    def _validate_graph_payload_sha256(cls, value: str) -> str:
        if not _SHA256_HEX.fullmatch(value):
            raise ValueError(
                "graph_payload_sha256 must be exactly 64 lowercase hex characters"
            )
        return value

    @field_validator("object_id")
    @classmethod
    def _validate_object_id(cls, value: str) -> str:
        if not _OBJECT_ID.fullmatch(value):
            raise ValueError("object_id must be obj:<opaque identity>")
        return value

    @model_validator(mode="after")
    def _resource_ref_is_complete(self) -> Self:
        if self.resource_ref.ruleset_id != "dnd5e":
            raise ValueError("resource_ref.ruleset_id must be dnd5e")
        return self

    @model_validator(mode="after")
    def _binding_id_matches_material(self) -> Self:
        expected = derive_world_object_mechanics_binding_id(
            world_id=self.world_id,
            graph_revision_id=self.graph_revision_id,
            graph_payload_sha256=self.graph_payload_sha256,
            semantic_profile=self.semantic_profile,
            world_object_vocabulary=self.world_object_vocabulary,
            object_id=self.object_id,
            object_kind=self.object_kind,
            visibility=self.visibility,
            resource_ref=self.resource_ref,
        )
        if self.binding_id != expected:
            raise ValueError("binding_id must match derived content address")
        return self


class DndWorldObjectMechanicsHydration(DungeonMindModel):
    """Verified exact mechanics bytes for one world-object binding."""

    model_config = ConfigDict(hide_input_in_errors=True)

    schema_version: Literal["dmdnd_world_object_mechanics_hydration_v1"] = (
        WORLD_OBJECT_MECHANICS_HYDRATION_SCHEMA
    )
    binding: DndWorldObjectMechanicsBinding
    mechanics_payload: dict[str, Any]

    @field_validator("mechanics_payload")
    @classmethod
    def _validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            from dungeonmind.domain.canonical import canonical_json

            canonical_json(value)
        except (TypeError, ValueError):
            raise ValueError("mechanics_payload must be finite JSON") from None
        return value

    @model_validator(mode="after")
    def _payload_matches_binding_ref(self) -> Self:
        if (
            canonical_sha256(self.mechanics_payload)
            != self.binding.resource_ref.payload_sha256
        ):
            raise ValueError("mechanics_payload digest must match resource_ref")
        return self

    @property
    def mechanics_payload_sha256(self) -> str:
        return self.binding.resource_ref.payload_sha256


class DndStatblockMechanicsAttachment(DungeonMindModel):
    """Statblock specialization of one exact world-object mechanics binding."""

    model_config = ConfigDict(hide_input_in_errors=True)

    schema_version: Literal["dmdnd_statblock_mechanics_attachment_v1"] = (
        STATBLOCK_MECHANICS_ATTACHMENT_SCHEMA
    )
    binding: DndWorldObjectMechanicsBinding
    role: StatblockMechanicsRole
    phase_key: str | None = None

    @model_validator(mode="after")
    def _phase_key_rules(self) -> Self:
        if self.role == "phase":
            phase_key = self.phase_key
            if phase_key is None or not phase_key.strip():
                raise ValueError("phase_key is required when role is phase")
            if phase_key != phase_key.strip():
                raise ValueError("phase_key must not include surrounding whitespace")
        elif self.phase_key is not None:
            raise ValueError("phase_key is only allowed when role is phase")
        return self


def enumerate_statblock_mechanics_attachments(
    attachments: list[DndStatblockMechanicsAttachment],
) -> list[DndStatblockMechanicsAttachment]:
    """Return a deterministic enumeration of every attachment (no first-winner).

    Ordering is stable by binding_id, then role, then phase_key (empty last).
    Callers that need a single Combat activation must choose explicitly later;
    this helper never selects.
    """
    if not attachments:
        return []
    binding_ids = [item.binding.binding_id for item in attachments]
    if len(binding_ids) != len(set(binding_ids)):
        raise ValueError("attachments must not share binding_id values")

    def _sort_key(item: DndStatblockMechanicsAttachment) -> tuple[str, str, str]:
        return (
            item.binding.binding_id,
            item.role,
            item.phase_key or "",
        )

    return sorted(attachments, key=_sort_key)
