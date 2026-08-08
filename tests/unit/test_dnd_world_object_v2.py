"""Immutable world-object-v2 catalog publication proofs (ADR-0016).

Historical world-object-v1 and dnd5e-profile-v3 remain digests-pinned.
world-object-v2 is additive: five peer kinds, predicates frozen as v1 copies.
"""

from __future__ import annotations

import json
from pathlib import Path

from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind_dnd.application.world_object_mechanics import (
    derive_world_object_mechanics_binding,
)
from dungeonmind_dnd.application.world_object_vocabulary import (
    WORLD_OBJECT_V2_VOCABULARY_REVISION,
    WORLD_OBJECT_VOCABULARY_ID,
    WORLD_OBJECT_VOCABULARY_REVISION,
    builtin_world_object_v2_vocabulary_ref,
    builtin_world_object_vocabulary_ref,
    load_builtin_v3_descriptor,
    load_builtin_world_object_v2_vocabulary,
    load_builtin_world_object_vocabulary,
    vocabulary_sha256,
)
from dungeonmind_dnd.contracts.world_object_mechanics import (
    WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
V1_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v1.json"
V2_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v2.json"
PROFILE_V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/profiles/dnd5e-v3.json"
INVENTORY_PATH = (
    REPO_ROOT
    / "tests/fixtures/dungeonmind_dnd/eldyrwild_kind_inventory_v1.json"
)

V3_DIGEST = "2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496"
WORLD_OBJECT_V1_DIGEST = (
    "7cc3b285611ed13eb01e0cdc8a963cfa0bea3130abe0ce816204ab67186cb880"
)
WORLD_OBJECT_V2_DIGEST = (
    "a53e2d0ec45878288800ff3d30006d54803db70a17e6680b359a0fa88f2a9922"
)

V1_KINDS = {
    "dnd5e:creature",
    "dnd5e:threat",
    "dnd5e:npc",
    "dnd5e:player_character",
    "dnd5e:location",
    "dnd5e:faction",
    "dnd5e:encounter",
}
V2_NEW_KINDS = {
    "dnd5e:item",
    "dnd5e:mystery",
    "dnd5e:group",
    "dnd5e:party",
    "dnd5e:event",
}

# Explicit Buddy inventory → target term table for the pinned #522 fixture.
# This is test evidence, not a runtime adapter.
BUDDY_KIND_TARGETS: dict[str, str | None] = {
    "threat": "dnd5e:threat",
    "npc": "dnd5e:npc",
    "pc": "dnd5e:player_character",
    "creature": "dnd5e:creature",
    "location": "dnd5e:location",
    "faction": "dnd5e:faction",
    "encounter": "dnd5e:encounter",
    "item": "dnd5e:item",
    "mystery": "dnd5e:mystery",
    "group": "dnd5e:group",
    "party": "dnd5e:party",
    "event": "dnd5e:event",
    "external_resource": None,  # mechanics specialization, not a world-object kind
}

MISSING_UNDER_V1 = {
    "item": 125,
    "mystery": 93,
    "group": 29,
    "party": 11,
    "event": 2,
}


def test_historical_profile_v3_bytes_and_digest_unchanged() -> None:
    raw = PROFILE_V3_PATH.read_bytes()
    assert raw  # non-empty
    descriptor = load_builtin_v3_descriptor()
    assert descriptor.profile_revision == "dnd5e-profile-v3"
    assert descriptor_sha256(descriptor) == V3_DIGEST
    assert json.loads(raw.decode("utf-8"))["profile_revision"] == "dnd5e-profile-v3"


def test_historical_world_object_v1_bytes_and_digest_unchanged() -> None:
    on_disk = json.loads(V1_PATH.read_text(encoding="utf-8"))
    catalog = load_builtin_world_object_vocabulary()
    assert on_disk["vocabulary_revision"] == "world-object-v1"
    assert vocabulary_sha256(catalog) == WORLD_OBJECT_V1_DIGEST
    assert catalog.vocabulary_revision == WORLD_OBJECT_VOCABULARY_REVISION
    assert {k.term for k in catalog.object_kinds} == V1_KINDS
    ref = builtin_world_object_vocabulary_ref()
    assert ref.vocabulary_revision == "world-object-v1"
    assert ref.catalog_sha256 == WORLD_OBJECT_V1_DIGEST


def test_mechanics_remain_pinned_to_world_object_v1() -> None:
    """Mechanics eligibility and historical pin stay on world-object-v1."""
    assert frozenset(
        {"dnd5e:threat", "dnd5e:npc"}
    ) == WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS
    assert V2_NEW_KINDS.isdisjoint(WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS)
    # Historical loader still serves v1; v2 is a separate explicit pin.
    assert load_builtin_world_object_vocabulary().vocabulary_revision == "world-object-v1"
    assert load_builtin_world_object_v2_vocabulary().vocabulary_revision == "world-object-v2"
    assert derive_world_object_mechanics_binding is not None


def test_world_object_v2_identity_and_digest() -> None:
    catalog = load_builtin_world_object_v2_vocabulary()
    assert catalog.schema_version == "dmdnd_semantic_vocabulary_v1"
    assert catalog.vocabulary_id == WORLD_OBJECT_VOCABULARY_ID
    assert catalog.vocabulary_revision == WORLD_OBJECT_V2_VOCABULARY_REVISION
    assert catalog.semantic_profile.profile_revision == "dnd5e-profile-v3"
    assert catalog.semantic_profile.descriptor_sha256 == V3_DIGEST
    digest = vocabulary_sha256(catalog)
    assert digest == WORLD_OBJECT_V2_DIGEST
    ref = builtin_world_object_v2_vocabulary_ref()
    assert ref.vocabulary_revision == "world-object-v2"
    assert ref.catalog_sha256 == WORLD_OBJECT_V2_DIGEST
    assert ref.vocabulary_id == WORLD_OBJECT_VOCABULARY_ID


def test_world_object_v2_has_exactly_twelve_kinds() -> None:
    catalog = load_builtin_world_object_v2_vocabulary()
    terms = [kind.term for kind in catalog.object_kinds]
    assert len(terms) == 12
    assert len(set(terms)) == 12
    assert set(terms) == V1_KINDS | V2_NEW_KINDS
    # V1 seven kinds retained with identical metadata.
    v1 = {k.term: k for k in load_builtin_world_object_vocabulary().object_kinds}
    v2 = {k.term: k for k in catalog.object_kinds}
    for term in V1_KINDS:
        assert v2[term].model_dump() == v1[term].model_dump()


def test_world_object_v2_predicates_equal_v1_byte_for_byte() -> None:
    v1 = load_builtin_world_object_vocabulary()
    v2 = load_builtin_world_object_v2_vocabulary()
    assert len(v2.predicates) == 4
    assert {p.term for p in v2.predicates} == {p.term for p in v1.predicates}
    v1_by_term = {p.term: p for p in v1.predicates}
    for predicate in v2.predicates:
        assert predicate.model_dump() == v1_by_term[predicate.term].model_dump()
    forbidden = {"dnd5e:located_in", "dnd5e:attacks", "dnd5e:contains", "located_in"}
    present = {p.term for p in v2.predicates} | {
        p.term.split(":", 1)[-1] for p in v2.predicates
    }
    assert forbidden.isdisjoint(present)


def test_world_object_v2_on_disk_matches_loader() -> None:
    on_disk = json.loads(V2_PATH.read_text(encoding="utf-8"))
    catalog = load_builtin_world_object_v2_vocabulary()
    assert on_disk["vocabulary_revision"] == "world-object-v2"
    assert on_disk["vocabulary_id"] == catalog.vocabulary_id
    assert len(on_disk["object_kinds"]) == 12
    assert len(on_disk["predicates"]) == 4


def test_new_kind_descriptions_encode_negative_boundaries() -> None:
    by_term = {
        kind.term: kind.description
        for kind in load_builtin_world_object_v2_vocabulary().object_kinds
    }
    assert "mechanics" in by_term["dnd5e:item"].casefold()
    assert "external" in by_term["dnd5e:item"].casefold()
    assert "epistemic" in by_term["dnd5e:mystery"].casefold()
    assert "speculative" in by_term["dnd5e:mystery"].casefold()
    assert "faction" in by_term["dnd5e:group"].casefold()
    assert "party" in by_term["dnd5e:group"].casefold()
    assert "player" in by_term["dnd5e:party"].casefold()
    assert "faction" in by_term["dnd5e:party"].casefold()
    assert "encounter" in by_term["dnd5e:event"].casefold()
    assert "session" in by_term["dnd5e:event"].casefold()
    assert "fictional-time" in by_term["dnd5e:event"].casefold()


def test_no_hierarchy_or_property_catalog_in_v2() -> None:
    catalog = load_builtin_world_object_v2_vocabulary()
    dump = catalog.model_dump(mode="json")
    blob = json.dumps(dump)
    for forbidden in (
        "is_a",
        "subclass_of",
        "kind_parent",
        "kind_family",
        "dnd5e:role",
        "property_terms",
        "latest",
    ):
        assert forbidden not in blob
    assert "properties" not in dump


def test_eldyrwild_kind_inventory_world_object_kind_gap_closes_under_v2() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert inventory["schema"] == "dmdnd_eldyrwild_kind_inventory_fixture_v1"
    assert inventory["source"]["world_id"] == "eldyrwild"
    assert (
        inventory["source"]["revision_id"]
        == "rev:3413bf6f5044cf2680233f5e37c90dcf"
    )
    counts: dict[str, int] = inventory["kind_counts"]
    assert sum(MISSING_UNDER_V1[k] for k in MISSING_UNDER_V1) == 260
    for kind, expected in MISSING_UNDER_V1.items():
        assert counts[kind] == expected

    v1_terms = {k.term for k in load_builtin_world_object_vocabulary().object_kinds}
    v2_terms = {k.term for k in load_builtin_world_object_v2_vocabulary().object_kinds}

    missing_v1_instances = 0
    for buddy_kind, count in counts.items():
        target = BUDDY_KIND_TARGETS[buddy_kind]
        if target is None:
            continue  # external_resource is not a WORLD_OBJECT_KIND
        if target not in v1_terms:
            missing_v1_instances += count
        assert target in v2_terms

    assert missing_v1_instances == 260
    # All WORLD_OBJECT_KIND instances are structurally representable under v2.
    world_object_instances = sum(
        count
        for buddy_kind, count in counts.items()
        if BUDDY_KIND_TARGETS[buddy_kind] is not None
    )
    assert world_object_instances == sum(counts.values()) - counts["external_resource"]
    assert all(
        BUDDY_KIND_TARGETS[buddy_kind] in v2_terms
        for buddy_kind in counts
        if BUDDY_KIND_TARGETS[buddy_kind] is not None
    )


def test_v2_publication_does_not_claim_whole_graph_ready() -> None:
    # Documentary/executable nonclaim: the inventory fixture still leaves
    # relationship/property/adoption work outside this catalog.
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert "predicate_counts" not in inventory
    assert "WHOLE_GRAPH_ADOPTION_READY" not in json.dumps(inventory)
