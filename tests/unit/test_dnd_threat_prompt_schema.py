"""Deterministic JSON Schema and prompt-fragment proofs."""

from __future__ import annotations

from typing import Any

from dungeonmind.domain.canonical import canonical_sha256, sha256_text
from dungeonmind_dnd.application.threat_candidates import (
    load_builtin_threat_vocabulary,
    render_threat_vocabulary_prompt,
    threat_candidate_json_schema,
)

SCHEMA_DIGEST = "54833e753515b3ff497a0f408e62e9dbdc4852be8bbc80b0fe712de6b440ad2e"
PROMPT_DIGEST = "5b94c0a1ffe1ce315bae3ed720d5343bdcc472295681d6b9636f222f4fd60a6c"

EXPECTED_KINDS = ["dnd5e:creature", "dnd5e:encounter", "dnd5e:faction", "dnd5e:location"]
EXPECTED_PREDICATES = [
    "dnd5e:located_at",
    "dnd5e:member_of",
    "dnd5e:participates_in",
    "dnd5e:threatens",
]

FORBIDDEN_PROSE = [
    "Tripod",
    "North Gate",
    "armor class",
    "hit points",
    "challenge rating",
    "legendary action",
    "spell slot",
]


def _string_branch(prop: dict[str, Any]) -> dict[str, Any]:
    if "anyOf" in prop:
        for branch in prop["anyOf"]:
            if branch.get("type") == "string":
                return branch
        raise AssertionError("no string branch in anyOf")
    return prop


def test_json_schema_is_deterministic_and_digest_pinned() -> None:
    first = threat_candidate_json_schema()
    second = threat_candidate_json_schema()
    assert first == second
    assert canonical_sha256(first) == SCHEMA_DIGEST


def test_json_schema_injects_exact_catalog_enums() -> None:
    schema = threat_candidate_json_schema()
    defs = schema["$defs"]
    node_kind = _string_branch(defs["DndNodeCandidate"]["properties"]["kind"])
    assert node_kind["enum"] == EXPECTED_KINDS
    predicate = _string_branch(
        defs["DndRelationshipCandidate"]["properties"]["predicate"]
    )
    assert predicate["enum"] == EXPECTED_PREDICATES
    expected_kind = _string_branch(
        defs["DndCandidateEndpointRef"]["properties"]["expected_kind"]
    )
    assert expected_kind["enum"] == EXPECTED_KINDS


def test_json_schema_stays_strict() -> None:
    schema = threat_candidate_json_schema()
    assert schema["additionalProperties"] is False
    for model_name in (
        "DndNodeCandidate",
        "DndRelationshipCandidate",
        "DndCandidateEndpointRef",
    ):
        assert schema["$defs"][model_name]["additionalProperties"] is False


def test_prompt_is_deterministic_and_digest_pinned() -> None:
    first = render_threat_vocabulary_prompt()
    second = render_threat_vocabulary_prompt()
    assert first == second
    assert sha256_text(first) == PROMPT_DIGEST


def test_prompt_lists_exact_terms_and_direction() -> None:
    prompt = render_threat_vocabulary_prompt()
    catalog = load_builtin_threat_vocabulary()
    for kind in catalog.object_kinds:
        assert f"- {kind.term} ({kind.label}): {kind.description}" in prompt
    for predicate in catalog.predicates:
        assert (
            f"- {predicate.term} ({predicate.label}): {predicate.description}"
            in prompt
        )
        subjects = " | ".join(predicate.subject_kinds)
        objects = " | ".join(predicate.object_kinds)
        assert f"direction: {subjects} -> {objects}" in prompt
    # Threat-as-relationship rule, naming both the predicate and the
    # forbidden kind.
    assert "dnd5e:threatens" in prompt
    assert "never an object kind" in prompt
    assert "dnd5e:threat." in prompt


def test_prompt_contains_no_campaign_prose_or_rulebook_text() -> None:
    prompt = render_threat_vocabulary_prompt()
    for needle in FORBIDDEN_PROSE:
        assert needle not in prompt


def test_prompt_is_derived_from_catalog_data_only() -> None:
    prompt = render_threat_vocabulary_prompt()
    catalog = load_builtin_threat_vocabulary()
    catalog_terms = {kind.term for kind in catalog.object_kinds}
    catalog_terms |= {predicate.term for predicate in catalog.predicates}
    mentioned = {
        stripped
        for token in prompt.split()
        if (stripped := token.strip(".,;()")).startswith("dnd5e:")
    }
    assert catalog_terms <= mentioned
    # The only non-catalog term named is the explicitly forbidden kind.
    assert mentioned - catalog_terms == {"dnd5e:threat"}
