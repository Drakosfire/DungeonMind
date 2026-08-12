"""Immutable world-object-v5 campaign-thread publication proofs (CUTOVER Case A)."""

from __future__ import annotations

import json
from pathlib import Path

from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind_dnd.application import world_object_vocabulary as world_object_vocab_module
from dungeonmind_dnd.application.world_object_mechanics import (
    derive_world_object_mechanics_binding,
)
from dungeonmind_dnd.application.world_object_vocabulary import (
    WORLD_OBJECT_V2_VOCABULARY_REVISION,
    WORLD_OBJECT_V3_VOCABULARY_REVISION,
    WORLD_OBJECT_V4_VOCABULARY_REVISION,
    WORLD_OBJECT_V5_VOCABULARY_REVISION,
    WORLD_OBJECT_VOCABULARY_ID,
    WORLD_OBJECT_VOCABULARY_REVISION,
    builtin_world_object_v2_vocabulary_ref,
    builtin_world_object_v3_vocabulary_ref,
    builtin_world_object_v4_vocabulary_ref,
    builtin_world_object_v5_vocabulary_ref,
    builtin_world_object_vocabulary_ref,
    load_builtin_v3_descriptor,
    load_builtin_world_object_v2_vocabulary,
    load_builtin_world_object_v3_vocabulary,
    load_builtin_world_object_v4_vocabulary,
    load_builtin_world_object_v5_vocabulary,
    load_builtin_world_object_vocabulary,
    vocabulary_sha256,
)
from dungeonmind_dnd.contracts.world_object_mechanics import (
    WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
V1_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v1.json"
V2_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v2.json"
V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v3.json"
V4_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v4.json"
V5_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v5.json"
PROFILE_V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/profiles/dnd5e-v3.json"
ACCEPTANCE_PATH = (
    REPO_ROOT / "tests/fixtures/dungeonmind_dnd/eldyrwild_thread_kind_acceptance_v1.json"
)
ADR_PATH = (
    REPO_ROOT / "Docs/Decisions/ADR-0017-campaign-thread-world-object-kind-v5.md"
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
WORLD_OBJECT_V4_DIGEST = (
    "552c59a3fa9a20e437294d1a77974c05e37b69ec95e5ea03337a7d010e4d287b"
)
WORLD_OBJECT_V5_DIGEST = (
    "f9fd5420e0ab3849224e0d58cf83dd432ca2e5da22ce661b25654406ec9c60d8"
)
WORLD_PROPERTY_V2_DIGEST = (
    "8ad4c223e83ce48cf5cd33a33e10f5be5d48a80ad742784d7c561470b450ab73"
)
WORLD_PROPERTY_V3_DIGEST = (
    "aa94df78c10a913e7ca6774198f080131f8f447c90cc917b9b840ed88bd856e4"
)


def test_predecessor_pins_and_historical_immutability() -> None:
    descriptor = load_builtin_v3_descriptor()
    assert descriptor.profile_revision == "dnd5e-profile-v3"
    assert descriptor_sha256(descriptor) == V3_DIGEST
    assert json.loads(PROFILE_V3_PATH.read_text(encoding="utf-8"))[
        "profile_revision"
    ] == "dnd5e-profile-v3"
    assert vocabulary_sha256(load_builtin_world_object_vocabulary()) == WORLD_OBJECT_V1_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v2_vocabulary()) == WORLD_OBJECT_V2_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v3_vocabulary()) == WORLD_OBJECT_V3_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v4_vocabulary()) == WORLD_OBJECT_V4_DIGEST
    assert builtin_world_object_vocabulary_ref().vocabulary_revision == (
        WORLD_OBJECT_VOCABULARY_REVISION
    )
    assert builtin_world_object_v2_vocabulary_ref().vocabulary_revision == (
        WORLD_OBJECT_V2_VOCABULARY_REVISION
    )
    assert builtin_world_object_v3_vocabulary_ref().vocabulary_revision == (
        WORLD_OBJECT_V3_VOCABULARY_REVISION
    )
    assert builtin_world_object_v4_vocabulary_ref().vocabulary_revision == (
        WORLD_OBJECT_V4_VOCABULARY_REVISION
    )
    assert builtin_world_object_v4_vocabulary_ref().catalog_sha256 == WORLD_OBJECT_V4_DIGEST
    for path in (V1_PATH, V2_PATH, V3_PATH, V4_PATH):
        assert path.is_file()


def test_world_object_v5_identity_and_digest() -> None:
    catalog = load_builtin_world_object_v5_vocabulary()
    assert catalog.vocabulary_id == WORLD_OBJECT_VOCABULARY_ID
    assert catalog.vocabulary_revision == WORLD_OBJECT_V5_VOCABULARY_REVISION
    assert catalog.schema_version == "dmdnd_semantic_vocabulary_v1"
    assert catalog.semantic_profile.profile_revision == "dnd5e-profile-v3"
    assert catalog.semantic_profile.descriptor_sha256 == V3_DIGEST
    digest = vocabulary_sha256(catalog)
    assert digest == WORLD_OBJECT_V5_DIGEST
    ref = builtin_world_object_v5_vocabulary_ref()
    assert ref.vocabulary_revision == "world-object-v5"
    assert ref.catalog_sha256 == WORLD_OBJECT_V5_DIGEST
    on_disk = json.loads(V5_PATH.read_text(encoding="utf-8"))
    assert on_disk["vocabulary_revision"] == "world-object-v5"


