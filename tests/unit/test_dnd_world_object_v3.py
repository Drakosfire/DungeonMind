"""Immutable world-object-v3 relationship vocabulary publication proofs.

Historical world-object-v1/v2 and dnd5e-profile-v3 remain digests-pinned.
world-object-v3 is additive: same twelve kinds, expanded governed predicates.
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
    WORLD_OBJECT_V3_VOCABULARY_REVISION,
    WORLD_OBJECT_VOCABULARY_ID,
    WORLD_OBJECT_VOCABULARY_REVISION,
    builtin_world_object_v2_vocabulary_ref,
    builtin_world_object_v3_vocabulary_ref,
    builtin_world_object_vocabulary_ref,
    load_builtin_v3_descriptor,
    load_builtin_world_object_v2_vocabulary,
    load_builtin_world_object_v3_vocabulary,
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
PROFILE_V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/profiles/dnd5e-v3.json"
INVENTORY_PATH = (
    REPO_ROOT
    / "tests/fixtures/dungeonmind_dnd/eldyrwild_relationship_inventory_v1.json"
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

ALL = frozenset(
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
PEOPLE_OR_ORGS = frozenset(
    {
        "dnd5e:npc",
        "dnd5e:player_character",
        "dnd5e:faction",
        "dnd5e:group",
        "dnd5e:party",
    }
)
COMBATANT = frozenset(
    {
        "dnd5e:creature",
        "dnd5e:threat",
        "dnd5e:npc",
        "dnd5e:player_character",
        "dnd5e:faction",
        "dnd5e:group",
        "dnd5e:party",
        "dnd5e:item",
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

BUDDY_TO_DM = {
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

UNRESOLVED_BUDDY_PREDICATES = frozenset(
    {
        "carries_report_to",
        "controls_comms_with",
        "defends_weakened_location",
        "identified_as",
        "mission_targets",
        "objective_of",
        "part_of_group",
        "reports_threat_in",
        "same_as",
    }
)

DIRECT_BUDDY_PREDICATES = frozenset(
    {
        "allied_with",
        "associated_with",
        "attacks",
        "aware_of",
        "carries",
        "causes",
        "commands",
        "contains",
        "cooperates_with",
        "displaced_from",
        "holds",
        "knows_about",
        "leads",
        "leads_to",
        "located_in",
        "member_of",
        "near",
        "owns",
        "parent_of",
        "part_of",
        "participates_in",
        "possesses",
        "present_at",
        "pursues",
        "recruits_for",
        "rivals",
        "serves",
        "south_of",
        "suspects",
        "threatens",
        "travels_to",
        "trusts",
        "works_with",
    }
)

EXPECTED_RESIDUAL_BY_PREDICATE = {
    "carries": 4,
    "carries_report_to": 1,
    "contains": 2,
    "controls_comms_with": 3,
    "defends_weakened_location": 1,
    "identified_as": 4,
    "leads": 2,
    "leads_to": 5,
    "located_in": 5,
    "member_of": 1,
    "mission_targets": 1,
    "objective_of": 2,
    "part_of": 4,
    "part_of_group": 1,
    "participates_in": 6,
    "present_at": 2,
    "reports_threat_in": 1,
    "routes_to": 1,
    "same_as": 5,
    "serves": 3,
    "travels_to": 2,
    "within": 2,
}


def _endpoint_sets(catalog_term: str) -> tuple[frozenset[str], frozenset[str]]:
    predicate = next(
        p
        for p in load_builtin_world_object_v3_vocabulary().predicates
        if p.term == catalog_term
    )
    return frozenset(predicate.subject_kinds), frozenset(predicate.object_kinds)


def _map_buddy_edge(
    buddy_predicate: str,
    source_buddy_kind: str,
    target_buddy_kind: str,
) -> tuple[str, str | None]:
    """Test-only explicit source normalization — not a runtime Buddy adapter."""
    if buddy_predicate == "uses_statblock":
        return "mechanics", None
    if buddy_predicate in UNRESOLVED_BUDDY_PREDICATES:
        return "unresolved", None
    if buddy_predicate in DIRECT_BUDDY_PREDICATES:
        return "mapped", f"dnd5e:{buddy_predicate}"
    if buddy_predicate == "appeared_in":
        return "mapped", "dnd5e:present_at"
    if buddy_predicate == "belongs_to":
        return "mapped_reverse", "dnd5e:owns"
    if buddy_predicate == "linked_to":
        return "mapped", "dnd5e:associated_with"
    if buddy_predicate == "occurred_at":
        return "mapped", "dnd5e:occurs_at"
    if buddy_predicate == "participated_in":
        return "mapped", "dnd5e:participates_in"
    if buddy_predicate == "path_to":
        return "mapped", "dnd5e:leads_to"
    if buddy_predicate == "results_in":
        return "mapped", "dnd5e:causes"
    if buddy_predicate == "routes_to":
        if source_buddy_kind == "location" and target_buddy_kind == "location":
            return "mapped", "dnd5e:leads_to"
        return "unresolved", None
    if buddy_predicate == "sublocation_of":
        return "mapped", "dnd5e:part_of"
    if buddy_predicate == "within":
        if target_buddy_kind == "location":
            return "mapped", "dnd5e:located_in"
        return "unresolved", None
    return "unknown", None


def _endpoint_admitted(
    term: str,
    source_buddy_kind: str,
    target_buddy_kind: str,
    *,
    reverse: bool = False,
) -> bool:
    if source_buddy_kind not in BUDDY_TO_DM or target_buddy_kind not in BUDDY_TO_DM:
        return False
    subjects, objects = _endpoint_sets(term)
    src = BUDDY_TO_DM[target_buddy_kind if reverse else source_buddy_kind]
    tgt = BUDDY_TO_DM[source_buddy_kind if reverse else target_buddy_kind]
    return src in subjects and tgt in objects


def test_historical_profile_and_vocab_digests_unchanged() -> None:
    descriptor = load_builtin_v3_descriptor()
    assert descriptor.profile_revision == "dnd5e-profile-v3"
    assert descriptor_sha256(descriptor) == V3_DIGEST
    assert json.loads(PROFILE_V3_PATH.read_text(encoding="utf-8"))[
        "profile_revision"
    ] == "dnd5e-profile-v3"

    v1 = load_builtin_world_object_vocabulary()
    assert vocabulary_sha256(v1) == WORLD_OBJECT_V1_DIGEST
    assert builtin_world_object_vocabulary_ref().vocabulary_revision == "world-object-v1"
    assert json.loads(V1_PATH.read_text(encoding="utf-8"))["vocabulary_revision"] == (
        WORLD_OBJECT_VOCABULARY_REVISION
    )

    v2 = load_builtin_world_object_v2_vocabulary()
    assert vocabulary_sha256(v2) == WORLD_OBJECT_V2_DIGEST
    assert builtin_world_object_v2_vocabulary_ref().vocabulary_revision == (
        WORLD_OBJECT_V2_VOCABULARY_REVISION
    )
    assert json.loads(V2_PATH.read_text(encoding="utf-8"))["vocabulary_revision"] == (
        "world-object-v2"
    )


def test_mechanics_remain_exact_world_object_v1() -> None:
    assert frozenset({"dnd5e:threat", "dnd5e:npc"}) == WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS
    assert load_builtin_world_object_vocabulary().vocabulary_revision == "world-object-v1"
    assert load_builtin_world_object_v3_vocabulary().vocabulary_revision == "world-object-v3"
    assert derive_world_object_mechanics_binding is not None


def test_world_object_v3_identity_and_digest() -> None:
    catalog = load_builtin_world_object_v3_vocabulary()
    assert catalog.schema_version == "dmdnd_semantic_vocabulary_v1"
    assert catalog.vocabulary_id == WORLD_OBJECT_VOCABULARY_ID
    assert catalog.vocabulary_revision == WORLD_OBJECT_V3_VOCABULARY_REVISION
    assert catalog.semantic_profile.profile_revision == "dnd5e-profile-v3"
    assert catalog.semantic_profile.descriptor_sha256 == V3_DIGEST
    digest = vocabulary_sha256(catalog)
    assert digest == WORLD_OBJECT_V3_DIGEST
    ref = builtin_world_object_v3_vocabulary_ref()
    assert ref.vocabulary_id == WORLD_OBJECT_VOCABULARY_ID
    assert ref.vocabulary_revision == "world-object-v3"
    assert ref.catalog_sha256 == WORLD_OBJECT_V3_DIGEST
    on_disk = json.loads(V3_PATH.read_text(encoding="utf-8"))
    assert on_disk["vocabulary_revision"] == "world-object-v3"


def test_world_object_v3_kinds_identical_to_v2() -> None:
    v2 = load_builtin_world_object_v2_vocabulary()
    v3 = load_builtin_world_object_v3_vocabulary()
    assert len(v3.object_kinds) == 12
    assert [k.model_dump() for k in v3.object_kinds] == [
        k.model_dump() for k in v2.object_kinds
    ]


def test_world_object_v3_predicate_contract() -> None:
    catalog = load_builtin_world_object_v3_vocabulary()
    terms = [p.term for p in catalog.predicates]
    assert len(terms) == 35
    assert len(set(terms)) == 35
    assert set(terms) == EXPECTED_PREDICATE_TERMS
    kind_terms = {k.term for k in catalog.object_kinds}
    for predicate in catalog.predicates:
        assert set(predicate.subject_kinds) <= kind_terms
        assert set(predicate.object_kinds) <= kind_terms


def test_world_object_v3_exact_endpoint_sets() -> None:
    assert _endpoint_sets("dnd5e:located_at") == (
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:encounter",
            }
        ),
        frozenset({"dnd5e:location"}),
    )
    assert _endpoint_sets("dnd5e:member_of") == (
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:group",
            }
        ),
        frozenset({"dnd5e:faction", "dnd5e:group", "dnd5e:party"}),
    )
    assert _endpoint_sets("dnd5e:participates_in") == (
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:faction",
                "dnd5e:group",
                "dnd5e:party",
            }
        ),
        frozenset({"dnd5e:encounter", "dnd5e:event"}),
    )
    assert _endpoint_sets("dnd5e:threatens") == (
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:faction",
                "dnd5e:group",
                "dnd5e:party",
                "dnd5e:encounter",
            }
        ),
        frozenset(
            {
                "dnd5e:location",
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:faction",
                "dnd5e:group",
                "dnd5e:party",
            }
        ),
    )
    assert _endpoint_sets("dnd5e:located_in") == (
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:encounter",
                "dnd5e:item",
                "dnd5e:location",
                "dnd5e:faction",
                "dnd5e:mystery",
                "dnd5e:group",
                "dnd5e:party",
            }
        ),
        frozenset({"dnd5e:location"}),
    )
    assert _endpoint_sets("dnd5e:contains") == (
        frozenset({"dnd5e:item", "dnd5e:location"}),
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:item",
                "dnd5e:location",
                "dnd5e:faction",
                "dnd5e:group",
                "dnd5e:party",
            }
        ),
    )
    assert _endpoint_sets("dnd5e:part_of") == (
        frozenset({"dnd5e:item", "dnd5e:location"}),
        frozenset({"dnd5e:item", "dnd5e:location"}),
    )
    assert _endpoint_sets("dnd5e:leads_to") == (
        frozenset({"dnd5e:location"}),
        frozenset({"dnd5e:location"}),
    )
    assert _endpoint_sets("dnd5e:near") == (SPATIAL, SPATIAL)
    assert _endpoint_sets("dnd5e:south_of") == (
        frozenset({"dnd5e:location"}),
        frozenset({"dnd5e:location"}),
    )
    assert _endpoint_sets("dnd5e:travels_to") == (
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:faction",
                "dnd5e:group",
                "dnd5e:party",
                "dnd5e:item",
            }
        ),
        frozenset({"dnd5e:location"}),
    )
    assert _endpoint_sets("dnd5e:displaced_from") == (SOCIAL, frozenset({"dnd5e:location"}))
    assert _endpoint_sets("dnd5e:occurs_at") == (
        frozenset({"dnd5e:encounter", "dnd5e:event"}),
        frozenset({"dnd5e:location"}),
    )
    assert _endpoint_sets("dnd5e:present_at") == (
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:faction",
                "dnd5e:group",
                "dnd5e:party",
                "dnd5e:item",
            }
        ),
        frozenset({"dnd5e:location", "dnd5e:encounter", "dnd5e:event"}),
    )
    assert _endpoint_sets("dnd5e:attacks") == (COMBATANT, COMBATANT)
    assert _endpoint_sets("dnd5e:causes") == (ALL, ALL)
    assert _endpoint_sets("dnd5e:pursues") == (SOCIAL, ALL)
    assert _endpoint_sets("dnd5e:aware_of") == (SOCIAL, ALL)
    assert _endpoint_sets("dnd5e:knows_about") == (SOCIAL, ALL)
    assert _endpoint_sets("dnd5e:suspects") == (PEOPLE_OR_ORGS, ALL)
    assert _endpoint_sets("dnd5e:carries") == (SOCIAL, frozenset({"dnd5e:item"}))
    assert _endpoint_sets("dnd5e:holds") == (SOCIAL, frozenset({"dnd5e:item"}))
    assert _endpoint_sets("dnd5e:possesses") == (SOCIAL, frozenset({"dnd5e:item"}))
    assert _endpoint_sets("dnd5e:owns") == (
        PEOPLE_OR_ORGS,
        frozenset({"dnd5e:creature", "dnd5e:item", "dnd5e:location"}),
    )
    assert _endpoint_sets("dnd5e:commands") == (PEOPLE_OR_ORGS, SOCIAL)
    assert _endpoint_sets("dnd5e:leads") == (
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
            }
        ),
        frozenset({"dnd5e:faction", "dnd5e:group", "dnd5e:party"}),
    )
    assert _endpoint_sets("dnd5e:recruits_for") == (
        PEOPLE_OR_ORGS,
        frozenset({"dnd5e:faction", "dnd5e:group", "dnd5e:party"}),
    )
    assert _endpoint_sets("dnd5e:serves") == (
        SOCIAL,
        frozenset(
            {
                "dnd5e:npc",
                "dnd5e:player_character",
                "dnd5e:faction",
                "dnd5e:group",
                "dnd5e:party",
            }
        ),
    )
    assert _endpoint_sets("dnd5e:allied_with") == (SOCIAL, SOCIAL)
    assert _endpoint_sets("dnd5e:cooperates_with") == (SOCIAL, SOCIAL)
    assert _endpoint_sets("dnd5e:works_with") == (SOCIAL, SOCIAL)
    assert _endpoint_sets("dnd5e:rivals") == (SOCIAL, SOCIAL)
    assert _endpoint_sets("dnd5e:trusts") == (SOCIAL, SOCIAL)
    assert _endpoint_sets("dnd5e:parent_of") == (
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
            }
        ),
        frozenset(
            {
                "dnd5e:creature",
                "dnd5e:threat",
                "dnd5e:npc",
                "dnd5e:player_character",
            }
        ),
    )
    assert _endpoint_sets("dnd5e:associated_with") == (ALL, ALL)


def test_located_at_record_unchanged_from_v2() -> None:
    v2 = next(
        p
        for p in load_builtin_world_object_v2_vocabulary().predicates
        if p.term == "dnd5e:located_at"
    )
    v3 = next(
        p
        for p in load_builtin_world_object_v3_vocabulary().predicates
        if p.term == "dnd5e:located_at"
    )
    assert v3.model_dump() == v2.model_dump()


def test_negative_vocabulary_and_no_latest_loader() -> None:
    terms = {p.term for p in load_builtin_world_object_v3_vocabulary().predicates}
    assert FORBIDDEN_TERMS.isdisjoint(terms)
    module = (
        REPO_ROOT / "src/dungeonmind_dnd/application/world_object_vocabulary.py"
    ).read_text(encoding="utf-8")
    assert "def load_latest" not in module
    assert "def load_current" not in module
    assert "load_builtin_world_object_latest" not in module
    assert "vocabulary_revision = \"latest\"" not in module
    assert 'vocabulary_revision="latest"' not in module
    dump = json.dumps(load_builtin_world_object_v3_vocabulary().model_dump(mode="json"))
    assert "latest" not in dump
    assert "dnd5e:related_to" not in dump


def test_eldyrwild_relationship_inventory_fixture_integrity() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert inventory["schema"] == "dmdnd_eldyrwild_relationship_inventory_fixture_v1"
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
    assert inventory["edge_count"] == 348
    assert inventory["uses_statblock_count"] == 2
    assert inventory["semantic_relationship_edge_count"] == 346
    predicates = inventory["predicates"]
    assert len(predicates) == 53
    assert sum(row["count"] for row in predicates) == 348
    for row in predicates:
        assert sum(pair["count"] for pair in row["endpoint_pairs"]) == row["count"]
    uses = next(row for row in predicates if row["buddy_predicate"] == "uses_statblock")
    assert uses["count"] == 2


def test_eldyrwild_v3_relationship_coverage_288_of_346() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    residual_by: dict[str, int] = {}
    admitted = 0
    mechanics = 0

    for row in inventory["predicates"]:
        buddy_predicate = row["buddy_predicate"]
        for pair in row["endpoint_pairs"]:
            src = pair["source_buddy_kind"]
            tgt = pair["target_buddy_kind"]
            count = pair["count"]
            kind, term = _map_buddy_edge(buddy_predicate, src, tgt)
            if kind == "mechanics":
                mechanics += count
                continue
            assert kind != "unknown", buddy_predicate
            ok = False
            if kind == "mapped":
                assert term is not None
                ok = _endpoint_admitted(term, src, tgt)
            elif kind == "mapped_reverse":
                assert term is not None
                ok = _endpoint_admitted(term, src, tgt, reverse=True)
            if ok:
                admitted += count
            else:
                residual_by[buddy_predicate] = residual_by.get(buddy_predicate, 0) + count

    assert mechanics == 2
    assert admitted == 288
    assert residual_by == EXPECTED_RESIDUAL_BY_PREDICATE
    assert sum(residual_by.values()) == 58
    assert admitted + sum(residual_by.values()) == 346
    assert mechanics + admitted + sum(residual_by.values()) == 348


def test_no_string_prefix_fallback_in_mapping_table() -> None:
    # Explicit identity spellings are allowed; inventing dnd5e:<unknown> is not.
    kind, term = _map_buddy_edge("same_as", "item", "item")
    assert kind == "unresolved"
    assert term is None
    kind, term = _map_buddy_edge("identified_as", "npc", "mystery")
    assert kind == "unresolved"
    assert term is None
    # Direct accepted mapping may share spelling with source predicate.
    kind, term = _map_buddy_edge("member_of", "npc", "faction")
    assert kind == "mapped"
    assert term == "dnd5e:member_of"
    assert _endpoint_admitted(term, "npc", "faction")


def test_attacks_is_not_threatens_and_uses_statblock_absent() -> None:
    catalog = load_builtin_world_object_v3_vocabulary()
    terms = {p.term for p in catalog.predicates}
    assert "dnd5e:attacks" in terms
    assert "dnd5e:threatens" in terms
    assert "dnd5e:uses_statblock" not in terms
    located_in = next(p for p in catalog.predicates if p.term == "dnd5e:located_in")
    located_at = next(p for p in catalog.predicates if p.term == "dnd5e:located_at")
    assert located_in.model_dump() != located_at.model_dump()
