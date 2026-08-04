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

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_BINDING_ID = re.compile(r"^mechbind:[0-9a-f]{32}$")
_REVISION_ID = re.compile(r"^rev:[0-9a-f]{32}$")
_OBJECT_ID = re.compile(r"^obj:[A-Za-z0-9._:-]+$")
_RELATIONSHIP_ID = re.compile(r"^rel:[A-Za-z0-9._:-]+$")
_OPAQUE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


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


def _validate_json_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Reject non-JSON payload values without echoing the rejected value."""
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        raise ValueError("mechanics_payload must be finite JSON") from None
    return value


def _require_sorted_unique(values: list[str], *, field_name: str) -> list[str]:
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
    ruleset_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    resource_revision: str = Field(min_length=1)
    resource_schema: str = Field(min_length=1)
    media_type: Literal["application/json"] = "application/json"
    payload_sha256: str = Field(min_length=64, max_length=64)

    @field_validator(
        "ruleset_id",
        "provider_id",
        "resource_id",
        "resource_revision",
        "resource_schema",
    )
    @classmethod
    def _validate_identity(cls, value: str, info: Any) -> str:
        return _validate_opaque_token(value, field_name=info.field_name)

    @field_validator("payload_sha256")
    @classmethod
    def _validate_payload_sha256(cls, value: str) -> str:
        if not _SHA256_HEX.fullmatch(value):
            raise ValueError("payload_sha256 must be exactly 64 lowercase hex characters")
        return value


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

    @property
    def mechanics_payload_sha256(self) -> str:
        """Return the verified digest without adding a wire field."""
        return canonical_sha256(self.mechanics_payload)


__all__ = [
    "MECHANICS_RESOURCE_ENVELOPE_SCHEMA",
    "MECHANICS_RESOURCE_REF_SCHEMA",
    "THREAT_MECHANICS_BINDING_SCHEMA",
    "THREAT_MECHANICS_HYDRATION_SCHEMA",
    "DndMechanicsResourceEnvelope",
    "DndMechanicsResourceRef",
    "DndMechanicsResourceResolver",
    "DndThreatMechanicsBinding",
    "DndThreatMechanicsHydration",
]
