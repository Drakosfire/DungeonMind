"""Unit checks for the deterministic K0.2 semantic witness."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tests.witness.k0_semantic_normalize import (
    REQUIRED_HISTORICAL_CASE_IDS,
    REQUIRED_OPERATION_IDS,
    WitnessValidationError,
    aggregate_semantic_sha256,
    find_forbidden_nondeterminism,
    normalize_semantic,
    sha256_canonical,
    validate_witness,
)
from tests.witness.k0_semantic_run import run_witness


@pytest.fixture(scope="module")
def witness() -> dict:
    return run_witness(adapter="memory")


def test_observation_only_mutations_do_not_change_digest() -> None:
    semantic = {"object_ids": ["obj:a"], "projected_at": "first"}
    changed_observation = {"object_ids": ["obj:a"], "projected_at": "second"}
    assert sha256_canonical(normalize_semantic(semantic)) == sha256_canonical(
        normalize_semantic(changed_observation)
    )

    changed_semantic = {"object_ids": ["obj:b"], "projected_at": "second"}
    assert sha256_canonical(normalize_semantic(semantic)) != sha256_canonical(
        normalize_semantic(changed_semantic)
    )


def test_normalization_preserves_list_order_and_undeclared_at_keys() -> None:
    # Contractual ranking/order must participate in equality.
    first = normalize_semantic({"matched_object_ids": ["obj:a", "obj:b"]})
    second = normalize_semantic({"matched_object_ids": ["obj:b", "obj:a"]})
    assert sha256_canonical(first) != sha256_canonical(second)

    # Keys outside the explicit observation allowlist are retained, even when
    # they carry an "_at" suffix; the forbidden-field guard flags them instead.
    retained = normalize_semantic({"reviewed_at": "2026-08-25"})
    assert retained == {"reviewed_at": "2026-08-25"}
    assert find_forbidden_nondeterminism(retained) == ["$.reviewed_at"]
    assert find_forbidden_nondeterminism({"object_ids": ["obj:a"]}) == []


def test_validate_rejects_missing_duplicate_and_forbidden_operations(
    witness: dict,
) -> None:
    missing = copy.deepcopy(witness)
    missing["operations"] = [
        row for row in missing["operations"] if row["id"] != REQUIRED_OPERATION_IDS[0]
    ]
    with pytest.raises(WitnessValidationError, match="missing required operation id"):
        validate_witness(missing)

    duplicate = copy.deepcopy(witness)
    duplicate["operations"].append(copy.deepcopy(duplicate["operations"][0]))
    with pytest.raises(WitnessValidationError, match="duplicate operation id"):
        validate_witness(duplicate)

    forbidden = copy.deepcopy(witness)
    row = forbidden["operations"][0]
    row["semantic_result"]["local_path"] = "/home/forbidden"
    row["semantic_sha256"] = sha256_canonical(row["semantic_result"])
    with pytest.raises(WitnessValidationError, match="forbidden nondeterministic field"):
        validate_witness(forbidden)


def test_validate_fails_closed_on_declared_inputs(witness: dict) -> None:
    tampered_base = copy.deepcopy(witness)
    tampered_base["inputs"]["dungeonmind_base_tree_sha"] = "0" * 40
    with pytest.raises(WitnessValidationError, match="dungeonmind_base_tree_sha"):
        validate_witness(tampered_base)

    tampered_landed = copy.deepcopy(witness)
    tampered_landed["inputs"]["dungeonmind_landed_base_sha"] = "0" * 40
    with pytest.raises(WitnessValidationError, match="dungeonmind_landed_base_sha"):
        validate_witness(tampered_landed)

    tampered_inventory = copy.deepcopy(witness)
    tampered_inventory["inputs"]["k0_inventory_digest"] = "sha256:" + "0" * 64
    with pytest.raises(WitnessValidationError, match="k0_inventory_digest"):
        validate_witness(tampered_inventory)

    tampered_fixture = copy.deepcopy(witness)
    tampered_fixture["fixture"]["world_id"] = "world:tampered"
    with pytest.raises(WitnessValidationError, match="fixture_digest"):
        validate_witness(tampered_fixture)

    tampered_policy = copy.deepcopy(witness)
    tampered_policy["normalization_policy"]["rules"] = []
    with pytest.raises(WitnessValidationError, match="normalization_policy"):
        validate_witness(tampered_policy)


def test_validate_fails_closed_on_historical_case_set(witness: dict) -> None:
    assert REQUIRED_HISTORICAL_CASE_IDS
    missing = copy.deepcopy(witness)
    dropped = missing["historical_compatibility"].pop()
    with pytest.raises(WitnessValidationError, match="missing required historical case"):
        validate_witness(missing)
    assert dropped["case_id"] in REQUIRED_HISTORICAL_CASE_IDS

    duplicate = copy.deepcopy(witness)
    duplicate["historical_compatibility"].append(
        copy.deepcopy(duplicate["historical_compatibility"][0])
    )
    with pytest.raises(WitnessValidationError, match="duplicate historical"):
        validate_witness(duplicate)


def test_memory_witness_contains_every_required_operation(witness: dict) -> None:
    assert {row["id"] for row in witness["operations"]} == set(REQUIRED_OPERATION_IDS)
    assert witness["schema"] == "dm_k0_semantic_witness_v1"
    case_ids = [row["case_id"] for row in witness["historical_compatibility"]]
    assert sorted(case_ids) == sorted(REQUIRED_HISTORICAL_CASE_IDS)
    assert len(case_ids) == len(set(case_ids))


def test_player_results_never_contain_hidden_content(witness: dict) -> None:
    player_rows = [
        row
        for row in witness["operations"]
        if row["id"]
        in {
            "read.deterministic_search",
            "scope.player_campaign",
            "read.neighborhood.depth_1",
            "read.neighborhood.depth_2",
        }
    ]
    assert len(player_rows) == 4
    serialized = json.dumps(player_rows, sort_keys=True)
    # Hidden labels/content must never appear in player-visible results.
    assert "Hidden Cache" not in serialized
    assert "Traitor's Keep" not in serialized
    for row in player_rows:
        result = row["semantic_result"]
        assert "obj:alpha-secret" not in result.get("object_ids", [])
        assert "obj:alpha-secret" not in result.get("matched_object_ids", [])
    # Neighborhood reads must explicitly record that the GM-only seed neighbor
    # (pinned by the fixture manifest) stayed fail-closed under PLAYER.
    neighborhood = [r for r in player_rows if r["id"].startswith("read.neighborhood.")]
    assert len(neighborhood) == 2
    assert all(r["semantic_result"]["player_traversal_fail_closed"] is True for r in neighborhood)


def test_historical_read_differs_from_head_projection(witness: dict) -> None:
    rows = {row["id"]: row for row in witness["operations"]}
    head = rows["read.head_projection"]["semantic_result"]
    historical = rows["read.exact_historical_revision"]["semantic_result"]
    assert historical["revision_id"] != head["revision_id"]
    assert (
        rows["read.exact_historical_revision"]["semantic_sha256"]
        != rows["read.head_projection"]["semantic_sha256"]
    )
    assert set(historical["object_ids"]) < set(head["object_ids"])


def test_checked_in_golden_matches_when_present(witness: dict) -> None:
    golden = Path(__file__).resolve().parents[2] / "Docs/Reports/K0-golden-semantic-witness-v1.json"
    if not golden.exists():
        pytest.skip("K0.2 golden witness has not been generated yet")
    assert json.loads(golden.read_text(encoding="utf-8")) == witness


def test_memory_witness_double_run_has_equal_aggregate_digest() -> None:
    first = run_witness(adapter="memory")
    second = run_witness(adapter="memory")
    assert first["aggregate_semantic_sha256"] == second["aggregate_semantic_sha256"]
    assert aggregate_semantic_sha256(first["operations"]) == aggregate_semantic_sha256(
        second["operations"]
    )
