"""Semantic profile identity contracts (data-only; no mechanics or hooks).

``SemanticProfileRef`` pins an immutable profile revision by content digest.
``SemanticProfileDescriptor`` enumerates admitted term namespaces. Neither
carries file paths, module names, URLs, or ``latest`` floating pointers.
"""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from .base import DungeonMindModel

SEMANTIC_PROFILE_REF_SCHEMA = "dm_semantic_profile_ref_v1"
SEMANTIC_PROFILE_DESCRIPTOR_SCHEMA = "dm_semantic_profile_v1"
SEMANTIC_PROFILE_REGISTRY_CONFIG_SCHEMA = "dm_semantic_profile_registry_config_v1"

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
# Lowercase dotted ids: dungeonmind.dnd5e, test.narrative
_PROFILE_ID = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
# Immutable revision tokens (no path/URI/latest)
_PROFILE_REVISION = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_NAMESPACE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


def _reject_locator_like(value: str, *, field_name: str) -> None:
    lowered = value.casefold()
    if lowered == "latest":
        raise ValueError(f"{field_name} must not be 'latest'")
    if any(ch.isspace() for ch in value):
        raise ValueError(f"{field_name} must not contain whitespace")
    if "/" in value or "\\" in value:
        raise ValueError(f"{field_name} must not contain path separators")
    if "://" in value or lowered.startswith(("http:", "https:", "file:", "ftp:")):
        raise ValueError(f"{field_name} must not be a URI")
    if value.endswith(".py") or value.startswith("dungeonmind_dnd."):
        raise ValueError(f"{field_name} must not be a module path")


class SemanticProfileRef(DungeonMindModel):
    """Pinned identity of a semantic profile revision (no locators)."""

    schema_version: Literal["dm_semantic_profile_ref_v1"] = SEMANTIC_PROFILE_REF_SCHEMA
    profile_id: str = Field(min_length=1)
    profile_revision: str = Field(min_length=1)
    descriptor_sha256: str = Field(min_length=64, max_length=64)

    @field_validator("profile_id")
    @classmethod
    def _validate_profile_id(cls, value: str) -> str:
        _reject_locator_like(value, field_name="profile_id")
        if not _PROFILE_ID.fullmatch(value):
            raise ValueError(
                "profile_id must be lowercase dotted "
                "(letters, digits, '.', '_', '-' only)"
            )
        return value

    @field_validator("profile_revision")
    @classmethod
    def _validate_profile_revision(cls, value: str) -> str:
        _reject_locator_like(value, field_name="profile_revision")
        if not _PROFILE_REVISION.fullmatch(value):
            raise ValueError(
                "profile_revision must be a non-empty immutable token "
                "(lowercase letters, digits, '.', '_', '-' only)"
            )
        return value

    @field_validator("descriptor_sha256")
    @classmethod
    def _validate_descriptor_sha256(cls, value: str) -> str:
        if not _SHA256_HEX.fullmatch(value):
            raise ValueError("descriptor_sha256 must be exactly 64 lowercase hex characters")
        return value


class SemanticProfileDescriptor(DungeonMindModel):
    """Data-only profile: admitted term namespaces for a pinned revision."""

    schema_version: Literal["dm_semantic_profile_v1"] = SEMANTIC_PROFILE_DESCRIPTOR_SCHEMA
    profile_id: str = Field(min_length=1)
    profile_revision: str = Field(min_length=1)
    term_namespaces: list[str] = Field(min_length=1)

    @field_validator("profile_id")
    @classmethod
    def _validate_profile_id(cls, value: str) -> str:
        _reject_locator_like(value, field_name="profile_id")
        if not _PROFILE_ID.fullmatch(value):
            raise ValueError(
                "profile_id must be lowercase dotted "
                "(letters, digits, '.', '_', '-' only)"
            )
        return value

    @field_validator("profile_revision")
    @classmethod
    def _validate_profile_revision(cls, value: str) -> str:
        _reject_locator_like(value, field_name="profile_revision")
        if not _PROFILE_REVISION.fullmatch(value):
            raise ValueError(
                "profile_revision must be a non-empty immutable token "
                "(lowercase letters, digits, '.', '_', '-' only)"
            )
        return value

    @field_validator("term_namespaces")
    @classmethod
    def _validate_term_namespaces(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("term_namespaces must be non-empty")
        seen: set[str] = set()
        for namespace in value:
            if not isinstance(namespace, str) or not namespace:
                raise ValueError("term_namespaces entries must be non-empty strings")
            if ":" in namespace:
                raise ValueError("term_namespaces must not contain ':'")
            if not _NAMESPACE.fullmatch(namespace):
                raise ValueError(
                    "term_namespaces must be lowercase "
                    "(letters, digits, '.', '_', '-' only)"
                )
            if namespace in seen:
                raise ValueError(f"duplicate term namespace {namespace!r}")
            seen.add(namespace)
        return value


class SemanticProfileRegistryEntry(DungeonMindModel):
    """Filesystem locator entry — config-only; never part of graph identity."""

    profile_id: str = Field(min_length=1)
    profile_revision: str = Field(min_length=1)
    descriptor_path: str = Field(min_length=1)

    @field_validator("profile_id")
    @classmethod
    def _validate_profile_id(cls, value: str) -> str:
        _reject_locator_like(value, field_name="profile_id")
        if not _PROFILE_ID.fullmatch(value):
            raise ValueError(
                "profile_id must be lowercase dotted "
                "(letters, digits, '.', '_', '-' only)"
            )
        return value

    @field_validator("profile_revision")
    @classmethod
    def _validate_profile_revision(cls, value: str) -> str:
        _reject_locator_like(value, field_name="profile_revision")
        if not _PROFILE_REVISION.fullmatch(value):
            raise ValueError(
                "profile_revision must be a non-empty immutable token "
                "(lowercase letters, digits, '.', '_', '-' only)"
            )
        return value

    @field_validator("descriptor_path")
    @classmethod
    def _validate_descriptor_path(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("descriptor_path must be a non-empty relative path")
        if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
            raise ValueError("descriptor_path must be relative to the registry config")
        if "://" in value:
            raise ValueError("descriptor_path must not be a URI")
        return value


class SemanticProfileRegistryConfig(DungeonMindModel):
    """Operator config mapping profile identity → relative descriptor files."""

    schema_version: Literal["dm_semantic_profile_registry_config_v1"] = (
        SEMANTIC_PROFILE_REGISTRY_CONFIG_SCHEMA
    )
    profiles: list[SemanticProfileRegistryEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_identity_keys(self) -> Self:
        seen: set[tuple[str, str]] = set()
        for entry in self.profiles:
            key = (entry.profile_id, entry.profile_revision)
            if key in seen:
                raise ValueError(
                    "duplicate profile_id/profile_revision in registry config"
                )
            seen.add(key)
        return self
