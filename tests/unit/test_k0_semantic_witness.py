"""Unit checks for the deterministic K0.2 semantic witness."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tests.witness.k0_semantic_normalize import (
    REQUIRED_OPERATION_IDS,
    WitnessValidationError,
    aggregate_semantic_sha256,
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


def test_memory_witness_contains_every_required_operation(witness: dict) -> None:
    assert {row["id"] for row in witness["operations"]} == set(REQUIRED_OPERATION_IDS)
    assert witness["schema"] == "dm_k0_semantic_witness_v1"
    assert witness["historical_compatibility"]


def test_player_results_never_contain_hidden_content(witness: dict) -> None:
    player_rows = [
        row
        for row in witness["operations"]
        if row["id"] in {"read.deterministic_search", "scope.player_campaign"}
    ]
    serialized = json.dumps(player_rows, sort_keys=True)
    assert "obj:alpha-secret" not in serialized
    assert "Hidden Cache" not in serialized
    assert "Traitor's Keep" not in serialized


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
