"""Proofs that contract identity includes semantic invariants, not only JSON Schema."""

from __future__ import annotations

import copy

from scripts.generate_vnext_contract_bundle import make_bundle

from dungeonmind.contracts.vnext.invariants import (
    RUNTIME_PARITY_CHECKERS,
    SEMANTIC_INVARIANTS,
    assert_checker_ids_match_manifest,
    assert_runtime_matches_manifest,
    binding_invariant_ids,
    semantic_invariant_manifest,
)


def test_runtime_validators_match_semantic_invariant_manifest() -> None:
    assert_runtime_matches_manifest()


def test_parity_checkers_cover_every_binding_invariant_id() -> None:
    assert_checker_ids_match_manifest()
    assert set(RUNTIME_PARITY_CHECKERS) == binding_invariant_ids()


def test_bundle_includes_semantic_invariant_manifest() -> None:
    bundle = make_bundle()
    assert "semantic_invariants" in bundle
    assert bundle["semantic_invariants"]["manifest_schema"] == (
        "dm_vnext_semantic_invariant_manifest_v1"
    )
    assert bundle["semantic_invariants"]["invariant_count"] == len(SEMANTIC_INVARIANTS)
    ids = [row["invariant_id"] for row in bundle["semantic_invariants"]["invariants"]]
    assert ids == sorted(ids)
    assert "vnext.value.NonBlankId.reject_whitespace_only" in ids
    assert "vnext.model.SemanticProfileDescriptorV2.term_namespaces" in ids


def test_validator_only_semantic_mutation_changes_aggregate() -> None:
    original = make_bundle(verify_runtime=False)["aggregate_sha256"]
    mutated = copy.deepcopy(list(SEMANTIC_INVARIANTS))
    for row in mutated:
        if row["invariant_id"] == "vnext.value.NonBlankId.reject_whitespace_only":
            row["definition"]["reject_if_empty_after_strip"] = False
            row["definition"]["reject_examples"] = [""]
            break
    else:
        raise AssertionError("NonBlankId invariant missing")
    changed = make_bundle(
        invariants=tuple(mutated),
        verify_runtime=False,
    )["aggregate_sha256"]
    assert changed != original


def test_term_namespaces_manifest_mutation_changes_aggregate() -> None:
    original = make_bundle(verify_runtime=False)["aggregate_sha256"]
    mutated = copy.deepcopy(list(SEMANTIC_INVARIANTS))
    for row in mutated:
        if row["invariant_id"] == (
            "vnext.model.SemanticProfileDescriptorV2.term_namespaces"
        ):
            row["definition"]["rules"] = ["each_item_must_be_non_empty"]
            break
    else:
        raise AssertionError("term_namespaces invariant missing")
    changed = make_bundle(
        invariants=tuple(mutated),
        verify_runtime=False,
    )["aggregate_sha256"]
    assert changed != original


def test_schema_shape_alone_does_not_capture_nonblank_semantics() -> None:
    """Document the stop-condition: JSON Schema still allows whitespace-only IDs."""
    from dungeonmind.contracts.vnext import Entity

    schema = Entity.model_json_schema()
    entity_id = schema["properties"]["entity_id"]
    assert entity_id.get("minLength") == 1
    # Without the invariant manifest, schema would accept whitespace-only.
    assert "pattern" not in entity_id
    # Manifest identity is what closes that gap.
    manifest = semantic_invariant_manifest()
    nonblank = next(
        row
        for row in manifest["invariants"]
        if row["invariant_id"] == "vnext.value.NonBlankId.reject_whitespace_only"
    )
    assert nonblank["definition"]["reject_if_empty_after_strip"] is True


def test_schema_shape_alone_does_not_capture_term_namespace_semantics() -> None:
    from dungeonmind.contracts.vnext import SemanticProfileDescriptorV2

    schema = SemanticProfileDescriptorV2.model_json_schema()
    term_ns = schema["properties"]["term_namespaces"]
    # JSON Schema only encodes list[str] + minItems; lowercase/no-colon lives in manifest.
    assert term_ns.get("minItems") == 1
    assert "pattern" not in term_ns.get("items", {})
    manifest = semantic_invariant_manifest()
    row = next(
        item
        for item in manifest["invariants"]
        if item["invariant_id"]
        == "vnext.model.SemanticProfileDescriptorV2.term_namespaces"
    )
    assert "each_item_must_not_contain_colon" in row["definition"]["rules"]
