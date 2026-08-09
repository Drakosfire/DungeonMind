"""Immutable world-object-v4 relationship vocabulary publication proofs.

Historical digests remain pinned. world-object-v4 admits three new atomic
predicates and narrowly widens part_of subjects with npc only.
"""

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
    WORLD_OBJECT_VOCABULARY_ID,
    WORLD_OBJECT_VOCABULARY_REVISION,
    builtin_world_object_v2_vocabulary_ref,
    builtin_world_object_v3_vocabulary_ref,
    builtin_world_object_v4_vocabulary_ref,
    builtin_world_object_vocabulary_ref,
    load_builtin_v3_descriptor,
    load_builtin_world_object_v2_vocabulary,
    load_builtin_world_object_v3_vocabulary,
    load_builtin_world_object_v4_vocabulary,
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
PROFILE_V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/profiles/dnd5e-v3.json"
ACCEPTANCE_PATH = (
    REPO_ROOT
    / "tests/fixtures/dungeonmind_dnd/eldyrwild_relationship_v4_acceptance_v1.json"
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
WORLD_PROPERTY_V1_DIGEST = (
    "b466e3f16ae1aba5814f3386dff86b7017399c6099158d99ef95e9979d7cea7f"
)

SOCIAL = frozenset(
    {
        "dnd5e:creature",
        "dnd5e:threat",
        "dnd5e:npc",
        "dnd5e:player_character",
        "dnd5e:faction",
        "dnd5e:group",
        "dnd5e:party",
    }
)
SPATIAL = frozenset(
    {
        "dnd5e:creature",
        "dnd5e:threat",
        "dnd5e:npc",
        "dnd5e:player_character",
        "dnd5e:location",
        "dnd5e:faction",
        "dnd5e:item",
        "dnd5e:group",
        "dnd5e:party",
    }
)

EXPECTED_PREDICATE_TERMS = frozenset(
    {
        "dnd5e:located_at",
        "dnd5e:member_of",
        "dnd5e:participates_in",
        "dnd5e:threatens",
        "dnd5e:located_in",
        "dnd5e:allied_with",
        "dnd5e:associated_with",
        "dnd5e:attacks",
        "dnd5e:aware_of",
        "dnd5e:carries",
        "dnd5e:causes",
        "dnd5e:commands",
        "dnd5e:contains",
        "dnd5e:cooperates_with",
        "dnd5e:displaced_from",
        "dnd5e:holds",
        "dnd5e:knows_about",
        "dnd5e:leads",
        "dnd5e:leads_to",
        "dnd5e:near",
        "dnd5e:occurs_at",
        "dnd5e:owns",
        "dnd5e:parent_of",
        "dnd5e:part_of",
        "dnd5e:possesses",
        "dnd5e:present_at",
        "dnd5e:pursues",
        "dnd5e:recruits_for",
        "dnd5e:rivals",
        "dnd5e:serves",
        "dnd5e:south_of",
        "dnd5e:suspects",
        "dnd5e:travels_to",
        "dnd5e:trusts",
        "dnd5e:works_with",
        "dnd5e:appears_to",
        "dnd5e:communicates_with",
        "dnd5e:protects",
    }
)

FORBIDDEN_TERMS = frozenset(
    {
        "dnd5e:same_as",
        "dnd5e:identified_as",
        "dnd5e:uses_statblock",
        "dnd5e:related_to",
        "dnd5e:role",
        "dnd5e:carries_report_to",
        "dnd5e:controls_comms_with",
        "dnd5e:defends_weakened_location",
        "dnd5e:mission_targets",
        "dnd5e:objective_of",
        "dnd5e:part_of_group",
        "dnd5e:reports_threat_in",
    }
)


def _endpoint_sets(catalog_term: str) -> tuple[frozenset[str], frozenset[str]]:
    predicate = next(
        p
        for p in load_builtin_world_object_v4_vocabulary().predicates
        if p.term == catalog_term
    )
    return frozenset(predicate.subject_kinds), frozenset(predicate.object_kinds)


def _admitted(term: str, subject_kind: str, object_kind: str) -> bool:
    subjects, objects = _endpoint_sets(term)
    return subject_kind in subjects and object_kind in objects


def test_historical_profile_and_vocab_digests_unchanged() -> None:
    descriptor = load_builtin_v3_descriptor()
    assert descriptor.profile_revision == "dnd5e-profile-v3"
    assert descriptor_sha256(descriptor) == V3_DIGEST
    assert json.loads(PROFILE_V3_PATH.read_text(encoding="utf-8"))[
        "profile_revision"
    ] == "dnd5e-profile-v3"

    assert vocabulary_sha256(load_builtin_world_object_vocabulary()) == WORLD_OBJECT_V1_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v2_vocabulary()) == WORLD_OBJECT_V2_DIGEST
    assert vocabulary_sha256(load_builtin_world_object_v3_vocabulary()) == WORLD_OBJECT_V3_DIGEST
    assert builtin_world_object_vocabulary_ref().vocabulary_revision == (
        WORLD_OBJECT_VOCABULARY_REVISION
    )
    assert builtin_world_object_v2_vocabulary_ref().vocabulary_revision == (
        WORLD_OBJECT_V2_VOCABULARY_REVISION
    )
    assert builtin_world_object_v3_vocabulary_ref().vocabulary_revision == (
        WORLD_OBJECT_V3_VOCABULARY_REVISION
    )
    assert json.loads(V1_PATH.read_text(encoding="utf-8"))["vocabulary_revision"] == (
        "world-object-v1"
    )
    assert json.loads(V2_PATH.read_text(encoding="utf-8"))["vocabulary_revision"] == (
        "world-object-v2"
    )
    assert json.loads(V3_PATH.read_text(encoding="utf-8"))["vocabulary_revision"] == (
        "world-object-v3"
    )


