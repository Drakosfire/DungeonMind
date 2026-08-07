"""Strict D&D mechanics-resource identity and hydration contracts.

Mechanics are producer-owned external data.  These contracts carry only
opaque resource identity, content digests, and the exact graph-pinned binding;
they never carry locators, credentials, graph prose, or provider metadata
beyond the opaque identity fields needed to resolve one resource.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal, Protocol, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from dungeonmind.contracts.base import DungeonMindModel
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.domain.canonical import canonical_json, canonical_sha256

from .vocabulary import DndVocabularyRef

MECHANICS_RESOURCE_REF_SCHEMA = "dmdnd_mechanics_resource_ref_v1"
MECHANICS_RESOURCE_ENVELOPE_SCHEMA = "dmdnd_mechanics_resource_envelope_v1"
THREAT_MECHANICS_BINDING_SCHEMA = "dmdnd_threat_mechanics_binding_v1"
THREAT_MECHANICS_HYDRATION_SCHEMA = "dmdnd_threat_mechanics_hydration_v1"

# Exact DungeonMind statblock-v1 resource identity (PR #21). Shared by the
# provider resolver and DndStatblockMechanicsAttachment so the shapes cannot drift.
STATBLOCKS_PROVIDER_ID = "dungeonmind.statblocks"
STATBLOCKS_RESOURCE_SCHEMA = "dungeonmind.dungeonbuddy-statblocks.1.0.0"
STATBLOCKS_MEDIA_TYPE = "application/json"

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_BINDING_ID = re.compile(r"^mechbind:[0-9a-f]{32}$")
_REVISION_ID = re.compile(r"^rev:[0-9a-f]{32}$")
_OBJECT_ID = re.compile(r"^obj:[A-Za-z0-9._:-]+$")
_RELATIONSHIP_ID = re.compile(r"^rel:[A-Za-z0-9._:-]+$")
_OPAQUE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_LOWER_IDENTITY_TOKEN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_STATBLOCK_RESOURCE_ID = re.compile(r"^sb_[a-z0-9]+$")
_STATBLOCK_REVISION_ID = re.compile(r"^rev_[a-z0-9]+$")


def _validate_opaque_token(value: str, *, field_name: str) -> str:
    """Validate identity tokens without admitting locators or floating refs."""
    lowered = value.casefold()
    if not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be a non-blank opaque token")
    if lowered == "latest":
        raise ValueError(f"{field_name} must not be 'latest'")
    if "://" in value or lowered.startswith(("http:", "https:", "file:", "ftp:")):
        raise ValueError(f"{field_name} must not be a URI")
    if "/" in value or "\\" in value:
        raise ValueError(f"{field_name} must not be a path")
    if not _OPAQUE_TOKEN.fullmatch(value):
        raise ValueError(f"{field_name} must be an opaque identity token")
    return value


def _validate_canonical_token(value: str, *, field_name: str) -> str:
    """Validate a lowercase canonical token, not a locator."""
    if not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be a non-blank identity token")
    if value.casefold() == "latest":
        raise ValueError(f"{field_name} must not be 'latest'")
    if "://" in value or value.casefold().startswith(
        ("http:", "https:", "file:", "ftp:")
    ):
        raise ValueError(f"{field_name} must not be a URI")
    if "/" in value or "\\" in value:
        raise ValueError(f"{field_name} must not be a path")
    if not _LOWER_IDENTITY_TOKEN.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase identity token")
    return value


def _validate_json_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Reject non-JSON payload values without echoing the rejected value."""
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        raise ValueError("mechanics_payload must be finite JSON") from None
    return value


def _require_sorted_unique(values: list[str], *, field_name: str) -> list[str]:
    if not values:
        raise ValueError(f"{field_name} must be non-empty")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must be unique")
    if values != sorted(values):
        raise ValueError(f"{field_name} must be sorted deterministically")
    return values


