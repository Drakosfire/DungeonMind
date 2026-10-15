"""Immutable world-object-v6 governance vocabulary proofs."""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dungeonmind_dnd.application import world_object_vocabulary as world_object_vocab_module
from dungeonmind_dnd.application.world_object_vocabulary import (
    WORLD_OBJECT_V5_VOCABULARY_REVISION,
    WORLD_OBJECT_V6_VOCABULARY_REVISION,
    builtin_world_object_v5_vocabulary_ref,
    builtin_world_object_v6_vocabulary_ref,
    load_builtin_world_object_v5_vocabulary,
    load_builtin_world_object_v6_vocabulary,
    vocabulary_sha256,
)
from dungeonmind_dnd.domain.errors import DndVocabularyIntegrityError

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v5.json"
V6_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v6.json"
V5_DIGEST = "f9fd5420e0ab3849224e0d58cf83dd432ca2e5da22ce661b25654406ec9c60d8"
V6_DIGEST = "2c6e2a8547515f968a960fa5647c5ba28ce0978b8e4adb60befe55ef45666845"


def test_v6_adds_only_directed_faction_governance_and_preserves_v5() -> None:
    v5 = load_builtin_world_object_v5_vocabulary()
    v6 = load_builtin_world_object_v6_vocabulary()

    assert WORLD_OBJECT_V5_VOCABULARY_REVISION == "world-object-v5"
    assert WORLD_OBJECT_V6_VOCABULARY_REVISION == "world-object-v6"
    assert vocabulary_sha256(v5) == V5_DIGEST
    assert vocabulary_sha256(v6) == V6_DIGEST
    assert V5_PATH.is_file() and V6_PATH.is_file()
    assert builtin_world_object_v5_vocabulary_ref().catalog_sha256 == V5_DIGEST
    assert builtin_world_object_v6_vocabulary_ref().catalog_sha256 == V6_DIGEST
    assert [kind.model_dump(mode="json") for kind in v6.object_kinds] == [
        kind.model_dump(mode="json") for kind in v5.object_kinds
    ]
    assert [predicate.model_dump(mode="json") for predicate in v6.predicates[:-1]] == [
        predicate.model_dump(mode="json") for predicate in v5.predicates
    ]

    governs = v6.predicates[-1]
    assert governs.term == "dnd5e:governs"
    assert governs.label == "Governs"
    assert governs.subject_kinds == ["dnd5e:faction"]
    assert governs.object_kinds == ["dnd5e:location"]
    definition = governs.description.lower()
    for boundary in (
        "governing authority",
        "territory",
        "not a location relation",
        "ownership",
        "membership",
        "election",
        "individual leader",
        "exclusivity",
        "reciprocal authority",
    ):
        assert boundary in definition
    assert all(predicate.term != "dnd5e:governs" for predicate in v5.predicates)
    assert (
        builtin_world_object_v6_vocabulary_ref().vocabulary_id
        == builtin_world_object_v5_vocabulary_ref().vocabulary_id
    )


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda data: data.__setitem__("vocabulary_id", "dungeonmind.dnd5e.altered"),
            "vocabulary_identity_mismatch",
        ),
        (
            lambda data: data.__setitem__("vocabulary_revision", "world-object-v7"),
            "vocabulary_identity_mismatch",
        ),
        (
            lambda data: data["semantic_profile"].__setitem__("descriptor_sha256", "0" * 64),
            "profile_digest_mismatch",
        ),
        (
            lambda data: data["predicates"][-1].__setitem__("term", "unknown:governs"),
            "namespace_not_admitted",
        ),
        (
            lambda data: data["predicates"][-1].__setitem__(
                "object_kinds", ["dnd5e:unsupported_kind"]
            ),
            "ValidationError",
        ),
    ],
    ids=("catalog-id", "revision", "profile-digest", "namespace", "unknown-endpoint"),
)
def test_v6_loader_rejects_changed_contract(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any]], None],
    reason: str,
) -> None:
    original = world_object_vocab_module._load_json_resource

    def altered_resource(directory: str, name: str, *, description: str) -> Any:
        data = original(directory, name, description=description)
        if name == "world-object-v6.json":
            data = copy.deepcopy(data)
            mutate(data)
        return data

    monkeypatch.setattr(world_object_vocab_module, "_load_json_resource", altered_resource)
    with pytest.raises(DndVocabularyIntegrityError) as exc:
        load_builtin_world_object_v6_vocabulary()
    assert exc.value.details["reason"] == reason
