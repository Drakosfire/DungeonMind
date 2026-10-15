"""Immutable world-property-v4 compatibility pin for world-object-v6."""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dungeonmind_dnd.application import world_property_vocabulary as property_vocab_module
from dungeonmind_dnd.application.world_object_vocabulary import (
    builtin_world_object_v6_vocabulary_ref,
    load_builtin_world_object_v3_vocabulary,
    load_builtin_world_object_v5_vocabulary,
    load_builtin_world_object_v6_vocabulary,
    vocabulary_sha256,
)
from dungeonmind_dnd.application.world_property_vocabulary import (
    builtin_world_property_v3_vocabulary_ref,
    builtin_world_property_v4_vocabulary_ref,
    load_builtin_world_property_v3_vocabulary,
    load_builtin_world_property_v4_vocabulary,
    validate_world_property_assignment_v4,
    world_property_vocabulary_sha256,
)
from dungeonmind_dnd.domain.errors import DndCandidateValidationError, DndVocabularyIntegrityError

REPO_ROOT = Path(__file__).resolve().parents[2]
V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-property-v3.json"
V4_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-property-v4.json"
WORLD_OBJECT_V5_DIGEST = "f9fd5420e0ab3849224e0d58cf83dd432ca2e5da22ce661b25654406ec9c60d8"
WORLD_OBJECT_V6_DIGEST = "2c6e2a8547515f968a960fa5647c5ba28ce0978b8e4adb60befe55ef45666845"
WORLD_PROPERTY_V3_DIGEST = "aa94df78c10a913e7ca6774198f080131f8f447c90cc917b9b840ed88bd856e4"
WORLD_PROPERTY_V4_DIGEST = "1b94913b9c0ecee5270d7b9f48b0a8b8824e768b2400ad69d0624241e2c58cb9"


def test_v4_pairs_exactly_with_v6_and_preserves_property_semantics() -> None:
    object_v3 = load_builtin_world_object_v3_vocabulary()
    object_v5 = load_builtin_world_object_v5_vocabulary()
    object_v6 = load_builtin_world_object_v6_vocabulary()
    prop_v3 = load_builtin_world_property_v3_vocabulary()
    prop_v4 = load_builtin_world_property_v4_vocabulary()

    assert vocabulary_sha256(object_v5) == WORLD_OBJECT_V5_DIGEST
    assert vocabulary_sha256(object_v6) == WORLD_OBJECT_V6_DIGEST
    assert world_property_vocabulary_sha256(prop_v3) == WORLD_PROPERTY_V3_DIGEST
    assert world_property_vocabulary_sha256(prop_v4) == WORLD_PROPERTY_V4_DIGEST
    assert V3_PATH.is_file() and V4_PATH.is_file()
    assert builtin_world_property_v3_vocabulary_ref().catalog_sha256 == WORLD_PROPERTY_V3_DIGEST
    assert prop_v4.world_object_vocabulary.model_dump(
        mode="json"
    ) == builtin_world_object_v6_vocabulary_ref().model_dump(mode="json")
    assert prop_v4.properties == prop_v3.properties
    assert [kind.model_dump(mode="json") for kind in object_v6.object_kinds] == [
        kind.model_dump(mode="json") for kind in object_v5.object_kinds
    ]
    assert len(object_v3.object_kinds) < len(object_v5.object_kinds)
    ref = builtin_world_property_v4_vocabulary_ref()
    assert ref.vocabulary_revision == "world-property-v4"
    assert ref.catalog_sha256 == WORLD_PROPERTY_V4_DIGEST


def test_v4_role_assignment_uses_v6_kinds_and_fails_closed() -> None:
    validate_world_property_assignment_v4(
        property_term="dnd5e:role", subject_kind="dnd5e:faction", value="governing council"
    )
    with pytest.raises(DndCandidateValidationError):
        validate_world_property_assignment_v4(
            property_term="dnd5e:role", subject_kind="dnd5e:unregistered", value="council"
        )
    with pytest.raises(DndCandidateValidationError):
        validate_world_property_assignment_v4(
            property_term="dnd5e:role", subject_kind="dnd5e:faction", value="  "
        )


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda data: data["world_object_vocabulary"].__setitem__(
                "vocabulary_revision", "world-object-v5"
            ),
            "world_object_dependency_mismatch",
        ),
        (
            lambda data: data["world_object_vocabulary"].__setitem__("catalog_sha256", "0" * 64),
            "world_object_dependency_mismatch",
        ),
        (
            lambda data: data["semantic_profile"].__setitem__("descriptor_sha256", "0" * 64),
            "profile_digest_mismatch",
        ),
        (lambda data: data["properties"][0].__setitem__("term", "dnd5e:governs"), "term_collision"),
        (
            lambda data: data["properties"][0].__setitem__("subject_kinds", ["dnd5e:unknown"]),
            "unknown_subject_kind",
        ),
        (
            lambda data: data["properties"][0].__setitem__("term", "unknown:role"),
            "namespace_not_admitted",
        ),
        (
            lambda data: data.__setitem__("vocabulary_revision", "world-property-v5"),
            "vocabulary_identity_mismatch",
        ),
    ],
    ids=(
        "dependency-revision",
        "dependency-digest",
        "profile-digest",
        "term-collision",
        "unknown-subject",
        "namespace",
        "revision",
    ),
)
def test_v4_loader_rejects_changed_contract(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any]], None],
    reason: str,
) -> None:
    original = property_vocab_module._load_json_resource

    def altered_resource(directory: str, name: str, *, description: str) -> Any:
        data = original(directory, name, description=description)
        if name == "world-property-v4.json":
            data = copy.deepcopy(data)
            mutate(data)
        return data

    monkeypatch.setattr(property_vocab_module, "_load_json_resource", altered_resource)
    with pytest.raises(DndVocabularyIntegrityError) as exc:
        load_builtin_world_property_v4_vocabulary()
    assert exc.value.details["reason"] == reason