class DndMechanicsResourceRef(DungeonMindModel):
    """Opaque identity and digest for one producer-owned mechanics resource."""

    model_config = ConfigDict(hide_input_in_errors=True)

    schema_version: Literal["dmdnd_mechanics_resource_ref_v1"] = (
        MECHANICS_RESOURCE_REF_SCHEMA
    )
    ruleset_id: Literal["dnd5e"]
    provider_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    resource_revision: str = Field(min_length=1)
    resource_schema: str = Field(min_length=1)
    media_type: Literal["application/json"] = "application/json"
    payload_sha256: str = Field(min_length=64, max_length=64)

    @field_validator("provider_id", "resource_schema")
    @classmethod
    def _validate_canonical_identity(cls, value: str, info: Any) -> str:
        return _validate_canonical_token(value, field_name=info.field_name)

    @field_validator("resource_id", "resource_revision")
    @classmethod
    def _validate_opaque_identity(cls, value: str, info: Any) -> str:
        return _validate_opaque_token(value, field_name=info.field_name)

    @field_validator("payload_sha256")
    @classmethod
    def _validate_payload_sha256(cls, value: str) -> str:
        if not _SHA256_HEX.fullmatch(value):
            raise ValueError("payload_sha256 must be exactly 64 lowercase hex characters")
        return value


def is_exact_dungeonmind_statblock_resource_ref(
    resource_ref: DndMechanicsResourceRef,
) -> bool:
    """Return True iff ``resource_ref`` matches the PR #21 exact statblock identity.

    Shared by the provider resolver and ``DndStatblockMechanicsAttachment`` so
    specialization and resolution cannot drift on provider/schema/id grammar.
    """
    try:
        return (
            resource_ref.ruleset_id == "dnd5e"
            and resource_ref.provider_id == STATBLOCKS_PROVIDER_ID
            and resource_ref.resource_schema == STATBLOCKS_RESOURCE_SCHEMA
            and resource_ref.media_type == STATBLOCKS_MEDIA_TYPE
            and bool(_STATBLOCK_RESOURCE_ID.fullmatch(resource_ref.resource_id))
            and bool(_STATBLOCK_REVISION_ID.fullmatch(resource_ref.resource_revision))
        )
    except Exception:
        return False


def _binding_id_material(
    *,
    world_id: str,
    graph_revision_id: str,
    graph_payload_sha256: str,
    semantic_profile: SemanticProfileRef,
    threat_vocabulary: DndVocabularyRef,
    object_id: str,
    object_kind: str,
    threat_relationship_ids: list[str],
    visibility: str,
    resource_ref: DndMechanicsResourceRef,
) -> dict[str, Any]:
    return {
        "schema": THREAT_MECHANICS_BINDING_SCHEMA,
        "world_id": world_id,
        "graph_revision_id": graph_revision_id,
        "graph_payload_sha256": graph_payload_sha256,
        "semantic_profile": semantic_profile.model_dump(mode="json"),
        "threat_vocabulary": threat_vocabulary.model_dump(mode="json"),
        "object_id": object_id,
        "object_kind": object_kind,
        "threat_relationship_ids": list(threat_relationship_ids),
        "resource_ref": resource_ref.model_dump(mode="json"),
        "visibility": visibility,
    }


def _derive_threat_mechanics_binding_id(
    *,
    world_id: str,
    graph_revision_id: str,
    graph_payload_sha256: str,
    semantic_profile: SemanticProfileRef,
    threat_vocabulary: DndVocabularyRef,
    object_id: str,
    object_kind: str,
    threat_relationship_ids: list[str],
    visibility: str,
    resource_ref: DndMechanicsResourceRef,
) -> str:
    """Derive the binding ID without repairing relationship ordering."""
    _require_sorted_unique(
        threat_relationship_ids,
        field_name="threat_relationship_ids",
    )
    material = _binding_id_material(
        world_id=world_id,
        graph_revision_id=graph_revision_id,
        graph_payload_sha256=graph_payload_sha256,
        semantic_profile=semantic_profile,
        threat_vocabulary=threat_vocabulary,
        object_id=object_id,
        object_kind=object_kind,
        threat_relationship_ids=threat_relationship_ids,
        resource_ref=resource_ref,
        visibility=visibility,
    )
    return f"mechbind:{canonical_sha256(material)[:32]}"


class DndMechanicsResourceEnvelope(DungeonMindModel):
    """One resolved resource ref plus its producer-owned JSON payload."""

    model_config = ConfigDict(hide_input_in_errors=True)

    schema_version: Literal["dmdnd_mechanics_resource_envelope_v1"] = (
        MECHANICS_RESOURCE_ENVELOPE_SCHEMA
    )
    resource_ref: DndMechanicsResourceRef
    mechanics_payload: dict[str, Any]

    @field_validator("mechanics_payload")
    @classmethod
    def _validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_json_payload(value)

    @model_validator(mode="after")
    def _payload_matches_resource_ref(self) -> Self:
        if canonical_sha256(self.mechanics_payload) != self.resource_ref.payload_sha256:
            raise ValueError("mechanics_payload digest must match resource_ref")
        return self


