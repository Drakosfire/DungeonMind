"""Filesystem and static adapters for :class:`SemanticProfileRegistry`.

Neither adapter imports ``dungeonmind_dnd``. Error messages and details never
include local filesystem paths.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..application.semantic_profiles import descriptor_sha256
from ..contracts.semantic_profile import (
    SemanticProfileDescriptor,
    SemanticProfileRegistryConfig,
)
from ..domain.errors import SemanticProfileIntegrityError

ENV_SEMANTIC_PROFILE_REGISTRY_PATH = "DUNGEONMIND_SEMANTIC_PROFILE_REGISTRY_PATH"


def _integrity(message: str, *, details: dict[str, Any] | None = None) -> None:
    raise SemanticProfileIntegrityError(message, details=details)


class StaticSemanticProfileRegistry:
    """In-memory registry keyed by ``(profile_id, profile_revision)``."""

    def __init__(
        self,
        descriptors: Iterable[SemanticProfileDescriptor] | None = None,
    ) -> None:
        self._by_key: dict[tuple[str, str], SemanticProfileDescriptor] = {}
        for descriptor in descriptors or ():
            key = (descriptor.profile_id, descriptor.profile_revision)
            if key in self._by_key:
                _integrity(
                    "duplicate semantic profile identity in static registry",
                    details={
                        "profile_id": descriptor.profile_id,
                        "profile_revision": descriptor.profile_revision,
                    },
                )
            self._by_key[key] = descriptor.model_copy(deep=True)

    def get(
        self, profile_id: str, profile_revision: str
    ) -> SemanticProfileDescriptor | None:
        found = self._by_key.get((profile_id, profile_revision))
        if found is None:
            return None
        return found.model_copy(deep=True)


class FilesystemSemanticProfileRegistry:
    """Load descriptors from a registry config file (relative paths only)."""

    def __init__(self, config_path: Path | str) -> None:
        path = Path(config_path)
        self._by_key: dict[tuple[str, str], SemanticProfileDescriptor] = {}
        self._load(path)

    @classmethod
    def from_config_path(cls, config_path: Path | str) -> FilesystemSemanticProfileRegistry:
        return cls(config_path)

    def get(
        self, profile_id: str, profile_revision: str
    ) -> SemanticProfileDescriptor | None:
        found = self._by_key.get((profile_id, profile_revision))
        if found is None:
            return None
        return found.model_copy(deep=True)

    def _load(self, config_path: Path) -> None:
        try:
            raw_text = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            _integrity(
                "semantic profile registry config could not be read",
                details={"reason": type(exc).__name__},
            )
            return  # pragma: no cover — _integrity always raises

        try:
            raw: Any = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise SemanticProfileIntegrityError(
                "semantic profile registry config is not valid JSON",
                details={"reason": type(exc).__name__},
            ) from exc

        try:
            config = SemanticProfileRegistryConfig.model_validate(raw)
        except ValidationError as exc:
            raise SemanticProfileIntegrityError(
                "semantic profile registry config failed validation",
                details={"reason": "ValidationError"},
            ) from exc

        base_dir = config_path.parent
        for entry in config.profiles:
            descriptor = self._load_descriptor(
                base_dir=base_dir,
                relative_path=entry.descriptor_path,
                expected_profile_id=entry.profile_id,
                expected_profile_revision=entry.profile_revision,
            )
            key = (descriptor.profile_id, descriptor.profile_revision)
            if key in self._by_key:
                _integrity(
                    "duplicate semantic profile identity in registry",
                    details={
                        "profile_id": descriptor.profile_id,
                        "profile_revision": descriptor.profile_revision,
                    },
                )
            # Touch digest so malformed descriptors fail closed at load time.
            _ = descriptor_sha256(descriptor)
            self._by_key[key] = descriptor

    def _load_descriptor(
        self,
        *,
        base_dir: Path,
        relative_path: str,
        expected_profile_id: str,
        expected_profile_revision: str,
    ) -> SemanticProfileDescriptor:
        # Resolve relative to the config file. Parent segments (``..``) are
        # allowed so deployment layout can locate package-owned descriptors.
        # Absolute paths and URIs are rejected by the config contract. Never
        # put resolved filesystem paths into error payloads.
        candidate = (base_dir / relative_path).resolve()

        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError as exc:
            raise SemanticProfileIntegrityError(
                "semantic profile descriptor could not be read",
                details={
                    "profile_id": expected_profile_id,
                    "profile_revision": expected_profile_revision,
                    "reason": type(exc).__name__,
                },
            ) from exc

        try:
            payload: Mapping[str, Any] = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SemanticProfileIntegrityError(
                "semantic profile descriptor is not valid JSON",
                details={
                    "profile_id": expected_profile_id,
                    "profile_revision": expected_profile_revision,
                    "reason": type(exc).__name__,
                },
            ) from exc

        try:
            descriptor = SemanticProfileDescriptor.model_validate(payload)
        except ValidationError as exc:
            raise SemanticProfileIntegrityError(
                "semantic profile descriptor failed validation",
                details={
                    "profile_id": expected_profile_id,
                    "profile_revision": expected_profile_revision,
                    "reason": "ValidationError",
                },
            ) from exc

        if (
            descriptor.profile_id != expected_profile_id
            or descriptor.profile_revision != expected_profile_revision
        ):
            raise SemanticProfileIntegrityError(
                "semantic profile descriptor identity does not match registry entry",
                details={
                    "profile_id": expected_profile_id,
                    "profile_revision": expected_profile_revision,
                    "descriptor_profile_id": descriptor.profile_id,
                    "descriptor_profile_revision": descriptor.profile_revision,
                },
            )
        return descriptor.model_copy(deep=True)