def test_mechanics_remain_exact_world_object_v1() -> None:
    assert frozenset({"dnd5e:threat", "dnd5e:npc"}) == WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS
    assert load_builtin_world_object_vocabulary().vocabulary_revision == "world-object-v1"
    assert load_builtin_world_object_v4_vocabulary().vocabulary_revision == "world-object-v4"
    assert derive_world_object_mechanics_binding is not None


def test_no_latest_or_current_world_object_loader() -> None:
    names = dir(world_object_vocab_module)
    assert "load_latest_world_object_vocabulary" not in names
    assert "load_current_world_object_vocabulary" not in names
    assert "default_vocabulary" not in names
    assert "highest_revision" not in names


def test_world_object_v4_identity_and_digest() -> None:
    catalog = load_builtin_world_object_v4_vocabulary()
    assert catalog.schema_version == "dmdnd_semantic_vocabulary_v1"
    assert catalog.vocabulary_id == WORLD_OBJECT_VOCABULARY_ID
    assert catalog.vocabulary_revision == WORLD_OBJECT_V4_VOCABULARY_REVISION
    assert catalog.semantic_profile.profile_revision == "dnd5e-profile-v3"
    assert catalog.semantic_profile.descriptor_sha256 == V3_DIGEST
    digest = vocabulary_sha256(catalog)
    assert digest == WORLD_OBJECT_V4_DIGEST
    ref = builtin_world_object_v4_vocabulary_ref()
    assert ref.vocabulary_id == WORLD_OBJECT_VOCABULARY_ID
    assert ref.vocabulary_revision == "world-object-v4"
    assert ref.catalog_sha256 == WORLD_OBJECT_V4_DIGEST
    on_disk = json.loads(V4_PATH.read_text(encoding="utf-8"))
    assert on_disk["vocabulary_revision"] == "world-object-v4"


def test_world_object_v4_kinds_identical_to_v3() -> None:
    v3 = load_builtin_world_object_v3_vocabulary()
    v4 = load_builtin_world_object_v4_vocabulary()
    assert len(v4.object_kinds) == 12
    assert [k.model_dump() for k in v4.object_kinds] == [
        k.model_dump() for k in v3.object_kinds
    ]


def test_world_object_v4_predicate_contract() -> None:
    catalog = load_builtin_world_object_v4_vocabulary()
    terms = [p.term for p in catalog.predicates]
    assert len(terms) == 38
    assert len(set(terms)) == 38
    assert set(terms) == EXPECTED_PREDICATE_TERMS
    kind_terms = {k.term for k in catalog.object_kinds}
    for predicate in catalog.predicates:
        assert set(predicate.subject_kinds) <= kind_terms
        assert set(predicate.object_kinds) <= kind_terms


def test_world_object_v4_preserves_unchanged_v3_predicates() -> None:
    v3 = load_builtin_world_object_v3_vocabulary()
    v4 = load_builtin_world_object_v4_vocabulary()
    v3_by_term = {p.term: p.model_dump() for p in v3.predicates}
    v4_by_term = {p.term: p.model_dump() for p in v4.predicates}
    changed = sorted(term for term, dump in v3_by_term.items() if v4_by_term[term] != dump)
    assert changed == ["dnd5e:part_of"]
    unchanged = [term for term in v3_by_term if term != "dnd5e:part_of"]
    assert len(unchanged) == 34
    for term in unchanged:
        assert v4_by_term[term] == v3_by_term[term]
    assert sorted(set(v4_by_term) - set(v3_by_term)) == [
        "dnd5e:appears_to",
        "dnd5e:communicates_with",
        "dnd5e:protects",
    ]


def test_world_object_v4_part_of_endpoint_extension() -> None:
    subjects, objects = _endpoint_sets("dnd5e:part_of")
    assert subjects == frozenset({"dnd5e:item", "dnd5e:location", "dnd5e:npc"})
    assert objects == frozenset({"dnd5e:item", "dnd5e:location"})
    part_of = next(
        p for p in load_builtin_world_object_v4_vocabulary().predicates if p.term == "dnd5e:part_of"
    )
    v3_part_of = next(
        p for p in load_builtin_world_object_v3_vocabulary().predicates if p.term == "dnd5e:part_of"
    )
    assert part_of.description == v3_part_of.description
    assert part_of.label == v3_part_of.label