def test_exact_kind_delta_and_predicates_unchanged() -> None:
    v4 = load_builtin_world_object_v4_vocabulary()
    v5 = load_builtin_world_object_v5_vocabulary()
    assert len(v4.object_kinds) == 12
    assert len(v5.object_kinds) == 13
    v4_terms = {kind.term for kind in v4.object_kinds}
    v5_terms = {kind.term for kind in v5.object_kinds}
    assert v5_terms - v4_terms == {"dnd5e:thread"}
    assert v4_terms - v5_terms == set()
    for kind in v4.object_kinds:
        match = next(item for item in v5.object_kinds if item.term == kind.term)
        assert match.model_dump() == kind.model_dump()
    assert [p.model_dump() for p in v5.predicates] == [
        p.model_dump() for p in v4.predicates
    ]
    for predicate in v5.predicates:
        assert "dnd5e:thread" not in predicate.subject_kinds
        assert "dnd5e:thread" not in predicate.object_kinds


def test_thread_semantic_boundaries_sealed() -> None:
    catalog = load_builtin_world_object_v5_vocabulary()
    thread = next(kind for kind in catalog.object_kinds if kind.term == "dnd5e:thread")
    assert thread.label == "Thread"
    description = thread.description.lower()
    for token in (
        "mystery",
        "secrecy",
        "event",
        "quest",
        "objective",
        "epistemic",
        "fictional-time",
        "mechanics",
    ):
        assert token in description
    adr = ADR_PATH.read_text(encoding="utf-8").lower()
    assert "thread → mystery" in adr or "thread -> mystery" in adr
    assert "thread → event" in adr or "thread -> event" in adr
    assert "no profile" in adr or "no profile, union-graph" in adr


def test_cutover_thread_kind_acceptance_witness() -> None:
    fixture = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    assert fixture["schema"] == "dmdnd_eldyrwild_thread_kind_acceptance_v1"
    source = fixture["cutover_source"]
    assert source["repository"] == "Drakosfire/DungeonMindBuddy"
    assert source["pr"] == 568
    assert source["merge_commit"] == "e5aaaf1d3d1e1e9f8c07a62383770dfd8326f259"
    assert source["world_id"] == "eldyrwild"
    assert source["canonical_revision_id"] == "rev:5a7c13ae45c49a65b402920499be72ed"
    assert source["canonical_graph_payload_sha256"] == (
        "2632870ef70638969503de788cfdec97acd490875deff3e2630ac91dc96fe974"
    )
    assert source["node_kind_repair_manifest_sha256"] == (
        "96cc26fc6e99448e8fba5cd6982070c1e29bb058f2b1e8a4ac291f8a0a083247"
    )
    assert source["cutover_reanchor_fixture_sha256"] == (
        "6c978f89527ccd82e9bad32eac70a5386a5d714e80f7e426f574d7dbc0e43cbf"
    )
    blocker = fixture["blocker"]
    assert blocker["blocker_class"] == "WORLD_OBJECT_KIND"
    assert blocker["count"] == 1
    assert blocker["blocking_stage"] == "adoption_package_construction"
    assert blocker["responsible_repo"] == "DungeonMind"
    assert blocker["buddy_kind"] == "thread"
    assert blocker["target_term"] == "dnd5e:thread"
    assert blocker["durable_field_path"] == (
        "node:mystery:session25:light-and-sound-as-search-tools-during-night-response:field:kind"
    )
    catalogs = fixture["published_catalogs"]
    assert catalogs["world_object_v5"]["catalog_sha256"] == WORLD_OBJECT_V5_DIGEST
    assert catalogs["world_property_v3"]["catalog_sha256"] == WORLD_PROPERTY_V3_DIGEST
    v4_terms = {kind.term for kind in load_builtin_world_object_v4_vocabulary().object_kinds}
    v5_terms = {kind.term for kind in load_builtin_world_object_v5_vocabulary().object_kinds}
    assert "dnd5e:thread" not in v4_terms
    assert "dnd5e:thread" in v5_terms
    assert fixture["cutover_nonclaim"]["cutover_ready"] is False
    assert fixture["cutover_nonclaim"]["dual_sense_stops_remain"] is True
    assert fixture["cutover_nonclaim"]["durable_adoption_boundary_missing"] is True


def test_mechanics_unchanged_and_thread_not_eligible() -> None:
    assert "dnd5e:thread" not in WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS
    assert WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS == frozenset({"dnd5e:threat", "dnd5e:npc"})
    assert callable(derive_world_object_mechanics_binding)


def test_explicit_loaders_only_no_latest_alias() -> None:
    names = dir(world_object_vocab_module)
    assert "load_latest_world_object_vocabulary" not in names
    assert "load_current_world_object_vocabulary" not in names
    module_text = (
        REPO_ROOT / "src/dungeonmind_dnd/application/world_object_vocabulary.py"
    ).read_text(encoding="utf-8")
    assert "def load_latest" not in module_text
    assert "def load_current" not in module_text
    assert "DungeonMindBuddy" not in module_text
