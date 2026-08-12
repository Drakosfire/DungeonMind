"""Immutable world-property-v3 compatibility pin proofs for world-object-v5."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind_dnd.application import world_property_vocabulary as world_property_vocab_module
from dungeonmind_dnd.application.world_object_vocabulary import (
    WORLD_OBJECT_V4_VOCABULARY_REVISION,
    WORLD_OBJECT_V5_VOCABULARY_REVISION,
    builtin_world_object_v4_vocabulary_ref,
    builtin_world_object_v5_vocabulary_ref,
    load_builtin_v3_descriptor,
    load_builtin_world_object_v2_vocabulary,
    load_builtin_world_object_v3_vocabulary,
    load_builtin_world_object_v4_vocabulary,
    load_builtin_world_object_v5_vocabulary,
    load_builtin_world_object_vocabulary,
    vocabulary_sha256,
)
from dungeonmind_dnd.application.world_property_vocabulary import (
    WORLD_PROPERTY_V2_VOCABULARY_REVISION,
    WORLD_PROPERTY_V3_VOCABULARY_REVISION,
    WORLD_PROPERTY_VOCABULARY_ID,
    WORLD_PROPERTY_VOCABULARY_REVISION,
    builtin_world_property_v2_vocabulary_ref,
    builtin_world_property_v3_vocabulary_ref,
    builtin_world_property_vocabulary_ref,
    load_builtin_world_property_v2_vocabulary,
    load_builtin_world_property_v3_vocabulary,
    load_builtin_world_property_vocabulary,
    validate_world_property_assignment_v2,
    validate_world_property_assignment_v3,
    world_property_vocabulary_sha256,
)
from dungeonmind_dnd.contracts.vocabulary import PROPERTY_VOCABULARY_SCHEMA
from dungeonmind_dnd.domain.errors import DndCandidateValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
PROPERTY_V1_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-property-v1.json"
PROPERTY_V2_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-property-v2.json"
PROPERTY_V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-property-v3.json"
PROFILE_V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/profiles/dnd5e-v3.json"

V3_DIGEST = "2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496"
WORLD_OBJECT_V1_DIGEST = (
    "7cc3b285611ed13eb01e0cdc8a963cfa0bea3130abe0ce816204ab67186cb880"
)
WORLD_OBJECT_V2_DIGEST = (
    "a53e2d0ec45878288800ff3d30006d54803db70a17e6680b359a0fa88f2a9922"
)
WORLD_OBJECT_V3_DIGEST = (
    "d2f08de9ec3def308c8bc6d9d81132e5bbff9bd10b4bd706fc1cb39667b71a19"
)
WORLD_OBJECT_V4_DIGEST = (
    "552c59a3fa9a20e437294d1a77974c05e37b69ec95e5ea03337a7d010e4d287b"
)
WORLD_OBJECT_V5_DIGEST = (
    "f9fd5420e0ab3849224e0d58cf83dd432ca2e5da22ce661b25654406ec9c60d8"
)
WORLD_PROPERTY_V1_DIGEST = (
    "b466e3f16ae1aba5814f3386dff86b7017399c6099158d99ef95e9979d7cea7f"
)
WORLD_PROPERTY_V2_DIGEST = (
    "8ad4c223e83ce48cf5cd33a33e10f5be5d48a80ad742784d7c561470b450ab73"
)
WORLD_PROPERTY_V3_DIGEST = (
    "aa94df78c10a913e7ca6774198f080131f8f447c90cc917b9b840ed88bd856e4"
)

TWELVE_KINDS = frozenset(
    {
        "dnd5e:creature",
        "dnd5e:threat",
        "dnd5e:npc",
        "dnd5e:player_character",
        "dnd5e:location",
        "dnd5e:faction",
        "dnd5e:encounter",
        "dnd5e:item",
        "dnd5e:mystery",
        "dnd5e:group",
        "dnd5e:party",
        "dnd5e:event",
    }
)
THIRTEEN_KINDS = TWELVE_KINDS | {"dnd5e:thread"}


def test_historical_property_digests_unchanged() -> None:
    descriptor = load_builtin_v3_descriptor()
    assert descriptor.profile_revision == "dnd5e-profile-v3"
    assert descriptor_sha256(descriptor) == V3_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_vocabulary()) == WORLD_OBJECT_V1_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v2_vocabulary()) == WORLD_OBJECT_V2_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v3_vocabulary()) == WORLD_OBJECT_V3_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v4_vocabulary()) == WORLD_OBJECT_V4_DIGEST
    assert (
        world_property_vocabulary_sha256(load_builtin_world_property_vocabulary())
        == WORLD_PROPERTY_V1_DIGEST
    )
    assert (
        world_property_vocabulary_sha256(load_builtin_world_property_v2_vocabulary())
        == WORLD_PROPERTY_V2_DIGEST
    )
    assert PROPERTY_V1_PATH.is_file()
    assert PROPERTY_V2_PATH.is_file()


def test_world_property_v3_identity_and_world_object_v5_pin() -> None:
    catalog = load_builtin_world_property_v3_vocabulary()
    assert catalog.schema_version == PROPERTY_VOCABULARY_SCHEMA
    assert catalog.vocabulary_id == WORLD_PROPERTY_VOCABULARY_ID
    assert catalog.vocabulary_revision == WORLD_PROPERTY_V3_VOCABULARY_REVISION
    assert catalog.semantic_profile.profile_revision == "dnd5e-profile-v3"
    assert catalog.semantic_profile.descriptor_sha256 == V3_DIGEST
    expected_ref = builtin_world_object_v5_vocabulary_ref()
    assert catalog.world_object_vocabulary.model_dump() == expected_ref.model_dump()
    assert expected_ref.vocabulary_revision == WORLD_OBJECT_V5_VOCABULARY_REVISION
    assert expected_ref.catalog_sha256 == WORLD_OBJECT_V5_DIGEST
    digest = world_property_vocabulary_sha256(catalog)
    assert digest == WORLD_PROPERTY_V3_DIGEST
    ref = builtin_world_property_v3_vocabulary_ref()
    assert ref.vocabulary_revision == "world-property-v3"
    assert ref.catalog_sha256 == WORLD_PROPERTY_V3_DIGEST
    on_disk = json.loads(PROPERTY_V3_PATH.read_text(encoding="utf-8"))
    assert on_disk["vocabulary_revision"] == "world-property-v3"
    assert on_disk["world_object_vocabulary"]["vocabulary_revision"] == "world-object-v5"
    assert on_disk["world_object_vocabulary"]["catalog_sha256"] == WORLD_OBJECT_V5_DIGEST


def test_role_semantics_unchanged_except_thread_subject() -> None:
    v2 = load_builtin_world_property_v2_vocabulary()
    v3 = load_builtin_world_property_v3_vocabulary()
    assert len(v2.properties) == 1
    assert len(v3.properties) == 1
    role_v2 = v2.properties[0]
    role_v3 = v3.properties[0]
    assert role_v2.term == role_v3.term == "dnd5e:role"
    assert role_v2.label == role_v3.label
    assert role_v2.description == role_v3.description
    assert role_v2.value_contract == role_v3.value_contract == "non_empty_string"
    assert set(role_v2.subject_kinds) == TWELVE_KINDS
    assert set(role_v3.subject_kinds) == THIRTEEN_KINDS
    assert set(role_v3.subject_kinds) - set(role_v2.subject_kinds) == {"dnd5e:thread"}
    v5_kinds = {kind.term for kind in load_builtin_world_object_v5_vocabulary().object_kinds}
    assert set(role_v3.subject_kinds) == v5_kinds


def test_v3_accepts_thread_role_and_v2_rejects() -> None:
    validate_world_property_assignment_v3(
        property_term="dnd5e:role",
        subject_kind="dnd5e:thread",
        value="pursuit",
    )
    with pytest.raises(DndCandidateValidationError):
        validate_world_property_assignment_v2(
            property_term="dnd5e:role",
            subject_kind="dnd5e:thread",
            value="pursuit",
        )
    assert builtin_world_property_v2_vocabulary_ref().vocabulary_revision == (
        WORLD_PROPERTY_V2_VOCABULARY_REVISION
    )
    assert builtin_world_object_v4_vocabulary_ref().vocabulary_revision == (
        WORLD_OBJECT_V4_VOCABULARY_REVISION
    )
    assert builtin_world_property_vocabulary_ref().vocabulary_revision == (
        WORLD_PROPERTY_VOCABULARY_REVISION
    )


@pytest.mark.parametrize("subject_kind", sorted(THIRTEEN_KINDS))
def test_validate_world_property_assignment_v3_accepts_all_kinds(subject_kind: str) -> None:
    validate_world_property_assignment_v3(
        property_term="dnd5e:role",
        subject_kind=subject_kind,
        value="probe",
    )


def test_no_latest_or_current_property_loader() -> None:
    names = dir(world_property_vocab_module)
    assert "load_latest_world_property_vocabulary" not in names
    assert "load_current_world_property_vocabulary" not in names
    module_text = (
        REPO_ROOT / "src/dungeonmind_dnd/application/world_property_vocabulary.py"
    ).read_text(encoding="utf-8")
    assert "def load_latest" not in module_text
    assert "def load_current" not in module_text
    assert "DungeonMindBuddy" not in module_text