class DndMechanicsResourceResolver(Protocol):
    """Caller-owned, one-call resolver for one exact opaque resource ref."""

    def resolve(
        self, resource_ref: DndMechanicsResourceRef
    ) -> DndMechanicsResourceEnvelope | Mapping[str, Any] | None: ...


class DndThreatMechanicsBinding(DungeonMindModel):
    """Non-durable, content-addressed binding of one Threat to one resource."""

    model_config = ConfigDict(hide_input_in_errors=True)

    schema_version: Literal["dmdnd_threat_mechanics_binding_v1"] = (
        THREAT_MECHANICS_BINDING_SCHEMA
    )
    binding_id: str
    world_id: str = Field(min_length=1)
    graph_revision_id: str
    graph_payload_sha256: str = Field(min_length=64, max_length=64)
    semantic_profile: SemanticProfileRef
    threat_vocabulary: DndVocabularyRef
    object_id: str
    object_kind: Literal["dnd5e:creature"] = "dnd5e:creature"
    threat_relationship_ids: list[str] = Field(min_length=1)
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

    @field_validator("threat_relationship_ids")
    @classmethod
    def _validate_relationship_ids(cls, value: list[str]) -> list[str]:
        for relationship_id in value:
            if not _RELATIONSHIP_ID.fullmatch(relationship_id):
                raise ValueError("threat_relationship_ids must contain rel IDs")
        return _require_sorted_unique(value, field_name="threat_relationship_ids")

    @model_validator(mode="after")
    def _resource_ref_is_complete(self) -> Self:
        if self.resource_ref.ruleset_id != "dnd5e":
            raise ValueError("resource_ref ruleset_id must be dnd5e")
        return self

    @model_validator(mode="after")
    def _binding_id_is_content_addressed(self) -> Self:
        expected_id = _derive_threat_mechanics_binding_id(
            world_id=self.world_id,
            graph_revision_id=self.graph_revision_id,
            graph_payload_sha256=self.graph_payload_sha256,
            semantic_profile=self.semantic_profile,
            threat_vocabulary=self.threat_vocabulary,
            object_id=self.object_id,
            object_kind=self.object_kind,
            threat_relationship_ids=self.threat_relationship_ids,
            resource_ref=self.resource_ref,
            visibility=self.visibility,
        )
        if self.binding_id != expected_id:
            raise ValueError("binding_id must match canonical binding derivation")
        return self


class DndThreatMechanicsHydration(DungeonMindModel):
    """Isolated, digest-verified mechanics bytes for one exact binding."""

    model_config = ConfigDict(hide_input_in_errors=True)

    schema_version: Literal["dmdnd_threat_mechanics_hydration_v1"] = (
        THREAT_MECHANICS_HYDRATION_SCHEMA
    )
    binding: DndThreatMechanicsBinding
    mechanics_payload: dict[str, Any]

    @field_validator("mechanics_payload")
    @classmethod
    def _validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_json_payload(value)

    @model_validator(mode="after")
    def _payload_matches_binding(self) -> Self:
        if (
            canonical_sha256(self.mechanics_payload)
            != self.binding.resource_ref.payload_sha256
        ):
            raise ValueError("mechanics_payload digest must match binding.resource_ref")
        return self

    @property
    def mechanics_payload_sha256(self) -> str:
        """Return the verified digest without adding a wire field."""
        return canonical_sha256(self.mechanics_payload)


__all__ = [
    "MECHANICS_RESOURCE_ENVELOPE_SCHEMA",
    "MECHANICS_RESOURCE_REF_SCHEMA",
    "STATBLOCKS_MEDIA_TYPE",
    "STATBLOCKS_PROVIDER_ID",
    "STATBLOCKS_RESOURCE_SCHEMA",
    "THREAT_MECHANICS_BINDING_SCHEMA",
    "THREAT_MECHANICS_HYDRATION_SCHEMA",
    "DndMechanicsResourceEnvelope",
    "DndMechanicsResourceRef",
    "DndMechanicsResourceResolver",
    "DndThreatMechanicsBinding",
    "DndThreatMechanicsHydration",
    "is_exact_dungeonmind_statblock_resource_ref",
]