def test_world_object_v4_new_predicate_endpoint_sets() -> None:
    assert _endpoint_sets("dnd5e:appears_to") == (SOCIAL, SOCIAL)
    assert _endpoint_sets("dnd5e:communicates_with") == (SOCIAL, SOCIAL)
    assert _endpoint_sets("dnd5e:protects") == (SOCIAL, SPATIAL)


def test_acceptance_fixture_four_rows_admitted() -> None:
    payload = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    assert payload["authority"]["buddy_merge"] == (
        "67025dee9cc06d8bd3b566581bb4ef26baaabd70"
    )
    assert payload["authority"]["revision_id"] == "rev:3413bf6f5044cf2680233f5e37c90dcf"
    assert payload["authority"]["graph_payload_sha256"] == (
        "346c1fbfb3cbbf6d0e5ded1453fdd7760264a5106022e398d6074679799ab0fa"
    )
    summary = payload["residual_summary"]
    assert summary["total_residual_count"] == 59
    assert summary["dungeonmind_owned_count"] == 4
    assert summary["buddy_owned_count"] == 55
    rows = payload["dungeonmind_owned_rows"]
    assert len(rows) == 4
    for row in rows:
        assert _admitted(
            row["candidate_term"],
            row["source_dm_kind"],
            row["target_dm_kind"],
        )
    by_term = {row["candidate_term"]: row for row in rows}
    assert by_term["dnd5e:appears_to"]["source_dm_kind"] == "dnd5e:faction"
    assert by_term["dnd5e:appears_to"]["target_dm_kind"] == "dnd5e:player_character"
    assert by_term["dnd5e:protects"]["source_dm_kind"] == "dnd5e:player_character"
    assert by_term["dnd5e:protects"]["target_dm_kind"] == "dnd5e:group"
    assert by_term["dnd5e:communicates_with"]["source_dm_kind"] == "dnd5e:player_character"
    assert by_term["dnd5e:communicates_with"]["target_dm_kind"] == "dnd5e:npc"
    assert by_term["dnd5e:part_of"]["source_dm_kind"] == "dnd5e:npc"
    assert by_term["dnd5e:part_of"]["target_dm_kind"] == "dnd5e:item"
    assert payload["not_claimed_by_this_publication"]["buddy_owned_count"] == 55


def test_part_of_rejects_unrelated_residual_endpoint_pairs() -> None:
    assert not _admitted("dnd5e:part_of", "dnd5e:group", "dnd5e:location")
    assert not _admitted("dnd5e:part_of", "dnd5e:location", "dnd5e:party")
    assert not _admitted("dnd5e:part_of", "dnd5e:faction", "dnd5e:npc")


def test_appears_to_rejects_non_social_endpoints() -> None:
    assert not _admitted("dnd5e:appears_to", "dnd5e:item", "dnd5e:player_character")
    assert not _admitted("dnd5e:appears_to", "dnd5e:location", "dnd5e:player_character")
    assert not _admitted("dnd5e:appears_to", "dnd5e:event", "dnd5e:player_character")
    assert not _admitted("dnd5e:appears_to", "dnd5e:mystery", "dnd5e:player_character")
    assert not _admitted("dnd5e:appears_to", "dnd5e:npc", "dnd5e:location")


def test_communicates_with_rejects_non_social_endpoints() -> None:
    assert not _admitted("dnd5e:communicates_with", "dnd5e:player_character", "dnd5e:item")
    assert not _admitted(
        "dnd5e:communicates_with", "dnd5e:player_character", "dnd5e:location"
    )
    assert not _admitted("dnd5e:communicates_with", "dnd5e:item", "dnd5e:npc")
    assert not _admitted("dnd5e:communicates_with", "dnd5e:event", "dnd5e:npc")


def test_protects_rejects_non_admitted_endpoints() -> None:
    assert not _admitted("dnd5e:protects", "dnd5e:event", "dnd5e:group")
    assert not _admitted("dnd5e:protects", "dnd5e:mystery", "dnd5e:group")
    assert not _admitted("dnd5e:protects", "dnd5e:encounter", "dnd5e:group")
    assert not _admitted("dnd5e:protects", "dnd5e:player_character", "dnd5e:mystery")
    assert not _admitted("dnd5e:protects", "dnd5e:player_character", "dnd5e:event")
    assert not _admitted("dnd5e:protects", "dnd5e:player_character", "dnd5e:encounter")


def test_forbidden_terms_absent_from_v4() -> None:
    terms = {p.term for p in load_builtin_world_object_v4_vocabulary().predicates}
    kinds = {k.term for k in load_builtin_world_object_v4_vocabulary().object_kinds}
    assert FORBIDDEN_TERMS.isdisjoint(terms)
    assert FORBIDDEN_TERMS.isdisjoint(kinds)


def test_property_v1_digest_still_pinned_in_v4_suite() -> None:
    from dungeonmind_dnd.application.world_property_vocabulary import (
        load_builtin_world_property_vocabulary,
        world_property_vocabulary_sha256,
    )

    assert (
        world_property_vocabulary_sha256(load_builtin_world_property_vocabulary())
        == WORLD_PROPERTY_V1_DIGEST
    )
