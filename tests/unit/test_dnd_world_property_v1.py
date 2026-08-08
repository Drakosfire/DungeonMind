"""Immutable world-property-v1 catalog publication and assignment proofs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V5,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import (
    WORLD_OBJECT_V2_VOCABULARY_REVISION,
    WORLD_OBJECT_V3_VOCABULARY_REVISION,
    WORLD_OBJECT_VOCABULARY_REVISION,
    builtin_world_object_v3_vocabulary_ref,
    load_builtin_v3_descriptor,
    load_builtin_world_object_v2_vocabulary,
    load_builtin_world_object_v3_vocabulary,
    load_builtin_world_object_vocabulary,
    vocabulary_sha256,
)
from dungeonmind_dnd.application.world_property_vocabulary import (
    WORLD_PROPERTY_VOCABULARY_ID,
    WORLD_PROPERTY_VOCABULARY_REVISION,
    builtin_world_property_vocabulary_ref,
    load_builtin_world_property_vocabulary,
    validate_world_property_assignment,
    world_property_vocabulary_sha256,
)
from dungeonmind_dnd.contracts.vocabulary import (
    PROPERTY_VOCABULARY_SCHEMA,
    DndPropertyVocabulary,
    DndVocabularyProperty,
)
from dungeonmind_dnd.domain.errors import DndCandidateValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
V1_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v1.json"
V2_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v2.json"
V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v3.json"
PROPERTY_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-property-v1.json"
PROFILE_V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/profiles/dnd5e-v3.json"
INVENTORY_PATH = (
    REPO_ROOT / "tests/fixtures/dungeonmind_dnd/eldyrwild_role_inventory_v1.json"
)

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
WORLD_PROPERTY_V1_DIGEST = (
    "b466e3f16ae1aba5814f3386dff86b7017399c6099158d99ef95e9979d7cea7f"
)

BUDDY_KIND_TO_DM = {
    "creature": "dnd5e:creature",
    "threat": "dnd5e:threat",
    "npc": "dnd5e:npc",
    "pc": "dnd5e:player_character",
    "location": "dnd5e:location",
    "faction": "dnd5e:faction",
    "encounter": "dnd5e:encounter",
    "item": "dnd5e:item",
    "mystery": "dnd5e:mystery",
    "group": "dnd5e:group",
    "party": "dnd5e:party",
    "event": "dnd5e:event",
}

EXPECTED_KIND_COUNTS = {
    "creature": 4,
    "encounter": 2,
    "event": 2,
    "external_resource": 2,
    "faction": 13,
    "group": 29,
    "item": 125,
    "location": 103,
    "mystery": 93,
    "npc": 45,
    "party": 11,
    "pc": 6,
    "threat": 3,
}

EXPECTED_ROLE_VALUE_COUNTS = {
    "item": 125,
    "location": 101,
    "mystery": 93,
    "npc": 45,
    "group": 29,
    "faction": 13,
    "party": 10,
    "creature": 6,
    "player-character": 6,
    "encounter": 3,
    "statblock": 2,
    "travel": 1,
    "city": 1,
    "town": 1,
    "adventuring-party": 1,
    "encounter-threat": 1,
}

TWELVE_KINDS = frozenset(BUDDY_KIND_TO_DM.values())


def test_historical_profile_and_world_object_digests_unchanged() -> None:
    descriptor = load_builtin_v3_descriptor()
    assert descriptor.profile_revision == "dnd5e-profile-v3"
    assert descriptor_sha256(descriptor) == V3_DIGEST
    assert json.loads(PROFILE_V3_PATH.read_text(encoding="utf-8"))[
        "profile_revision"
    ] == "dnd5e-profile-v3"

    assert vocabulary_sha256(load_builtin_world_object_vocabulary()) == WORLD_OBJECT_V1_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v2_vocabulary()) == WORLD_OBJECT_V2_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v3_vocabulary()) == WORLD_OBJECT_V3_DIGEST
    assert json.loads(V1_PATH.read_text(encoding="utf-8"))["vocabulary_revision"] == (
        WORLD_OBJECT_VOCABULARY_REVISION
    )
    assert json.loads(V2_PATH.read_text(encoding="utf-8"))["vocabulary_revision"] == (
        WORLD_OBJECT_V2_VOCABULARY_REVISION
    )
    assert json.loads(V3_PATH.read_text(encoding="utf-8"))["vocabulary_revision"] == (
        WORLD_OBJECT_V3_VOCABULARY_REVISION
    )


def test_property_vocabulary_contract_rejects_latest_and_requires_terms() -> None:
    with pytest.raises(ValueError, match="latest"):
        DndPropertyVocabulary.model_validate(
            {
                "vocabulary_id": "dungeonmind.dnd5e.world_property",
                "vocabulary_revision": "latest",
                "semantic_profile": {
                    "schema_version": "dm_semantic_profile_ref_v1",
                    "profile_id": "dungeonmind.dnd5e",
                    "profile_revision": "dnd5e-profile-v3",
                    "descriptor_sha256": V3_DIGEST,
                },
                "world_object_vocabulary": builtin_world_object_v3_vocabulary_ref().model_dump(
                    mode="json"
                ),
                "properties": [
                    {
                        "term": "dnd5e:role",
                        "label": "Role",
                        "description": "x",
                        "subject_kinds": ["dnd5e:location"],
                        "value_contract": "non_empty_string",
                    }
                ],
            }
        )
    with pytest.raises(ValueError, match="qualified"):
        DndVocabularyProperty.model_validate(
            {
                "term": "role",
                "label": "Role",
                "description": "x",
                "subject_kinds": ["dnd5e:location"],
                "value_contract": "non_empty_string",
            }
        )


def test_world_property_v1_identity_and_digest() -> None:
    catalog = load_builtin_world_property_vocabulary()
    assert catalog.schema_version == PROPERTY_VOCABULARY_SCHEMA
    assert catalog.vocabulary_id == WORLD_PROPERTY_VOCABULARY_ID
    assert catalog.vocabulary_revision == WORLD_PROPERTY_VOCABULARY_REVISION
    assert catalog.semantic_profile.profile_revision == "dnd5e-profile-v3"
    assert catalog.semantic_profile.descriptor_sha256 == V3_DIGEST
    expected_ref = builtin_world_object_v3_vocabulary_ref()
    assert catalog.world_object_vocabulary.model_dump() == expected_ref.model_dump()
    digest = world_property_vocabulary_sha256(catalog)
    assert digest == WORLD_PROPERTY_V1_DIGEST
    ref = builtin_world_property_vocabulary_ref()
    assert ref.vocabulary_revision == "world-property-v1"
    assert ref.catalog_sha256 == WORLD_PROPERTY_V1_DIGEST
    on_disk = json.loads(PROPERTY_PATH.read_text(encoding="utf-8"))
    assert on_disk["vocabulary_revision"] == "world-property-v1"


def test_world_property_v1_exact_role_definition() -> None:
    catalog = load_builtin_world_property_vocabulary()
    assert len(catalog.properties) == 1
    role = catalog.properties[0]
    assert role.term == "dnd5e:role"
    assert role.value_contract == "non_empty_string"
    assert set(role.subject_kinds) == TWELVE_KINDS
    assert len(role.subject_kinds) == 12
    v3_kinds = {k.term for k in load_builtin_world_object_v3_vocabulary().object_kinds}
    assert set(role.subject_kinds) == v3_kinds


def test_negative_property_semantics() -> None:
    dump = json.dumps(load_builtin_world_property_vocabulary().model_dump(mode="json"))
    for forbidden in (
        "dnd5e:kind",
        "dnd5e:type",
        "dnd5e:statblock",
        "dnd5e:mechanics",
        "dnd5e:canon_state",
        "dnd5e:epistemic_kind",
        "dnd5e:visibility",
        "dnd5e:campaign_scope",
        "latest",
    ):
        assert forbidden not in dump
    module = (
        REPO_ROOT / "src/dungeonmind_dnd/application/world_property_vocabulary.py"
    ).read_text(encoding="utf-8")
    assert "def load_latest" not in module
    assert "def load_current" not in module


@pytest.mark.parametrize(
    ("subject_kind", "value"),
    [
        ("dnd5e:location", "city"),
        ("dnd5e:location", "town"),
        ("dnd5e:event", "travel"),
        ("dnd5e:party", "adventuring-party"),
        ("dnd5e:threat", "encounter-threat"),
        ("dnd5e:player_character", "player-character"),
        ("dnd5e:item", "item"),
    ],
)
def test_validate_world_property_assignment_accepts_role_examples(
    subject_kind: str,
    value: str,
) -> None:
    validate_world_property_assignment(
        property_term="dnd5e:role",
        subject_kind=subject_kind,
        value=value,
    )


@pytest.mark.parametrize(
    ("property_term", "subject_kind", "value"),
    [
        ("dnd5e:unknown", "dnd5e:location", "city"),
        ("dnd5e:role", "dnd5e:unknown", "city"),
        ("dnd5e:role", "external_resource", "statblock"),
        ("dnd5e:role", "dnd5e:location", ""),
        ("dnd5e:role", "dnd5e:location", "   "),
        ("dnd5e:role", "dnd5e:location", None),
        ("dnd5e:role", "dnd5e:location", 1),
        ("dnd5e:role", "dnd5e:location", True),
        ("dnd5e:role", "dnd5e:location", []),
        ("dnd5e:role", "dnd5e:location", {}),
    ],
)
def test_validate_world_property_assignment_rejects_invalid(
    property_term: str,
    subject_kind: str,
    value: object,
) -> None:
    with pytest.raises(DndCandidateValidationError):
        validate_world_property_assignment(
            property_term=property_term,
            subject_kind=subject_kind,
            value=value,
        )


def test_eldyrwild_role_inventory_coverage() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert inventory["schema"] == "dmdnd_eldyrwild_role_inventory_fixture_v1"
    assert inventory["source"]["world_id"] == "eldyrwild"
    assert inventory["source"]["revision_id"] == (
        "rev:3413bf6f5044cf2680233f5e37c90dcf"
    )
    assert inventory["source"]["graph_payload_sha256"] == (
        "346c1fbfb3cbbf6d0e5ded1453fdd7760264a5106022e398d6074679799ab0fa"
    )
    assert inventory["source"]["buddy_pr"] == 523
    assert inventory["source"]["buddy_head"] == (
        "0894a08e0dffd45afa36aac17c936fc05edabc7f"
    )
    assert inventory["node_role_count"] == 438
    assert inventory["world_object_role_count"] == 436
    assert inventory["external_resource_role_count"] == 2

    kind_counts = {
        row["object_kind"]: row["count"] for row in inventory["object_kind_counts"]
    }
    value_counts = {row["value"]: row["count"] for row in inventory["role_value_counts"]}
    assert kind_counts == EXPECTED_KIND_COUNTS
    assert value_counts == EXPECTED_ROLE_VALUE_COUNTS
    assert sum(kind_counts.values()) == 438
    assert sum(value_counts.values()) == 438
    assert kind_counts["external_resource"] == 2
    assert value_counts["statblock"] == 2

    world_object_instances = 0
    for buddy_kind, count in kind_counts.items():
        if buddy_kind == "external_resource":
            continue
        target = BUDDY_KIND_TO_DM[buddy_kind]
        validate_world_property_assignment(
            property_term="dnd5e:role",
            subject_kind=target,
            value="probe",
        )
        world_object_instances += count
    assert world_object_instances == 436
    assert world_object_instances + kind_counts["external_resource"] == 438

    # Every observed non-statblock role string is admissible on some world-object kind.
    for role_value, count in value_counts.items():
        if role_value == "statblock":
            continue
        validate_world_property_assignment(
            property_term="dnd5e:role",
            subject_kind="dnd5e:location",
            value=role_value,
        )
        assert count >= 1
    assert sum(c for v, c in value_counts.items() if v != "statblock") == 436


def test_v5_graph_transport_preserves_dnd5e_role_property() -> None:
    """Property transport already exists; this proves semantics were the gap."""
    descriptor = load_builtin_v3_descriptor()
    profile_ref = {
        "schema_version": "dm_semantic_profile_ref_v1",
        "profile_id": descriptor.profile_id,
        "profile_revision": descriptor.profile_revision,
        "descriptor_sha256": descriptor_sha256(descriptor),
    }
    meta = {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": "asrt:city-exists",
        "campaign_scope": None,
        "visibility": "player",
        "epistemic_kind": "asserted",
        "canon_state": "canonical",
        "evidence_ref_ids": ["ev:role"],
        "session_refs": [],
        "temporal_scope": {
            "schema_version": "dm_temporal_scope_ref_v1",
            "kind": "unknown",
        },
    }
    payload: dict[str, Any] = {
        "world_id": "world:property-v1-transport",
        "semantic_profile": profile_ref,
        "objects": [
            {
                "object_id": "obj:mireward",
                "kind": "dnd5e:location",
                "label": "Mireward",
                "assertion_metadata": meta,
                "aliases": [],
                "summary": None,
                "properties": [
                    {
                        "property_term": "dnd5e:role",
                        "value": "city",
                        "assertion_metadata": {
                            **meta,
                            "assertion_id": "asrt:mireward-role",
                        },
                    }
                ],
            }
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "schema_version": "dm_evidence_ref_v2",
                "evidence_ref_id": "ev:role",
                "source_artifact_id": "src:role",
                "source_revision_id": None,
                "source_domain_key": "manual_seed",
                "source_domain": "manual",
                "evidence_role": "support",
                "can_open_source": False,
                "can_highlight_span": False,
                "session_id": None,
                "source_span_ref_id": None,
                "locator": None,
                "uri": None,
                "source_locator": None,
                "line_ref": None,
            }
        ],
    }
    validate_world_property_assignment(
        property_term="dnd5e:role",
        subject_kind="dnd5e:location",
        value="city",
    )
    reader = VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )
    snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V5, graph_payload=payload)
    obj = snapshot.objects["obj:mireward"]
    assert obj.kind == "dnd5e:location"
    assert len(obj.admitted_property_assertions) == 1
    prop = obj.admitted_property_assertions[0]
    assert prop.property_term == "dnd5e:role"
    assert prop.value == "city"
    assert prop.assertion_id == "asrt:mireward-role"
