"""Filesystem and static semantic profile registry behavior."""

from __future__ import annotations

import json
import shutil
import traceback
from pathlib import Path

import pytest

from dungeonmind.application.semantic_profiles import (
    descriptor_sha256,
    resolve_and_verify_profile,
)
from dungeonmind.contracts.semantic_profile import (
    SemanticProfileDescriptor,
    SemanticProfileRef,
)
from dungeonmind.domain.errors import (
    SemanticProfileIntegrityError,
    SemanticProfileNotFoundError,
)
from dungeonmind.infrastructure.semantic_profiles import (
    FilesystemSemanticProfileRegistry,
    StaticSemanticProfileRegistry,
)

FIXTURE_DESCRIPTOR = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "semantic_profiles"
    / "test-narrative-v1.json"
)


def _write_registry(
    tmp_path: Path,
    *,
    descriptor_name: str = "test-narrative-v1.json",
    descriptor_src: Path | None = None,
    profile_id: str = "test.narrative",
    profile_revision: str = "narrative-profile-v1",
) -> Path:
    src = descriptor_src or FIXTURE_DESCRIPTOR
    dest = tmp_path / descriptor_name
    shutil.copy(src, dest)
    config = {
        "schema_version": "dm_semantic_profile_registry_config_v1",
        "profiles": [
            {
                "profile_id": profile_id,
                "profile_revision": profile_revision,
                "descriptor_path": descriptor_name,
            }
        ],
    }
    config_path = tmp_path / "registry.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def _full_traceback(exc: BaseException) -> str:
    """Complete chained traceback text, as a startup logger would emit it."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def _assert_traceback_has_no_paths(exc: BaseException, *needles: str) -> None:
    """The formatted chained traceback must not contain local paths/content."""
    blob = _full_traceback(exc)
    for needle in needles:
        assert needle not in blob
    # ``from None``: no explicit cause, and implicit __context__ suppressed.
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True


def test_filesystem_registry_loads_and_returns_deep_copy(tmp_path: Path) -> None:
    config_path = _write_registry(tmp_path)
    registry = FilesystemSemanticProfileRegistry.from_config_path(config_path)
    first = registry.get("test.narrative", "narrative-profile-v1")
    assert first is not None
    first.term_namespaces.append("mutated")
    second = registry.get("test.narrative", "narrative-profile-v1")
    assert second is not None
    assert second.term_namespaces == ["narrative"]


def test_filesystem_registry_missing_config_fails_without_path_leak(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "registry.json"
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        FilesystemSemanticProfileRegistry.from_config_path(config_path)
    assert str(tmp_path) not in str(exc_info.value)
    assert str(tmp_path) not in json.dumps(exc_info.value.details)
    _assert_traceback_has_no_paths(exc_info.value, str(tmp_path), "registry.json")


def test_filesystem_registry_malformed_config_json_suppresses_traceback(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "registry.json"
    # Embed a local path in the malformed payload; it must not surface.
    config_path.write_text(f"{{ not json: {tmp_path}", encoding="utf-8")
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        FilesystemSemanticProfileRegistry.from_config_path(config_path)
    assert "not valid JSON" in str(exc_info.value)
    _assert_traceback_has_no_paths(exc_info.value, str(tmp_path), "registry.json")


def test_filesystem_registry_invalid_config_suppresses_traceback(
    tmp_path: Path,
) -> None:
    # Absolute descriptor_path is rejected by the config contract; the
    # pydantic input dump would otherwise echo the local absolute path.
    config = {
        "schema_version": "dm_semantic_profile_registry_config_v1",
        "profiles": [
            {
                "profile_id": "test.narrative",
                "profile_revision": "narrative-profile-v1",
                "descriptor_path": str(tmp_path / "absolute.json"),
            }
        ],
    }
    config_path = tmp_path / "registry.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        FilesystemSemanticProfileRegistry.from_config_path(config_path)
    assert "failed validation" in str(exc_info.value)
    _assert_traceback_has_no_paths(exc_info.value, str(tmp_path), "absolute.json")


def test_filesystem_registry_missing_descriptor_fails_without_path_leak(
    tmp_path: Path,
) -> None:
    config = {
        "schema_version": "dm_semantic_profile_registry_config_v1",
        "profiles": [
            {
                "profile_id": "test.narrative",
                "profile_revision": "narrative-profile-v1",
                "descriptor_path": "missing.json",
            }
        ],
    }
    config_path = tmp_path / "registry.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        FilesystemSemanticProfileRegistry.from_config_path(config_path)
    message = str(exc_info.value)
    details = json.dumps(exc_info.value.details)
    assert str(tmp_path) not in message
    assert str(tmp_path) not in details
    assert "missing.json" not in message
    assert "missing.json" not in details
    _assert_traceback_has_no_paths(exc_info.value, str(tmp_path), "missing.json")


def test_filesystem_registry_malformed_descriptor_json_suppresses_traceback(
    tmp_path: Path,
) -> None:
    desc_path = tmp_path / "broken.json"
    desc_path.write_text(f"{{ not json: {tmp_path}", encoding="utf-8")
    config = {
        "schema_version": "dm_semantic_profile_registry_config_v1",
        "profiles": [
            {
                "profile_id": "test.narrative",
                "profile_revision": "narrative-profile-v1",
                "descriptor_path": "broken.json",
            }
        ],
    }
    config_path = tmp_path / "registry.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        FilesystemSemanticProfileRegistry.from_config_path(config_path)
    assert "not valid JSON" in str(exc_info.value)
    _assert_traceback_has_no_paths(exc_info.value, str(tmp_path), "broken.json")


def test_filesystem_registry_invalid_descriptor_suppresses_traceback(
    tmp_path: Path,
) -> None:
    # profile_id containing path separators is rejected by the descriptor
    # contract; the pydantic input dump would otherwise echo the local path.
    desc_path = tmp_path / "invalid.json"
    desc_path.write_text(
        json.dumps(
            {
                "schema_version": "dm_semantic_profile_v1",
                "profile_id": f"bad{tmp_path}",
                "profile_revision": "narrative-profile-v1",
                "term_namespaces": ["narrative"],
            }
        ),
        encoding="utf-8",
    )
    config = {
        "schema_version": "dm_semantic_profile_registry_config_v1",
        "profiles": [
            {
                "profile_id": "test.narrative",
                "profile_revision": "narrative-profile-v1",
                "descriptor_path": "invalid.json",
            }
        ],
    }
    config_path = tmp_path / "registry.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        FilesystemSemanticProfileRegistry.from_config_path(config_path)
    assert "failed validation" in str(exc_info.value)
    _assert_traceback_has_no_paths(exc_info.value, str(tmp_path), "invalid.json")


def test_filesystem_registry_rejects_duplicate_identity(tmp_path: Path) -> None:
    shutil.copy(FIXTURE_DESCRIPTOR, tmp_path / "a.json")
    shutil.copy(FIXTURE_DESCRIPTOR, tmp_path / "b.json")
    config = {
        "schema_version": "dm_semantic_profile_registry_config_v1",
        "profiles": [
            {
                "profile_id": "test.narrative",
                "profile_revision": "narrative-profile-v1",
                "descriptor_path": "a.json",
            },
            {
                "profile_id": "test.narrative",
                "profile_revision": "narrative-profile-v1",
                "descriptor_path": "b.json",
            },
        ],
    }
    config_path = tmp_path / "registry.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        FilesystemSemanticProfileRegistry.from_config_path(config_path)
    assert exc_info.value.code == "semantic_profile_integrity_error"
    assert "duplicate" in str(exc_info.value).casefold()


def test_filesystem_registry_rejects_identity_mismatch(tmp_path: Path) -> None:
    config_path = _write_registry(
        tmp_path,
        profile_id="other.profile",
        profile_revision="other-revision-v1",
    )
    with pytest.raises(SemanticProfileIntegrityError) as exc_info:
        FilesystemSemanticProfileRegistry.from_config_path(config_path)
    assert str(tmp_path) not in str(exc_info.value)
    assert str(tmp_path) not in json.dumps(exc_info.value.details)


def test_resolve_and_verify_detects_tamper(tmp_path: Path) -> None:
    config_path = _write_registry(tmp_path)
    registry = FilesystemSemanticProfileRegistry.from_config_path(config_path)
    descriptor = registry.get("test.narrative", "narrative-profile-v1")
    assert descriptor is not None
    good_digest = descriptor_sha256(descriptor)
    ref = SemanticProfileRef(
        profile_id="test.narrative",
        profile_revision="narrative-profile-v1",
        descriptor_sha256=good_digest,
    )
    assert resolve_and_verify_profile(ref, registry).profile_id == "test.narrative"

    bad_ref = SemanticProfileRef(
        profile_id="test.narrative",
        profile_revision="narrative-profile-v1",
        descriptor_sha256="0" * 64,
    )
    with pytest.raises(SemanticProfileIntegrityError):
        resolve_and_verify_profile(bad_ref, registry)


def test_relocation_preserves_identity(tmp_path: Path) -> None:
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    first_dir.mkdir()
    second_dir.mkdir()
    first_config = _write_registry(first_dir)
    second_config = _write_registry(second_dir, descriptor_name="relocated.json")
    first = FilesystemSemanticProfileRegistry.from_config_path(first_config)
    second = FilesystemSemanticProfileRegistry.from_config_path(second_config)
    d1 = first.get("test.narrative", "narrative-profile-v1")
    d2 = second.get("test.narrative", "narrative-profile-v1")
    assert d1 is not None and d2 is not None
    assert descriptor_sha256(d1) == descriptor_sha256(d2)


def test_static_registry_cache_and_not_found() -> None:
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(FIXTURE_DESCRIPTOR.read_text(encoding="utf-8"))
    )
    registry = StaticSemanticProfileRegistry([descriptor])
    found = registry.get("test.narrative", "narrative-profile-v1")
    assert found is not None
    found.term_namespaces.append("x")
    again = registry.get("test.narrative", "narrative-profile-v1")
    assert again is not None
    assert again.term_namespaces == ["narrative"]
    assert registry.get("missing", "rev") is None
    with pytest.raises(SemanticProfileNotFoundError):
        resolve_and_verify_profile(
            SemanticProfileRef(
                profile_id="missing.id",
                profile_revision="missing-rev-v1",
                descriptor_sha256="0" * 64,
            ),
            registry,
        )
